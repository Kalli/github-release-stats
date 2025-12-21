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

## Storage Options

### Option 1: SQLite Database (Recommended for Analysis)

**Advantages**:
- SQL queries for complex analysis
- Efficient indexing for date range queries
- Built-in aggregation functions
- Portable single file
- No external dependencies

**Schema**:
```sql
CREATE TABLE repositories (
    id INTEGER PRIMARY KEY,
    github_id INTEGER UNIQUE,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    full_name TEXT UNIQUE NOT NULL,
    stars INTEGER,
    created_at TEXT,
    language TEXT,
    topics TEXT,
    fetched_at TEXT,
    INDEX idx_stars (stars DESC)
);

CREATE TABLE releases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_full_name TEXT NOT NULL,
    github_release_id INTEGER,
    tag_name TEXT NOT NULL,
    release_name TEXT,
    published_at TEXT NOT NULL,
    is_prerelease BOOLEAN,
    is_draft BOOLEAN,
    semver_compliant BOOLEAN,
    major_version INTEGER,
    minor_version INTEGER,
    patch_version INTEGER,
    prerelease_tag TEXT,
    version_type TEXT,
    changelog_snippet TEXT,
    source TEXT,
    FOREIGN KEY (repo_full_name) REFERENCES repositories(full_name),
    INDEX idx_published_at (published_at),
    INDEX idx_repo (repo_full_name),
    INDEX idx_version_type (version_type)
);
```

### Option 2: JSON Files

**Structure**:
- `data/repositories.json` - Array of all repositories
- `data/releases/{owner}/{repo}.json` - Releases per repository

**Advantages**:
- Human readable
- Easy to version control
- No database setup

**Disadvantages**:
- Slower queries
- Need to load entire files for analysis

### Option 3: CSV Files

**Files**:
- `repositories.csv`
- `releases.csv`

**Advantages**:
- Easy to import into spreadsheets/Pandas
- Simple format

**Disadvantages**:
- Handling nested data (topics, changelog)
- Slower queries than SQL

## Implementation Steps

1. **Setup**:
   - Create GitHub Personal Access Token (for authentication)
   - Choose storage format (recommend SQLite)
   - Setup rate limiting handling
   - Setup error logging

2. **Fetch Top Repositories**:
   - Paginate through search results
   - Store repository metadata
   - Handle API errors and retries

3. **Fetch Releases for Each Repository**:
   - Try releases endpoint first
   - Fallback to tags if no releases
   - Parse and store release data
   - Respect rate limits (add delays if needed)

4. **Parse Versions**:
   - Extract semver components
   - Classify version changes
   - Flag non-compliant versions

5. **Data Quality**:
   - Log repositories with no releases
   - Track parsing failures
   - Store raw tag_name for manual review

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

## Timeline Estimate

- Setup and initial code: 2-4 hours
- Fetching repositories: ~10 minutes (with rate limits)
- Fetching releases: 1-3 hours (with rate limits, ~2-5 requests/second)
- Data parsing and storage: Concurrent with fetching
- **Total data collection time: 2-4 hours**

## Recommended Tech Stack

- **Language**: Python or Node.js
- **HTTP Client**: `requests` (Python) or `octokit` (Node.js)
- **Database**: SQLite with `sqlite3` module
- **Version Parsing**: `semver` library
- **Rate Limiting**: Built-in retry logic with exponential backoff

## Notes

- Filter out draft releases from analysis
- Consider filtering out pre-releases (or analyze separately)
- Some repos might have 100+ releases (need pagination)
- Some repos might have no formal releases (tags only)
- Version naming conventions vary widely (v1.0.0, 1.0.0, release-1.0.0, etc.)
