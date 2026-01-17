#!/usr/bin/env python3
"""
Simple CLI tool for testing the version parser on real data (no external dependencies).

Usage:
    # Test random sample
    python src/test_parser_simple.py --random 20

    # Test specific lines
    python src/test_parser_simple.py --lines 1,5,10,100
"""

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import List
from parse_versions import parse_version, VersionInfo


def load_csv_lines(csv_path: Path, line_numbers: List[int] = None) -> List[dict]:
    """Load specific lines from CSV file."""
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            if line_numbers is None or i in line_numbers:
                rows.append({**row, '_line_num': i})
                if line_numbers and len(rows) == len(line_numbers):
                    break
    return rows


def load_random_lines(csv_path: Path, count: int) -> List[dict]:
    """Load random lines from CSV file."""
    # First count total lines
    with open(csv_path, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for _ in f) - 1  # Subtract header

    # Generate random line numbers
    line_numbers = sorted(random.sample(range(1, total_lines + 1), min(count, total_lines)))

    return load_csv_lines(csv_path, line_numbers)


def display_parse_result(row: dict, info: VersionInfo, show_details: bool = True):
    """Display a single parse result in a simple format."""
    release_name = row.get('release_name', '')
    tag_name = row.get('tag_name', '')
    repo_name = row.get('repo_name', '')
    line_num = row.get('_line_num', '?')

    # Status indicator
    status = '✓' if info.parseable else '✗'

    # Header
    print(f"\n{'='*80}")
    print(f"Line {line_num} | {repo_name}")
    print(f"{'='*80}")

    # Input
    print(f"\nINPUT:")
    print(f"  Release Name: {release_name or '(empty)'}")
    print(f"  Tag Name:     {tag_name or '(empty)'}")

    # Parsed result
    print(f"\nPARSED RESULT: {status}")
    print(f"  Scheme:    {info.version_scheme}")
    print(f"  Parseable: {info.parseable}")

    if show_details and info.parseable:
        print(f"\nDETAILS:")

        # Version components
        if info.major_version is not None:
            print(f"  Version: {info.major_version}.{info.minor_version}.{info.patch_version}")

        # CalVer
        if info.year is not None:
            print(f"  Date:    {info.year}-{info.month:02d}")

        # Metadata
        if info.version_prefix:
            print(f"  Prefix:  {info.version_prefix}")

        if info.prerelease_tag:
            prerelease = info.prerelease_tag
            if info.prerelease_number is not None:
                prerelease += f".{info.prerelease_number}"
            print(f"  Pre-rel: {prerelease}")

        if info.build_metadata:
            print(f"  Build:   {info.build_metadata}")

        if info.is_dev_build:
            print(f"  Dev:     Yes")

        if info.package_name:
            print(f"  Package: {info.package_name}")

        if info.product_name:
            print(f"  Product: {info.product_name}")


def generate_stats(results: List[tuple[dict, VersionInfo]]):
    """Generate and display statistics."""
    total = len(results)
    if total == 0:
        return

    # Count by scheme
    scheme_counts = {}
    parseable_count = 0

    for _, info in results:
        scheme_counts[info.version_scheme] = scheme_counts.get(info.version_scheme, 0) + 1
        if info.parseable:
            parseable_count += 1

    # Display stats
    print(f"\n{'='*80}")
    print("STATISTICS")
    print(f"{'='*80}")
    print(f"\nTotal Samples:  {total}")
    print(f"Parseable:      {parseable_count} ({parseable_count/total*100:.1f}%)")
    print(f"Unparseable:    {total - parseable_count} ({(total-parseable_count)/total*100:.1f}%)")

    # Scheme breakdown
    print(f"\nVERSION SCHEME BREAKDOWN:")
    for scheme, count in sorted(scheme_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = f"{count/total*100:.1f}%"
        print(f"  {scheme:20} {count:5} ({percentage})")


def main():
    parser = argparse.ArgumentParser(
        description="Test version parser on real release data"
    )

    parser.add_argument(
        '--csv',
        type=Path,
        default=Path('data/releases.csv'),
        help='Path to releases CSV file (default: data/releases.csv)'
    )

    # Selection mode
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--random',
        type=int,
        metavar='N',
        help='Test N random samples'
    )
    group.add_argument(
        '--lines',
        type=str,
        metavar='LINES',
        help='Test specific line numbers (comma-separated, e.g., 1,5,10)'
    )

    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Only show statistics, not individual results'
    )

    args = parser.parse_args()

    # Check CSV exists
    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)

    # Load data
    print(f"Loading data from {args.csv}...")

    if args.random:
        rows = load_random_lines(args.csv, args.random)
    elif args.lines:
        line_numbers = [int(x.strip()) for x in args.lines.split(',')]
        rows = load_csv_lines(args.csv, line_numbers)

    print(f"Loaded {len(rows)} rows")

    # Parse all and collect results
    results = []
    for row in rows:
        release_name = row.get('release_name', '')
        tag_name = row.get('tag_name', '')
        info = parse_version(release_name, tag_name)
        results.append((row, info))

    # Display results
    if not args.stats_only:
        for row, info in results:
            display_parse_result(row, info)

    # Show statistics
    generate_stats(results)


if __name__ == '__main__':
    main()
