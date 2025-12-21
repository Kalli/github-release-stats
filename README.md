# GitHub Release Stats

A research project to analyze release cadence patterns in the top 1000 most starred GitHub repositories.

## Project Aim

This project investigates whether software release cadence has accelerated following two significant dates in the tech industry:

1. **November 30, 2022** - The release of ChatGPT and the beginning of widespread AI-assisted development
2. **February 24, 2025** - [Future analysis date]

By collecting and analyzing release metadata from the most popular open-source repositories, we aim to understand:

- Has the average time between releases decreased?
- Are major/minor/patch releases happening more frequently?
- Do different types of projects show different patterns?
- Is there a correlation between AI tool adoption and release velocity?

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

See [PLAN.md](PLAN.md) for detailed implementation steps and API documentation.

## Research Context

This project was inspired by anecdotal evidence from developers reporting increased shipping velocity after adopting AI coding assistants. By analyzing real-world release data from the most popular open-source projects, we aim to provide empirical evidence to support or refute these observations.
