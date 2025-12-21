# GitHub Release Metadata Fetching Plan

## Objective
Fetch release metadata for the top 1000 most starred GitHub repositories to analyze whether release cadence has accelerated after:
1. November 30, 2022
2. February 24, 2025

## Data Collection Strategy

### Step 1: Fetch Top 1000 Most Starred Repositories

**Endpoint**: `GET /search/repositories`

**Query Parameters**:
- `q=stars:>1` (or more specific threshold)
- `sort=stars`
- `order=desc`
- `per_page=100` (max allowed)
- `page=1` through `page=10` (to get 1000 repos)

**Data to Extract per Repository**:
- `owner/login` - Repository owner
- `name` - Repository name
- `full_name` - Full repository name (owner/repo)
- `stargazers_count` - Number of stars
- `created_at` - Repository creation date
- `language` - Primary programming language
- `topics` - Repository topics/tags

**Rate Limiting**:
- Authenticated requests: 5,000 requests/hour
- Search API: 30 requests/minute
- Need ~10 requests for repository search

### Step 2: Fetch Release Data for Each Repository

**Primary Endpoint**: `GET /repos/{owner}/{repo}/releases`

**Query Parameters**:
- `per_page=100` (max allowed)
- `page=1, 2, 3...` (paginate through all releases)

**Data to Extract per Release**:
- `id` - Release ID
- `tag_name` - Version tag (e.g., "v1.2.3", "1.2.3")
- `name` - Release name/title
- `published_at` - Release publication date
- `created_at` - Release creation date
- `prerelease` - Boolean flag for pre-releases
- `draft` - Boolean flag for drafts
- `body` - Release notes/changelog (optional, can be large)

**Fallback Endpoint**: `GET /repos/{owner}/{repo}/tags`

Some repositories use tags instead of formal releases:
- `name` - Tag name
- `commit.sha` - Commit hash
- `commit.url` - URL to get commit details

**For tags, fetch commit details**: `GET /repos/{owner}/{repo}/commits/{sha}`
- `commit.author.date` - Commit date (use as release date)

**Rate Limiting Consideration**:
- Need 1 request per repository minimum (1000 requests)
- Additional requests for pagination if > 100 releases
- Additional requests for commit details if using tags
- Estimated total: 2,000-5,000 requests

### Step 3: Parse Semantic Versioning

**Semantic Version Regex**:
```regex
^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$
```

**Parsing Logic**:
- Extract major, minor, patch from version string
- Handle common prefixes: `v`, `release-`, `version-`
- Detect version type changes:
  - Major: X.0.0 (X changes)
  - Minor: X.Y.0 (Y changes, X same)
  - Patch: X.Y.Z (Z changes, X.Y same)
- Flag non-semver releases for separate analysis

**Version Classification**:
- `semver_compliant`: boolean
- `major_version`: integer
- `minor_version`: integer
- `patch_version`: integer
- `prerelease`: string (alpha, beta, rc, etc.)
- `build_metadata`: string

## Data Schema

### Repository Table/Collection

```json
{
  "id": "github_repo_id",
  "owner": "owner_name",
  "name": "repo_name",
  "full_name": "owner/repo",
  "stars": 12345,
  "created_at": "2020-01-01T00:00:00Z",
  "language": "JavaScript",
  "topics": ["react", "frontend"],
  "fetched_at": "2025-12-21T00:00:00Z"
}
```

### Release Table/Collection

```json
{
  "id": "unique_release_id",
  "repo_full_name": "owner/repo",
  "release_id": "github_release_id",
  "tag_name": "v1.2.3",
  "release_name": "Version 1.2.3",
  "published_at": "2023-06-15T10:30:00Z",
  "is_prerelease": false,
  "is_draft": false,
  "semver_compliant": true,
  "major_version": 1,
  "minor_version": 2,
  "patch_version": 3,
  "prerelease_tag": null,
  "version_type": "patch",
  "changelog_snippet": "First 500 chars of release notes",
  "source": "release"
}
```

## Storage Format

### CSV Files (Primary Storage)

**Files**:
- `data/repositories.csv`
- `data/releases.csv`

**Advantages**:
- Easy to import into Pandas for Jupyter notebook analysis
- Simple format, human readable
- Can be version controlled
- No database setup required

**Handling Nested Data**:
- Store nested fields (topics, etc.) as JSON strings within CSV cells
- Example: `topics` column contains `["react", "frontend", "typescript"]`
- Easy to parse in Python with `json.loads()`

**CSV Schema**:

`repositories.csv`:
```
github_id,owner,name,full_name,stars,created_at,language,topics,fetched_at
12345,facebook,react,facebook/react,180000,2013-05-24T00:00:00Z,JavaScript,"[""react"",""frontend""]",2025-12-21T00:00:00Z
```

`releases.csv`:
```
repo_full_name,github_release_id,tag_name,release_name,published_at,is_prerelease,is_draft,semver_compliant,major_version,minor_version,patch_version,prerelease_tag,version_type,changelog_snippet,source
facebook/react,12345,v18.2.0,React 18.2.0,2023-06-15T10:30:00Z,false,false,true,18,2,0,,minor,First 500 chars...,release
```

### Future Migration to SQLite

CSV files can be easily imported into SQLite later for more complex queries:
- Use Pandas `df.to_sql()` for import
- Or write a simple conversion script
- Enables efficient date range queries and aggregations

## Implementation Plan

- [ ] **Project Setup**
  - [ ] Initialize Python project with `uv`
  - [ ] Add dependencies (httpx/requests, pandas, semver)
  - [ ] Create project structure (src/, data/, notebooks/)
  - [ ] Setup .gitignore for data files and credentials

- [ ] **GitHub API Client**
  - [ ] Create GitHub API client with authentication
  - [ ] Implement rate limiting with exponential backoff
  - [ ] Add retry logic for failed requests
  - [ ] Setup error logging

- [ ] **Repository Fetcher**
  - [ ] Implement search API pagination (10 pages × 100 repos)
  - [ ] Extract and store repository metadata
  - [ ] Save to `data/repositories.csv`
  - [ ] Handle API errors gracefully

- [ ] **Release Fetcher**
  - [ ] Implement releases endpoint fetcher with pagination
  - [ ] Implement tags endpoint as fallback
  - [ ] Fetch commit dates for tags
  - [ ] Save to `data/releases.csv`
  - [ ] Add progress tracking for 1000 repos

- [ ] **Semantic Version Parser**
  - [ ] Create regex-based semver parser
  - [ ] Handle common version prefixes (v, release-, etc.)
  - [ ] Extract major, minor, patch components
  - [ ] Classify version bump types
  - [ ] Flag non-semver versions

- [ ] **Data Quality & Validation**
  - [ ] Log repositories with no releases/tags
  - [ ] Track semver parsing failures
  - [ ] Validate data completeness
  - [ ] Create summary statistics

- [ ] **Analysis Setup**
  - [ ] Create Jupyter notebook for exploratory analysis
  - [ ] Add helper functions for loading CSV data
  - [ ] Create visualization templates
  - [ ] (Optional) Add SQLite import script for complex queries

## Analysis Queries (Examples)

Once data is collected, example queries:

```sql
-- Average releases per month before/after Nov 30, 2022
SELECT
    CASE
        WHEN published_at < '2022-11-30' THEN 'Before ChatGPT'
        ELSE 'After ChatGPT'
    END as period,
    COUNT(*) / COUNT(DISTINCT repo_full_name) /
        ((julianday('2025-12-21') - julianday(MIN(published_at))) / 30.0) as avg_releases_per_month
FROM releases
WHERE is_draft = 0 AND is_prerelease = 0
GROUP BY period;

-- Release type distribution before/after
SELECT
    version_type,
    CASE
        WHEN published_at < '2022-11-30' THEN 'Before'
        ELSE 'After'
    END as period,
    COUNT(*) as count
FROM releases
WHERE semver_compliant = 1
GROUP BY version_type, period;
```


## Tech Stack

- **Language**: Python 3.11+
- **Package Manager**: `uv` for fast dependency management
- **HTTP Client**: `httpx` (async support) or `requests`
- **Data Processing**: `pandas` for CSV handling and analysis
- **Version Parsing**: `semver` library or custom regex
- **Rate Limiting**: Built-in retry logic with exponential backoff
- **Analysis**: Jupyter notebooks for exploratory data analysis

## Notes

- Filter out draft releases from analysis
- Consider filtering out pre-releases (or analyze separately)
- Some repos might have 100+ releases (need pagination)
- Some repos might have no formal releases (tags only)
- Version naming conventions vary widely (v1.0.0, 1.0.0, release-1.0.0, etc.)
