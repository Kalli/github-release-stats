"""
Unit tests for version parsing module.
"""

import pytest
from src.parse_versions import (
    parse_version,
    try_parse_semver,
    try_parse_calver,
    try_parse_package_scoped,
    try_parse_product_named,
    clean_version_string,
    extract_prerelease_info,
)


class TestCleanVersionString:
    """Test version string cleaning."""

    def test_removes_emoji(self):
        assert clean_version_string("v1.0.0 📦") == "v1.0.0"
        assert clean_version_string("Inso CLI 2.9.0-beta.0 📦") == "Inso CLI 2.9.0-beta.0"

    def test_strips_whitespace(self):
        assert clean_version_string("  v1.0.0  ") == "v1.0.0"
        assert clean_version_string("\tv1.0.0\n") == "v1.0.0"

    def test_removes_quotes(self):
        assert clean_version_string('"v1.0.0"') == "v1.0.0"
        assert clean_version_string("'v1.0.0'") == "v1.0.0"


class TestExtractPrereleaseInfo:
    """Test prerelease information extraction."""

    def test_alpha_with_number(self):
        tag, num = extract_prerelease_info("alpha.1")
        assert tag == "alpha"
        assert num == 1

    def test_beta_without_number(self):
        tag, num = extract_prerelease_info("beta")
        assert tag == "beta"
        assert num is None

    def test_rc_with_hyphen(self):
        tag, num = extract_prerelease_info("rc-2")
        assert tag == "rc"
        assert num == 2

    def test_nightly(self):
        tag, num = extract_prerelease_info("nightly.20230831")
        assert tag == "nightly"
        assert num == 20230831


class TestSemVerParsing:
    """Test semantic version parsing."""

    def test_basic_semver(self):
        result = try_parse_semver("1.2.3")
        assert result is not None
        assert result.major_version == 1
        assert result.minor_version == 2
        assert result.patch_version == 3
        assert result.version_scheme == "semver"
        assert result.parseable is True

    def test_semver_with_v_prefix(self):
        result = try_parse_semver("v1.2.3")
        assert result is not None
        assert result.version_prefix == "v"
        assert result.major_version == 1
        assert result.minor_version == 2
        assert result.patch_version == 3

    def test_semver_with_alpha(self):
        result = try_parse_semver("v1.2.3-alpha.1")
        assert result is not None
        assert result.major_version == 1
        assert result.minor_version == 2
        assert result.patch_version == 3
        assert result.prerelease_tag == "alpha"
        assert result.prerelease_number == 1

    def test_semver_with_beta(self):
        result = try_parse_semver("2.0.0-beta.5")
        assert result is not None
        assert result.prerelease_tag == "beta"
        assert result.prerelease_number == 5

    def test_semver_with_rc(self):
        result = try_parse_semver("v9.11.6-rc2")
        assert result is not None
        assert result.prerelease_tag == "rc"
        assert result.prerelease_number == 2

    def test_semver_with_build_metadata(self):
        result = try_parse_semver("1.0.0+20130313144700")
        assert result is not None
        assert result.build_metadata == "20130313144700"

    def test_semver_with_canary(self):
        result = try_parse_semver("v13.2.5-canary.32")
        assert result is not None
        assert result.prerelease_tag == "canary"
        assert result.prerelease_number == 32
        assert result.is_dev_build is True

    def test_semver_with_nightly(self):
        result = try_parse_semver("v7.3.3-nightly.20230831")
        assert result is not None
        assert result.prerelease_tag == "nightly"
        assert result.is_dev_build is True

    def test_capital_v_prefix(self):
        result = try_parse_semver("V3.11.0")
        assert result is not None
        assert result.version_prefix == "V"
        assert result.major_version == 3

    def test_semver_prerelease_without_dash(self):
        """Test prerelease without dash separator (e.g., v3.10.0a5)."""
        result = try_parse_semver("v3.10.0a5")
        assert result is not None
        assert result.major_version == 3
        assert result.minor_version == 10
        assert result.patch_version == 0
        assert result.prerelease_tag == "alpha"
        assert result.prerelease_number == 5

    def test_semver_short_alpha(self):
        """Test short alpha form (a instead of alpha)."""
        result = try_parse_semver("1.2.3a1")
        assert result is not None
        assert result.prerelease_tag == "alpha"
        assert result.prerelease_number == 1

    def test_semver_short_beta(self):
        """Test short beta form (b instead of beta)."""
        result = try_parse_semver("2.0.0b3")
        assert result is not None
        assert result.prerelease_tag == "beta"
        assert result.prerelease_number == 3

    def test_semver_four_part_version(self):
        """Test 4-part version number (e.g., v6.0.3.4)."""
        result = try_parse_semver("v6.0.3.4")
        assert result is not None
        assert result.major_version == 6
        assert result.minor_version == 0
        assert result.patch_version == 3
        assert result.build_metadata == "build.4"

    def test_semver_prefix_with_dash(self):
        """Test prefix with dash (e.g., nw-v0.22.0)."""
        result = try_parse_semver("nw-v0.22.0")
        assert result is not None
        assert result.version_prefix == "nw-v"
        assert result.major_version == 0
        assert result.minor_version == 22
        assert result.patch_version == 0

    def test_semver_with_release_suffix(self):
        """Test version with 'Release' suffix (e.g., 0.44.0 Release)."""
        result = try_parse_semver("0.44.0 Release")
        assert result is not None
        assert result.major_version == 0
        assert result.minor_version == 44
        assert result.patch_version == 0

    def test_invalid_semver_missing_patch(self):
        result = try_parse_semver("1.2")
        assert result is None

    def test_invalid_semver_text(self):
        result = try_parse_semver("Bugfix Release")
        assert result is None


class TestCalVerParsing:
    """Test calendar version parsing."""

    def test_basic_calver(self):
        result = try_parse_calver("2025.12.0")
        assert result is not None
        assert result.year == 2025
        assert result.month == 12
        assert result.patch_version == 0
        assert result.version_scheme == "calver"

    def test_calver_without_micro(self):
        result = try_parse_calver("2020.10")
        assert result is not None
        assert result.year == 2020
        assert result.month == 10
        assert result.patch_version is None

    def test_calver_with_beta(self):
        result = try_parse_calver("2026.1.0b2")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.patch_version == 0
        assert result.prerelease_tag == "beta"
        assert result.prerelease_number == 2

    def test_calver_invalid_year(self):
        result = try_parse_calver("1999.12.0")
        assert result is None

    def test_calver_invalid_month(self):
        result = try_parse_calver("2025.13.0")
        assert result is None

    def test_calver_future_year(self):
        result = try_parse_calver("2031.1.0")
        assert result is None


class TestPackageScopedParsing:
    """Test package-scoped version parsing."""

    def test_npm_scoped_package(self):
        result = try_parse_package_scoped("@gradio/chatbot@0.26.16")
        assert result is not None
        assert result.package_name == "@gradio/chatbot"
        assert result.major_version == 0
        assert result.minor_version == 26
        assert result.patch_version == 16
        assert result.version_scheme == "package_scoped"

    def test_npm_package_without_scope(self):
        result = try_parse_package_scoped("create-astro@4.2.1")
        assert result is not None
        assert result.package_name == "create-astro"
        assert result.major_version == 4
        assert result.minor_version == 2
        assert result.patch_version == 1

    def test_python_package(self):
        result = try_parse_package_scoped("langchain-community==0.3.1")
        assert result is not None
        assert result.package_name == "langchain-community"
        assert result.major_version == 0
        assert result.minor_version == 3
        assert result.patch_version == 1

    def test_package_with_prerelease(self):
        result = try_parse_package_scoped("@astrojs/react@2.3.2-beta.1")
        assert result is not None
        assert result.package_name == "@astrojs/react"
        assert result.prerelease_tag == "beta"
        assert result.prerelease_number == 1


class TestProductNamedParsing:
    """Test product-named version parsing."""

    def test_product_with_version(self):
        result = try_parse_product_named("Bun v1.1.39")
        assert result is not None
        assert result.product_name == "Bun"
        assert result.major_version == 1
        assert result.minor_version == 1
        assert result.patch_version == 39
        assert result.version_scheme == "product_named"

    def test_product_with_colon_separator(self):
        result = try_parse_product_named("puppeteer: v19.7.1")
        assert result is not None
        assert result.product_name == "puppeteer"
        assert result.major_version == 19
        assert result.minor_version == 7
        assert result.patch_version == 1

    def test_product_without_v_prefix(self):
        result = try_parse_product_named("Elasticsearch 6.8.23")
        assert result is not None
        assert result.product_name == "Elasticsearch"
        assert result.major_version == 6
        assert result.minor_version == 8
        assert result.patch_version == 23

    def test_product_multiword(self):
        result = try_parse_product_named("Ventoy 1.0.67 release")
        assert result is not None
        assert result.product_name == "Ventoy"
        # Note: "release" will be part of version string, which is okay

    def test_product_too_long_name_rejected(self):
        # Should reject if product name is unreasonably long
        long_name = "A" * 60 + " v1.0.0"
        result = try_parse_product_named(long_name)
        assert result is None


class TestParseVersionWaterfall:
    """Test the main parse_version function with waterfall detection."""

    def test_empty_release_name_uses_tag(self):
        result = parse_version("", tag_name="v1.2.3")
        assert result.major_version == 1
        assert result.minor_version == 2
        assert result.patch_version == 3

    def test_semver_detected_first(self):
        result = parse_version("v1.2.3")
        assert result.version_scheme == "semver"
        assert result.parseable is True

    def test_calver_detected(self):
        result = parse_version("2025.12.0")
        assert result.version_scheme == "calver"
        assert result.year == 2025

    def test_package_scoped_detected(self):
        result = parse_version("@gradio/chatbot@0.26.16")
        assert result.version_scheme == "package_scoped"
        assert result.package_name == "@gradio/chatbot"

    def test_product_named_detected(self):
        result = parse_version("Bun v1.1.39")
        assert result.version_scheme == "product_named"
        assert result.product_name == "Bun"

    def test_release_prefix_detected(self):
        result = parse_version("Release v1.6.2")
        assert result.version_scheme == "semver"
        assert result.major_version == 1

    def test_descriptive_release(self):
        result = parse_version("Bugfix Release")
        assert result.version_scheme == "descriptive"
        assert result.parseable is False

    def test_empty_both_fields(self):
        result = parse_version("", tag_name="")
        assert result.version_scheme == "unknown"
        assert result.parseable is False

    def test_dev_build_detection(self):
        result = parse_version("Nightly build 2026.01.03")
        assert result.is_dev_build is True

    def test_emoji_cleaned(self):
        result = parse_version("v1.0.0 📦")
        assert result.major_version == 1
        assert result.version_scheme == "semver"


class TestRealWorldExamples:
    """Test with real-world version strings from the dataset."""

    def test_examples_from_data(self):
        test_cases = [
            # (input, expected_scheme, expected_parseable)
            ("v1.75.0-nightly", "semver", True),
            ("2024.8.0b3", "calver", True),
            ("@astrojs/react@2.3.2", "package_scoped", True),
            ("v14.27.5", "semver", True),
            ("Release v1.6.2", "semver", True),
            ("@gradio/chatbot@0.26.16", "package_scoped", True),
            ("v4.0.0-beta.66", "semver", True),
            ("langchain-community==0.3.1", "package_scoped", True),
            ("Bun v1.1.39", "product_named", True),
            ("Metabase 0.23.0", "product_named", True),
            ("Elasticsearch 6.8.23", "product_named", True),
            ("Bugfix Release", "descriptive", False),
            ("snapshot-2023-11-12", "descriptive", False),
            ("Support for unicode letters.", "descriptive", False),
        ]

        for version_str, expected_scheme, expected_parseable in test_cases:
            result = parse_version(version_str)
            assert result.version_scheme == expected_scheme, \
                f"Failed for '{version_str}': expected {expected_scheme}, got {result.version_scheme}"
            assert result.parseable == expected_parseable, \
                f"Failed for '{version_str}': expected parseable={expected_parseable}, got {result.parseable}"

    def test_edge_cases_from_issues(self):
        """Test specific edge cases that were initially failing."""
        # Test v3.10.0a5 - prerelease without dash separator
        result = parse_version("v3.10.0a5")
        assert result.version_scheme == "semver"
        assert result.parseable is True
        assert result.major_version == 3
        assert result.minor_version == 10
        assert result.patch_version == 0
        assert result.prerelease_tag == "alpha"
        assert result.prerelease_number == 5

        # Test v6.0.3.4 - four-part version number
        result = parse_version("v6.0.3.4")
        assert result.version_scheme == "semver"
        assert result.parseable is True
        assert result.major_version == 6
        assert result.minor_version == 0
        assert result.patch_version == 3
        assert result.build_metadata == "build.4"

        # Test nw-v0.22.0 - prefix with dash
        result = parse_version("nw-v0.22.0")
        assert result.version_scheme == "semver"
        assert result.parseable is True
        assert result.version_prefix == "nw-v"
        assert result.major_version == 0
        assert result.minor_version == 22
        assert result.patch_version == 0

        # Test 0.44.0 Release - version followed by "Release"
        result = parse_version("0.44.0 Release")
        assert result.version_scheme == "semver"
        assert result.parseable is True
        assert result.major_version == 0
        assert result.minor_version == 44
        assert result.patch_version == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
