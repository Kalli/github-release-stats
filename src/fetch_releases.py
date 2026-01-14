#!/usr/bin/env python3
"""
Fetch GitHub releases for repositories and save to CSV.

This script fetches release data (or tags as fallback) for repositories
listed in repositories.csv and saves the results incrementally to releases.csv.
Supports crash recovery by tracking already-processed repositories.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests


# Constants
DEFAULT_REPOSITORIES_FILE = "data/repositories.csv"
DEFAULT_RELEASES_FILE = "data/releases.csv"
DEFAULT_NO_RELEASES_FILE = "data/no_releases.txt"
DEFAULT_PROGRESS_FILE = "data/fetch_progress.json"
RELEASES_PER_PAGE = 100
GITHUB_API_BASE = "https://api.github.com"


def get_github_token() -> Optional[str]:
    """
    Get GitHub token from environment variable or .env file.

    Returns:
        GitHub token if found, None otherwise
    """
    # Try environment variable first
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    # Try reading from .env file
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GITHUB_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")

    return None


def load_processed_repos(
    releases_csv: Path,
    no_releases_file: Path
) -> Set[str]:
    """
    Load set of repos already processed (with or without releases).

    Args:
        releases_csv: Path to releases CSV file
        no_releases_file: Path to no_releases.txt file

    Returns:
        Set of repository full names (owner/repo) that have been processed
    """
    processed = set()

    # Load repos that had releases/tags
    if releases_csv.exists():
        with open(releases_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed.add(row['repo_full_name'])

    # Load repos that had NO releases/tags
    if no_releases_file.exists():
        with open(no_releases_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('owner/repo'):  # Skip header
                    repo_name = line.split(',')[0]
                    processed.add(repo_name)

    return processed


def parse_link_header(link_header: str) -> Dict[str, str]:
    """
    Parse GitHub Link header for pagination.

    Args:
        link_header: Link header value from response

    Returns:
        Dictionary mapping rel values to URLs
    """
    links = {}
    if not link_header:
        return links

    # Parse format: <url>; rel="next", <url>; rel="last"
    for part in link_header.split(','):
        match = re.match(r'<([^>]+)>;\s*rel="([^"]+)"', part.strip())
        if match:
            url, rel = match.groups()
            links[rel] = url

    return links


def check_rate_limit_and_wait(response: requests.Response) -> None:
    """
    Check rate limit headers and wait if necessary.

    Args:
        response: HTTP response object
    """
    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

    if remaining < 100:  # Buffer of 100 requests
        wait_time = reset_time - time.time()
        if wait_time > 0:
            print(f"⏳ Rate limit low ({remaining} remaining), waiting {int(wait_time)}s...")
            time.sleep(wait_time + 1)


def fetch_with_retry(
    url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    timeout: int = 10
) -> Optional[requests.Response]:
    """
    Fetch URL with exponential backoff retry.

    Args:
        url: URL to fetch
        headers: Request headers
        params: Optional query parameters
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds

    Returns:
        Response object if successful, None if 404 or unrecoverable error
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()

            # Check and handle rate limiting
            check_rate_limit_and_wait(response)

            return response

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"⏳ Timeout, retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
            else:
                print(f"❌ Timeout after {max_retries} attempts")
                raise

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Repo deleted, moved, or endpoint doesn't exist
                return None
            elif e.response.status_code == 403:
                # Rate limit or access denied
                check_rate_limit_and_wait(e.response)
                if attempt < max_retries - 1:
                    continue
                raise
            else:
                raise

    return None


def fetch_releases_page(
    owner: str,
    repo: str,
    page: int,
    per_page: int,
    headers: Dict[str, str]
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Fetch a single page of releases.

    Args:
        owner: Repository owner
        repo: Repository name
        page: Page number
        per_page: Items per page
        headers: Request headers

    Returns:
        Tuple of (releases list, has_more_pages boolean)
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/releases"
    params = {"per_page": per_page, "page": page}

    response = fetch_with_retry(url, headers, params)
    if response is None:
        return [], False

    releases = response.json()

    # Check if there are more pages
    link_header = response.headers.get('Link', '')
    links = parse_link_header(link_header)
    has_next = 'next' in links

    return releases, has_next


def fetch_all_releases(
    owner: str,
    repo: str,
    headers: Dict[str, str],
    per_page: int = RELEASES_PER_PAGE
) -> List[Dict[str, Any]]:
    """
    Fetch all releases for a repository (paginated).

    Args:
        owner: Repository owner
        repo: Repository name
        headers: Request headers
        per_page: Releases per page

    Returns:
        List of all releases
    """
    all_releases = []
    page = 1

    while True:
        releases, has_next = fetch_releases_page(owner, repo, page, per_page, headers)

        all_releases.extend(releases)

        if not has_next or len(releases) < per_page:
            break

        page += 1
        time.sleep(0.2)  # Small delay between pages

    return all_releases


def fetch_tags_page(
    owner: str,
    repo: str,
    page: int,
    per_page: int,
    headers: Dict[str, str]
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Fetch a single page of tags.

    Args:
        owner: Repository owner
        repo: Repository name
        page: Page number
        per_page: Items per page
        headers: Request headers

    Returns:
        Tuple of (tags list, has_more_pages boolean)
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/tags"
    params = {"per_page": per_page, "page": page}

    response = fetch_with_retry(url, headers, params)
    if response is None:
        return [], False

    tags = response.json()

    # Check if there are more pages
    link_header = response.headers.get('Link', '')
    links = parse_link_header(link_header)
    has_next = 'next' in links

    return tags, has_next


def fetch_commit_date(
    owner: str,
    repo: str,
    sha: str,
    headers: Dict[str, str]
) -> Optional[str]:
    """
    Fetch commit date for a given SHA.

    Args:
        owner: Repository owner
        repo: Repository name
        sha: Commit SHA
        headers: Request headers

    Returns:
        Commit date string in ISO format, or None if failed
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}"

    response = fetch_with_retry(url, headers)
    if response is None:
        return None

    commit_data = response.json()
    return commit_data.get('commit', {}).get('author', {}).get('date')


def fetch_all_tags(
    owner: str,
    repo: str,
    headers: Dict[str, str],
    per_page: int = RELEASES_PER_PAGE
) -> List[Dict[str, Any]]:
    """
    Fetch all tags for a repository with commit dates.

    Args:
        owner: Repository owner
        repo: Repository name
        headers: Request headers
        per_page: Tags per page

    Returns:
        List of all tags with commit dates
    """
    all_tags = []
    page = 1

    while True:
        tags, has_next = fetch_tags_page(owner, repo, page, per_page, headers)

        # Fetch commit date for each tag
        for tag in tags:
            sha = tag.get('commit', {}).get('sha')
            if sha:
                commit_date = fetch_commit_date(owner, repo, sha, headers)
                tag['commit_date'] = commit_date
                time.sleep(0.1)  # Small delay between commit fetches

        all_tags.extend(tags)

        if not has_next or len(tags) < per_page:
            break

        page += 1
        time.sleep(0.2)  # Small delay between pages

    return all_tags


def extract_release_data(
    repo_full_name: str,
    release: Dict[str, Any],
    source: str = "release"
) -> Dict[str, Any]:
    """
    Extract relevant fields from a release object.

    Args:
        repo_full_name: Full repository name (owner/repo)
        release: Release object from GitHub API
        source: Data source ("release" or "tag")

    Returns:
        Dictionary with extracted fields
    """
    return {
        "repo_full_name": repo_full_name,
        "github_release_id": release.get("id", ""),
        "tag_name": release.get("tag_name", ""),
        "release_name": release.get("name", ""),
        "published_at": release.get("published_at", ""),
        "is_prerelease": release.get("prerelease", False),
        "is_draft": release.get("draft", False),
        "source": source,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def extract_tag_data(
    repo_full_name: str,
    tag: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract relevant fields from a tag object.

    Args:
        repo_full_name: Full repository name (owner/repo)
        tag: Tag object from GitHub API

    Returns:
        Dictionary with extracted fields
    """
    return {
        "repo_full_name": repo_full_name,
        "github_release_id": "",
        "tag_name": tag.get("name", ""),
        "release_name": "",
        "published_at": tag.get("commit_date", ""),
        "is_prerelease": False,
        "is_draft": False,
        "source": "tag",
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def initialize_csv_files(
    releases_csv: Path,
    no_releases_file: Path
) -> None:
    """
    Initialize CSV files with headers if they don't exist.

    Args:
        releases_csv: Path to releases CSV file
        no_releases_file: Path to no_releases.txt file
    """
    # Ensure data directory exists
    releases_csv.parent.mkdir(parents=True, exist_ok=True)

    # Initialize releases.csv
    if not releases_csv.exists():
        fieldnames = [
            "repo_full_name",
            "github_release_id",
            "tag_name",
            "release_name",
            "published_at",
            "is_prerelease",
            "is_draft",
            "source",
            "fetched_at",
        ]
        with open(releases_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    # Initialize no_releases.txt
    if not no_releases_file.exists():
        with open(no_releases_file, 'w', encoding='utf-8') as f:
            f.write("owner/repo-name,reason\n")


def append_releases_to_csv(
    releases: List[Dict[str, Any]],
    releases_csv: Path
) -> None:
    """
    Append releases to CSV file.

    Args:
        releases: List of release dictionaries
        releases_csv: Path to releases CSV file
    """
    if not releases:
        return

    fieldnames = [
        "repo_full_name",
        "github_release_id",
        "tag_name",
        "release_name",
        "published_at",
        "is_prerelease",
        "is_draft",
        "source",
        "fetched_at",
    ]

    with open(releases_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerows(releases)
        f.flush()  # Force write to disk


def append_to_no_releases(
    repo_full_name: str,
    reason: str,
    no_releases_file: Path
) -> None:
    """
    Append repository to no_releases.txt file.

    Args:
        repo_full_name: Full repository name
        reason: Reason why no releases (e.g., "no_releases_no_tags")
        no_releases_file: Path to no_releases.txt file
    """
    with open(no_releases_file, 'a', encoding='utf-8') as f:
        f.write(f"{repo_full_name},{reason}\n")
        f.flush()


def load_repositories(repositories_file: Path) -> List[Dict[str, Any]]:
    """
    Load repositories from CSV file.

    Args:
        repositories_file: Path to repositories CSV file

    Returns:
        List of repository dictionaries
    """
    repositories = []
    with open(repositories_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            repositories.append(row)
    return repositories


def save_progress(
    progress_file: Path,
    stats: Dict[str, Any]
) -> None:
    """
    Save progress to JSON file.

    Args:
        progress_file: Path to progress JSON file
        stats: Progress statistics dictionary
    """
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
        f.flush()


def process_repository(
    repo: Dict[str, Any],
    headers: Dict[str, str],
    releases_csv: Path,
    no_releases_file: Path
) -> Tuple[int, str]:
    """
    Process a single repository to fetch releases or tags.

    Args:
        repo: Repository dictionary
        headers: Request headers
        releases_csv: Path to releases CSV file
        no_releases_file: Path to no_releases.txt file

    Returns:
        Tuple of (releases_count, status)
        status can be: "releases", "tags", "none"
    """
    full_name = repo['full_name']
    owner, repo_name = full_name.split('/')

    print(f"📦 {full_name}... ", end="", flush=True)

    # Try to fetch releases first
    releases = fetch_all_releases(owner, repo_name, headers)

    if releases:
        # Process releases
        release_data = [extract_release_data(full_name, r, "release") for r in releases]
        append_releases_to_csv(release_data, releases_csv)
        print(f"✓ {len(releases)} releases")
        return len(releases), "releases"

    # No releases, try tags
    print("no releases, trying tags... ", end="", flush=True)
    tags = fetch_all_tags(owner, repo_name, headers)

    if tags:
        # Process tags
        tag_data = [extract_tag_data(full_name, t) for t in tags]
        append_releases_to_csv(tag_data, releases_csv)
        print(f"✓ {len(tags)} tags")
        return len(tags), "tags"

    # No releases or tags
    append_to_no_releases(full_name, "no_releases_no_tags", no_releases_file)
    print("⊘ no releases or tags")
    return 0, "none"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch GitHub releases for repositories and save to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch releases with token from environment
  export GITHUB_TOKEN=your_token_here
  python src/fetch_releases.py

  # Use custom input/output files
  python src/fetch_releases.py -i my_repos.csv -o my_releases.csv

  # Limit number of repositories to process
  python src/fetch_releases.py -n 10
        """
    )

    parser.add_argument(
        "-i", "--input",
        type=Path,
        default=Path(DEFAULT_REPOSITORIES_FILE),
        help=f"Input repositories CSV file (default: {DEFAULT_REPOSITORIES_FILE})"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path(DEFAULT_RELEASES_FILE),
        help=f"Output releases CSV file (default: {DEFAULT_RELEASES_FILE})"
    )

    parser.add_argument(
        "--no-releases-file",
        type=Path,
        default=Path(DEFAULT_NO_RELEASES_FILE),
        help=f"File to log repos without releases (default: {DEFAULT_NO_RELEASES_FILE})"
    )

    parser.add_argument(
        "--progress-file",
        type=Path,
        default=Path(DEFAULT_PROGRESS_FILE),
        help=f"Progress tracking JSON file (default: {DEFAULT_PROGRESS_FILE})"
    )

    parser.add_argument(
        "-n", "--limit",
        type=int,
        help="Limit number of repositories to process (for testing)"
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay in seconds between repositories (default: 0.5)"
    )

    args = parser.parse_args()

    # Get GitHub token
    token = get_github_token()
    if not token:
        print("❌ Error: No GitHub token found")
        print("   Set GITHUB_TOKEN environment variable or create .env file")
        sys.exit(1)

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    # Load repositories
    if not args.input.exists():
        print(f"❌ Error: Input file '{args.input}' not found")
        sys.exit(1)

    print(f"\n📂 Loading repositories from {args.input}...")
    repositories = load_repositories(args.input)
    print(f"✓ Loaded {len(repositories)} repositories")

    # Initialize output files
    initialize_csv_files(args.output, args.no_releases_file)

    # Load already processed repos
    print("\n🔍 Checking for already processed repositories...")
    processed_repos = load_processed_repos(args.output, args.no_releases_file)
    print(f"✓ Found {len(processed_repos)} already processed")

    # Filter repositories
    repos_to_process = [r for r in repositories if r['full_name'] not in processed_repos]

    if args.limit:
        repos_to_process = repos_to_process[:args.limit]

    if not repos_to_process:
        print("\n✅ All repositories already processed!")
        sys.exit(0)

    print(f"\n📥 Processing {len(repos_to_process)} repositories...\n")

    # Process repositories
    stats = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_processed": 0,
        "repos_with_releases": 0,
        "repos_with_tags_only": 0,
        "repos_with_nothing": 0,
        "total_releases_fetched": 0,
    }

    try:
        for i, repo in enumerate(repos_to_process, 1):
            print(f"[{i}/{len(repos_to_process)}] ", end="")

            try:
                count, status = process_repository(
                    repo,
                    headers,
                    args.output,
                    args.no_releases_file
                )

                stats["total_processed"] += 1
                stats["total_releases_fetched"] += count

                if status == "releases":
                    stats["repos_with_releases"] += 1
                elif status == "tags":
                    stats["repos_with_tags_only"] += 1
                else:
                    stats["repos_with_nothing"] += 1

                # Update progress
                stats["last_processed"] = repo['full_name']
                stats["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                save_progress(args.progress_file, stats)

                # Small delay between repos
                if i < len(repos_to_process):
                    time.sleep(args.delay)

            except Exception as e:
                print(f"❌ Error: {e}")
                # Save progress and continue
                save_progress(args.progress_file, stats)
                continue

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        save_progress(args.progress_file, stats)
        sys.exit(1)

    # Final summary
    print("\n📊 Summary:")
    print(f"   Total processed: {stats['total_processed']}")
    print(f"   Repos with releases: {stats['repos_with_releases']}")
    print(f"   Repos with tags only: {stats['repos_with_tags_only']}")
    print(f"   Repos with nothing: {stats['repos_with_nothing']}")
    print(f"   Total releases/tags fetched: {stats['total_releases_fetched']}")
    print(f"\n✅ Releases saved to: {args.output}")
    print(f"✅ No-releases log: {args.no_releases_file}")
    print(f"✅ Progress file: {args.progress_file}")


if __name__ == "__main__":
    main()
