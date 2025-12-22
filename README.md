# GitHub Release Stats

A research project to analyze release cadence patterns in the top 1000 most starred GitHub repositories.

## Project Aim

This project investigates whether software release cadence has accelerated following two significant dates in the tech industry:

1. **November 30, 2022** - The release of ChatGPT
2. **February 24, 2025** - Claude Code Released

By collecting and analyzing release metadata from the most popular open-source repositories, we aim to understand:

- Has the average time between releases decreased?
- Are major/minor/patch releases happening more frequently?
- Do different types of projects show different patterns?

## Methodology

### Data Collection

We collect release metadata from the **top 1000 most starred GitHub repositories** using the GitHub REST API:

- Repository metadata (stars, language, topics)
- Release information (versions, dates, changelogs)
- Semantic versioning analysis (major/minor/patch classification)

### Data Storage

Data is stored in CSV format for easy analysis in Jupyter notebooks:
- `data/repositories.csv` - Repository metadata
- `data/releases.csv` - Release information with parsed version data

### Analysis Approach

Using Python and Pandas, we will analyze:
- Release frequency trends over time
- Distribution of version bump types (major vs minor vs patch)
- Correlation between project characteristics and release patterns
- Statistical significance of changes around key dates

## Key Questions

- Are projects releasing more frequently after ChatGPT's launch?
- Has the ratio of major:minor:patch releases changed?
- Do AI-native tools show different patterns than traditional projects?
- Which programming languages/ecosystems show the most change?

## Project Structure

```
github-release-stats/
├── data/               # CSV files with collected data
├── src/                # Python modules for data collection
├── notebooks/          # Jupyter notebooks for analysis
├── PLAN.md            # Detailed implementation plan
└── README.md          # This file
```

## Tech Stack

- **Python 3.11+** - Primary language
- **uv** - Fast Python package manager
- **pandas** - Data manipulation and analysis
- **httpx/requests** - GitHub API interaction
- **Jupyter** - Interactive data analysis

## Getting Started

### Prerequisites

1. **Python 3.11+** installed on your system
2. **uv** package manager ([installation guide](https://github.com/astral-sh/uv))
3. **GitHub Personal Access Token** for API access

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd github-release-stats
```

2. Install dependencies using uv:
```bash
uv sync
```

3. Create a GitHub Personal Access Token:
   - Go to https://github.com/settings/tokens
   - Create a new token with `public_repo` scope
   - Copy the token

4. Set up your environment:
```bash
cp .env.example .env
# Edit .env and add your GitHub token
```

### Usage

#### Fetch Top Repositories

Fetch the top 1000 most starred GitHub repositories:

```bash
# Basic usage (with token in .env or GITHUB_TOKEN environment variable)
uv run python src/fetch_repositories.py

# Or export token directly
export GITHUB_TOKEN=your_token_here
uv run python src/fetch_repositories.py

# Custom output file
uv run python src/fetch_repositories.py -o custom_repos.csv

# Fetch different number of repos
uv run python src/fetch_repositories.py -n 500

# Force overwrite without prompting
uv run python src/fetch_repositories.py --force
```

**Options:**
- `-o, --output FILE` - Output CSV file (default: `data/repositories.csv`)
- `-n, --number N` - Number of repositories to fetch (default: 1000)
- `--force` - Force overwrite without prompting

**Output:**
The script creates a CSV file with the following columns:
- `github_id` - GitHub repository ID
- `owner` - Repository owner
- `name` - Repository name
- `full_name` - Full name (owner/repo)
- `stars` - Number of stars
- `created_at` - Repository creation date
- `language` - Primary programming language
- `topics` - Repository topics (JSON array)
- `fetched_at` - Timestamp of data collection

For more details, see [PLAN.md](PLAN.md).

## Research Context

This project was inspired by anecdotal evidence from developers reporting increased shipping velocity after adopting AI coding assistants. By analyzing real-world release data from the most popular open-source projects, we aim to inspect empirical evidence for such observations.
