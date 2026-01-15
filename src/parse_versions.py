"""
Version parsing module for GitHub releases.

Parses diverse version schemes including SemVer, CalVer, package-scoped,
product-named, and development builds.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VersionInfo:
    """Parsed version information."""

    # Original inputs
    release_name: str
    tag_name: str = ""

    # Classification
    version_scheme: str = "unknown"  # semver, calver, package_scoped, product_named, dev_build, descriptive, unknown
    parseable: bool = False

    # Version components (nullable)
    major_version: Optional[int] = None
    minor_version: Optional[int] = None
    patch_version: Optional[int] = None
    year: Optional[int] = None
    month: Optional[int] = None

    # Metadata
    version_prefix: str = ""
    prerelease_tag: str = ""
    prerelease_number: Optional[int] = None
    build_metadata: str = ""
    is_dev_build: bool = False
    product_name: str = ""
    package_name: str = ""

    # Raw version string extracted
    raw_version: str = ""


# Regex patterns with named groups and verbose mode for readability

# SemVer pattern (strict): v?MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
SEMVER_PATTERN = re.compile(
    r"""
    ^
    (?P<prefix>v|V|version[-_]?|release[-_]?)?  # Optional prefix
    (?P<major>\d+)                               # Major version (required)
    \.
    (?P<minor>\d+)                               # Minor version (required)
    \.
    (?P<patch>\d+)                               # Patch version (required)
    (?:
        -                                        # Prerelease separator
        (?P<prerelease>
            [0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*   # Prerelease identifiers
        )
    )?
    (?:
        \+                                       # Build metadata separator
        (?P<build>
            [0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*   # Build metadata
        )
    )?
    $
    """,
    re.VERBOSE
)

# CalVer pattern: YYYY.MM[.DD[.HH]][bN]
CALVER_PATTERN = re.compile(
    r"""
    ^
    (?P<prefix>v|V)?                             # Optional v prefix
    (?P<year>\d{4})                              # Year (4 digits)
    \.
    (?P<month>\d{1,2})                           # Month (1-2 digits)
    (?:
        \.
        (?P<day>\d{1,2})                         # Optional day
        (?:
            \.
            (?P<hour>\d{1,2})                    # Optional hour
        )?
    )?
    (?:
        b                                        # Beta suffix
        (?P<beta>\d+)
    )?
    $
    """,
    re.VERBOSE
)

# Package-scoped pattern: @scope/package@version or package==version
PACKAGE_SCOPED_PATTERN = re.compile(
    r"""
    ^
    (?P<package>
        @?[^@=]+                                 # Package name (may start with @)
    )
    (?:@|==)                                     # Separator
    (?P<version>.+)                              # Version string
    $
    """,
    re.VERBOSE
)

# Product-named pattern: ProductName vX.Y.Z
PRODUCT_NAMED_PATTERN = re.compile(
    r"""
    ^
    (?P<product>.+?)                             # Product name (non-greedy)
    \s+                                          # Whitespace
    (?::|\s)?                                    # Optional colon separator
    \s*
    (?P<version>v?\d+\.\d+.*)                    # Version string
    $
    """,
    re.VERBOSE
)

# Release-prefixed pattern: "Release vX.Y.Z" or "Release X.Y.Z"
RELEASE_PREFIX_PATTERN = re.compile(
    r"""
    ^
    (?:Release|Version)\s+                       # "Release " or "Version "
    (?P<version>v?\d+\.\d+.*)                    # Version string
    $
    """,
    re.VERBOSE | re.IGNORECASE
)

# Development build indicators
DEV_BUILD_PATTERN = re.compile(
    r"""
    (?P<type>nightly|canary|snapshot|dev)        # Dev build type
    """,
    re.VERBOSE | re.IGNORECASE
)

# Prerelease tag extraction
PRERELEASE_TAG_PATTERN = re.compile(
    r"""
    ^
    (?P<tag>alpha|beta|rc|canary|nightly|dev)    # Tag name
    (?:\.|-)?                                    # Optional separator
    (?P<number>\d+)?                             # Optional number
    """,
    re.VERBOSE | re.IGNORECASE
)


def clean_version_string(version: str) -> str:
    """Clean up version string by removing emoji, extra whitespace, etc."""
    # Remove emoji and special unicode characters
    version = re.sub(r'[^\x00-\x7F]+', '', version)

    # Strip whitespace
    version = version.strip()

    # Remove surrounding quotes if present
    version = version.strip('"\'')

    # Extract version before parentheses if present (e.g., "1.2.3 (April 26, 2024)")
    if '(' in version:
        version = version.split('(')[0].strip()

    return version


def extract_prerelease_info(prerelease: str) -> tuple[str, Optional[int]]:
    """Extract prerelease tag and number from prerelease string."""
    if not prerelease:
        return "", None

    match = PRERELEASE_TAG_PATTERN.match(prerelease)
    if match:
        tag = match.group('tag').lower()
        number_str = match.group('number')
        number = int(number_str) if number_str else None
        return tag, number

    # If no match, return the whole string as tag
    return prerelease.lower(), None


def try_parse_semver(version: str) -> Optional[VersionInfo]:
    """Try to parse as semantic version."""
    match = SEMVER_PATTERN.match(version)
    if not match:
        return None

    info = VersionInfo(
        release_name=version,
        version_scheme="semver",
        parseable=True,
        raw_version=version
    )

    # Extract components
    info.version_prefix = match.group('prefix') or ""
    info.major_version = int(match.group('major'))
    info.minor_version = int(match.group('minor'))
    info.patch_version = int(match.group('patch'))

    # Extract prerelease info
    prerelease = match.group('prerelease') or ""
    if prerelease:
        info.prerelease_tag, info.prerelease_number = extract_prerelease_info(prerelease)

    # Build metadata
    info.build_metadata = match.group('build') or ""

    # Check if it's a dev build
    if DEV_BUILD_PATTERN.search(prerelease):
        info.is_dev_build = True

    return info


def try_parse_calver(version: str) -> Optional[VersionInfo]:
    """Try to parse as calendar version."""
    match = CALVER_PATTERN.match(version)
    if not match:
        return None

    year = int(match.group('year'))
    month = int(match.group('month'))

    # Validate year and month ranges
    if not (2000 <= year <= 2030) or not (1 <= month <= 12):
        return None

    info = VersionInfo(
        release_name=version,
        version_scheme="calver",
        parseable=True,
        raw_version=version
    )

    # Prefix
    prefix = match.group('prefix')
    if prefix:
        info.version_prefix = prefix

    info.year = year
    info.month = month

    # Day (treat as patch for consistency)
    day = match.group('day')
    if day:
        info.patch_version = int(day)

    # Hour (store in major_version if present, as we don't have a dedicated hour field)
    # This is a bit hacky but maintains the data
    hour = match.group('hour')
    if hour:
        info.major_version = int(hour)

    # Beta suffix
    beta = match.group('beta')
    if beta:
        info.prerelease_tag = "beta"
        info.prerelease_number = int(beta)

    return info


def try_parse_package_scoped(version: str) -> Optional[VersionInfo]:
    """Try to parse as package-scoped version (e.g., @scope/package@version)."""
    match = PACKAGE_SCOPED_PATTERN.match(version)
    if not match:
        return None

    package = match.group('package')
    version_str = match.group('version')

    info = VersionInfo(
        release_name=version,
        version_scheme="package_scoped",
        parseable=True,
        raw_version=version_str,
        package_name=package
    )

    # Try to parse the version part as semver
    semver_info = try_parse_semver(version_str)
    if semver_info:
        info.major_version = semver_info.major_version
        info.minor_version = semver_info.minor_version
        info.patch_version = semver_info.patch_version
        info.version_prefix = semver_info.version_prefix
        info.prerelease_tag = semver_info.prerelease_tag
        info.prerelease_number = semver_info.prerelease_number
        info.build_metadata = semver_info.build_metadata
        info.is_dev_build = semver_info.is_dev_build

    return info


def try_parse_product_named(version: str) -> Optional[VersionInfo]:
    """Try to parse as product-named version (e.g., 'Bun v1.2.3')."""
    match = PRODUCT_NAMED_PATTERN.match(version)
    if not match:
        return None

    product = match.group('product').strip()
    version_str = match.group('version')

    # Avoid matching too broadly - product name should be reasonable
    if len(product) > 50 or len(product.split()) > 5:
        return None

    info = VersionInfo(
        release_name=version,
        version_scheme="product_named",
        parseable=True,
        raw_version=version_str,
        product_name=product
    )

    # Try to parse the version part as semver
    semver_info = try_parse_semver(version_str)
    if semver_info:
        info.major_version = semver_info.major_version
        info.minor_version = semver_info.minor_version
        info.patch_version = semver_info.patch_version
        info.version_prefix = semver_info.version_prefix
        info.prerelease_tag = semver_info.prerelease_tag
        info.prerelease_number = semver_info.prerelease_number
        info.build_metadata = semver_info.build_metadata
        info.is_dev_build = semver_info.is_dev_build

    return info


def try_parse_release_prefix(version: str) -> Optional[VersionInfo]:
    """Try to parse 'Release vX.Y.Z' pattern."""
    match = RELEASE_PREFIX_PATTERN.match(version)
    if not match:
        return None

    version_str = match.group('version')

    info = VersionInfo(
        release_name=version,
        version_scheme="semver",
        parseable=True,
        raw_version=version_str
    )

    # Try to parse the version part as semver
    semver_info = try_parse_semver(version_str)
    if semver_info:
        info.major_version = semver_info.major_version
        info.minor_version = semver_info.minor_version
        info.patch_version = semver_info.patch_version
        info.version_prefix = semver_info.version_prefix
        info.prerelease_tag = semver_info.prerelease_tag
        info.prerelease_number = semver_info.prerelease_number
        info.build_metadata = semver_info.build_metadata
        info.is_dev_build = semver_info.is_dev_build

    return info


def check_dev_build(version: str) -> bool:
    """Check if version string indicates a development build."""
    return bool(DEV_BUILD_PATTERN.search(version))


def parse_version(release_name: str, tag_name: str = "") -> VersionInfo:
    """
    Parse a version string using a waterfall approach.

    Detection order:
    1. Use tag_name if release_name is empty
    2. Try SemVer parsing (strictest)
    3. Try CalVer detection
    4. Try package-scoped extraction
    5. Try product-named extraction
    6. Try "Release vX.Y.Z" pattern
    7. Flag as descriptive/non-parseable

    Args:
        release_name: The release name from GitHub
        tag_name: The tag name (fallback if release_name is empty)

    Returns:
        VersionInfo object with parsed components
    """
    # Use tag_name if release_name is empty
    if not release_name or release_name.strip() == "":
        if tag_name:
            release_name = tag_name
        else:
            return VersionInfo(
                release_name="",
                tag_name=tag_name,
                version_scheme="unknown",
                parseable=False
            )

    # Clean the version string
    version = clean_version_string(release_name)

    if not version:
        return VersionInfo(
            release_name=release_name,
            tag_name=tag_name,
            version_scheme="unknown",
            parseable=False
        )

    # Try each parser in order
    # Note: CalVer must come before SemVer because YYYY.MM.DD is valid SemVer
    parsers = [
        try_parse_calver,
        try_parse_package_scoped,
        try_parse_release_prefix,
        try_parse_semver,
        try_parse_product_named,
    ]

    for parser in parsers:
        result = parser(version)
        if result:
            result.tag_name = tag_name
            # Check for dev build indicators
            if check_dev_build(version):
                result.is_dev_build = True
            return result

    # If nothing matched, classify as descriptive
    return VersionInfo(
        release_name=release_name,
        tag_name=tag_name,
        version_scheme="descriptive",
        parseable=False,
        raw_version=version
    )
