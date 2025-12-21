#!/usr/bin/env python3
"""
Fetch top starred GitHub repositories and save to CSV.

This script fetches the top 1000 most starred GitHub repositories using the
GitHub Search API and saves the results to a CSV file.
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


# Constants
DEFAULT_OUTPUT_FILE = "data/repositories.csv"
REPOS_PER_PAGE = 100
TOTAL_REPOS = 1000
GITHUB_API_BASE = "https://api.github.com"
SEARCH_ENDPOINT = f"{GITHUB_API_BASE}/search/repositories"


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


def check_overwrite(file_path: Path) -> bool:
    """
    Check if file exists and prompt user for overwrite confirmation.

    Args:
        file_path: Path to the file to check

    Returns:
        True if should proceed (file doesn't exist or user confirmed), False otherwise
    """
    if not file_path.exists():
        return True

    print(f"⚠️  File '{file_path}' already exists.")
    response = input("Do you want to overwrite it? [y/N]: ").strip().lower()
    return response in ('y', 'yes')


def fetch_repositories_page(
    page: int,
    per_page: int = REPOS_PER_PAGE,
    token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch a single page of top starred repositories.

    Args:
        page: Page number (1-indexed)
        per_page: Number of repositories per page
        token: GitHub API token for authentication

    Returns:
        API response as dictionary

    Raises:
        requests.RequestException: If the request fails
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
    }

    if token:
        headers["Authorization"] = f"token {token}"

    params = {
        "q": "stars:>1",
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": page,
    }

    print(f"Fetching page {page}... ", end="", flush=True)

    response = requests.get(SEARCH_ENDPOINT, headers=headers, params=params)
    response.raise_for_status()

    # Check rate limiting
    remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))

    print(f"✓ (Rate limit: {remaining} remaining)")

    if remaining < 5:
        wait_time = reset_time - time.time()
        if wait_time > 0:
            print(f"⏳ Rate limit low, waiting {int(wait_time)} seconds...")
            time.sleep(wait_time + 1)

    return response.json()


def extract_repository_data(repo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relevant fields from a repository object.

    Args:
        repo: Repository object from GitHub API

    Returns:
        Dictionary with extracted fields
    """
    return {
        "github_id": repo["id"],
        "owner": repo["owner"]["login"],
        "name": repo["name"],
        "full_name": repo["full_name"],
        "stars": repo["stargazers_count"],
        "created_at": repo["created_at"],
        "language": repo["language"] or "",
        "topics": json.dumps(repo.get("topics", [])),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def fetch_all_repositories(
    total: int = TOTAL_REPOS,
    per_page: int = REPOS_PER_PAGE,
    token: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch all top starred repositories.

    Args:
        total: Total number of repositories to fetch
        per_page: Repositories per page
        token: GitHub API token

    Returns:
        List of repository data dictionaries
    """
    repositories = []
    total_pages = (total + per_page - 1) // per_page  # Ceiling division

    print(f"\n📥 Fetching top {total} starred repositories ({total_pages} pages)\n")

    for page in range(1, total_pages + 1):
        try:
            data = fetch_repositories_page(page, per_page, token)

            if "items" not in data:
                print(f"❌ Error: No 'items' in response")
                break

            for repo in data["items"]:
                repositories.append(extract_repository_data(repo))

                if len(repositories) >= total:
                    break

            if len(repositories) >= total:
                break

            # Be nice to the API - add a small delay between requests
            if page < total_pages:
                time.sleep(1)

        except requests.RequestException as e:
            print(f"\n❌ Error fetching page {page}: {e}")
            if repositories:
                print(f"⚠️  Partial data available ({len(repositories)} repos)")
                break
            else:
                raise

    return repositories[:total]


def save_to_csv(repositories: List[Dict[str, Any]], output_file: Path) -> None:
    """
    Save repository data to CSV file.

    Args:
        repositories: List of repository dictionaries
        output_file: Path to output CSV file
    """
    if not repositories:
        print("❌ No data to save")
        return

    # Ensure directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write CSV
    fieldnames = [
        "github_id",
        "owner",
        "name",
        "full_name",
        "stars",
        "created_at",
        "language",
        "topics",
        "fetched_at",
    ]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(repositories)

    print(f"\n✅ Saved {len(repositories)} repositories to {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch top starred GitHub repositories and save to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch with token from environment
  export GITHUB_TOKEN=your_token_here
  python src/fetch_repositories.py

  # Fetch to custom output file
  python src/fetch_repositories.py -o my_repos.csv

  # Fetch different number of repos
  python src/fetch_repositories.py -n 500
        """
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT_FILE),
        help=f"Output CSV file (default: {DEFAULT_OUTPUT_FILE})"
    )

    parser.add_argument(
        "-n", "--number",
        type=int,
        default=TOTAL_REPOS,
        help=f"Number of repositories to fetch (default: {TOTAL_REPOS})"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite without prompting"
    )

    args = parser.parse_args()

    # Check for overwrite
    if not args.force and not check_overwrite(args.output):
        print("❌ Aborted")
        sys.exit(0)

    # Get GitHub token
    token = get_github_token()
    if not token:
        print("⚠️  Warning: No GitHub token found. Rate limits will be lower.")
        print("   Set GITHUB_TOKEN environment variable or create .env file")
        print("   Unauthenticated: 60 requests/hour")
        print("   Authenticated: 5,000 requests/hour")
        print()

        response = input("Continue without token? [y/N]: ").strip().lower()
        if response not in ('y', 'yes'):
            print("❌ Aborted")
            sys.exit(0)

    try:
        # Fetch repositories
        repositories = fetch_all_repositories(
            total=args.number,
            token=token
        )

        # Save to CSV
        save_to_csv(repositories, args.output)

        # Print summary
        print("\n📊 Summary:")
        print(f"   Total repositories: {len(repositories)}")
        if repositories:
            print(f"   Top repo: {repositories[0]['full_name']} ({repositories[0]['stars']:,} stars)")

            # Language distribution
            languages = {}
            for repo in repositories:
                lang = repo['language'] or 'Unknown'
                languages[lang] = languages.get(lang, 0) + 1

            print(f"   Languages: {len(languages)} different")
            top_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]
            for lang, count in top_langs:
                print(f"     - {lang}: {count}")

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
