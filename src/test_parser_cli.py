#!/usr/bin/env python3
"""
CLI tool for testing the version parser on real data.

Usage:
    # Test random sample
    python src/test_parser_cli.py --random 20

    # Test specific lines
    python src/test_parser_cli.py --lines 1,5,10,100

    # Test a range of lines
    python src/test_parser_cli.py --range 100:200

    # Filter by scheme
    python src/test_parser_cli.py --random 50 --scheme semver
"""

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from parse_versions import parse_version, VersionInfo


console = Console()


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


def format_version_info(info: VersionInfo) -> Table:
    """Format VersionInfo as a rich table."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="yellow")

    # Classification
    table.add_row("Scheme", info.version_scheme)
    table.add_row("Parseable", "✓" if info.parseable else "✗")

    # Version components
    if info.major_version is not None:
        table.add_row("Version", f"{info.major_version}.{info.minor_version}.{info.patch_version}")

    # CalVer
    if info.year is not None:
        table.add_row("Date", f"{info.year}-{info.month:02d}")

    # Metadata
    if info.version_prefix:
        table.add_row("Prefix", info.version_prefix)

    if info.prerelease_tag:
        prerelease = info.prerelease_tag
        if info.prerelease_number is not None:
            prerelease += f".{info.prerelease_number}"
        table.add_row("Prerelease", prerelease)

    if info.build_metadata:
        table.add_row("Build", info.build_metadata)

    if info.is_dev_build:
        table.add_row("Dev Build", "✓")

    if info.package_name:
        table.add_row("Package", info.package_name)

    if info.product_name:
        table.add_row("Product", info.product_name)

    if info.raw_version:
        table.add_row("Raw Version", info.raw_version)

    return table


def display_parse_result(row: dict, show_full: bool = False):
    """Display a single parse result in a nice format."""
    release_name = row.get('release_name', '')
    tag_name = row.get('tag_name', '')
    repo_name = row.get('repo_name', '')
    line_num = row.get('_line_num', '?')

    # Parse the version
    info = parse_version(release_name, tag_name)

    # Create header
    header = f"Line {line_num}"
    if repo_name:
        header += f" | {repo_name}"

    # Color based on parseability
    border_style = "green" if info.parseable else "red"

    # Build content
    content = f"[bold]Input:[/bold]\n"
    content += f"  Release Name: {release_name or '[dim](empty)[/dim]'}\n"
    content += f"  Tag Name:     {tag_name or '[dim](empty)[/dim]'}\n\n"

    # Add full row data if requested
    if show_full:
        content += f"[bold]Full Row:[/bold]\n"
        for key, value in row.items():
            if not key.startswith('_'):
                content += f"  {key}: {value}\n"
        content += "\n"

    content += f"[bold]Parsed Result:[/bold]\n"

    # Display panel with table
    console.print(Panel(content, title=header, border_style=border_style))
    console.print(format_version_info(info))
    console.print()


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

    # Create stats table
    table = Table(title="Parsing Statistics", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow", justify="right")

    table.add_row("Total Samples", str(total))
    table.add_row("Parseable", f"{parseable_count} ({parseable_count/total*100:.1f}%)")
    table.add_row("Unparseable", f"{total - parseable_count} ({(total-parseable_count)/total*100:.1f}%)")

    console.print()
    console.print(table)

    # Scheme breakdown
    scheme_table = Table(title="Version Scheme Breakdown", show_header=True)
    scheme_table.add_column("Scheme", style="cyan")
    scheme_table.add_column("Count", style="yellow", justify="right")
    scheme_table.add_column("Percentage", style="yellow", justify="right")

    for scheme, count in sorted(scheme_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = f"{count/total*100:.1f}%"
        scheme_table.add_row(scheme, str(count), percentage)

    console.print()
    console.print(scheme_table)


def main():
    parser = argparse.ArgumentParser(
        description="Test version parser on real release data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --random 20
  %(prog)s --lines 1,5,10,100
  %(prog)s --range 100:200
  %(prog)s --random 50 --scheme semver
        """
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
    group.add_argument(
        '--range',
        type=str,
        metavar='START:END',
        help='Test a range of lines (e.g., 100:200)'
    )

    parser.add_argument(
        '--scheme',
        type=str,
        choices=['semver', 'calver', 'package_scoped', 'product_named', 'dev_build', 'descriptive', 'unknown'],
        help='Filter by version scheme'
    )

    parser.add_argument(
        '--full',
        action='store_true',
        help='Show full row data for each sample'
    )

    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Only show statistics, not individual results'
    )

    args = parser.parse_args()

    # Check CSV exists
    if not args.csv.exists():
        console.print(f"[red]Error: CSV file not found: {args.csv}[/red]")
        sys.exit(1)

    # Load data
    console.print(f"[cyan]Loading data from {args.csv}...[/cyan]")

    if args.random:
        rows = load_random_lines(args.csv, args.random)
    elif args.lines:
        line_numbers = [int(x.strip()) for x in args.lines.split(',')]
        rows = load_csv_lines(args.csv, line_numbers)
    elif args.range:
        start, end = args.range.split(':')
        line_numbers = list(range(int(start), int(end) + 1))
        rows = load_csv_lines(args.csv, line_numbers)

    console.print(f"[green]Loaded {len(rows)} rows[/green]\n")

    # Parse all and collect results
    results = []
    for row in rows:
        release_name = row.get('release_name', '')
        tag_name = row.get('tag_name', '')
        info = parse_version(release_name, tag_name)
        results.append((row, info))

    # Filter by scheme if requested
    if args.scheme:
        results = [(row, info) for row, info in results if info.version_scheme == args.scheme]
        console.print(f"[yellow]Filtered to {len(results)} rows with scheme '{args.scheme}'[/yellow]\n")

    # Display results
    if not args.stats_only:
        for row, info in results:
            # Re-add info to row for display function
            display_parse_result(row, show_full=args.full)

    # Show statistics
    generate_stats(results)


if __name__ == '__main__':
    main()
