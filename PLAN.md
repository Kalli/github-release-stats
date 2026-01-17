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

### Step 3: Parse Semantic Versioning and Version Schemes

After analyzing the `data/releases.csv` (~171K releases), we've identified diverse versioning patterns that need categorization and parsing strategies.

#### Observed Versioning Patterns

1. **Empty Release Names** (~46K releases)
   - These rely solely on `tag_name` for version identification
   - Strategy: Parse `tag_name` instead of `release_name`

2. **Semantic Versioning (SemVer)** - Most common
   - Standard: `1.0.0`, `v2.3.1`, `v16.8.6`
   - With pre-release: `v16.9.0-alpha.0`, `v16.9.0-rc.0`, `3.1.0-rc.8`, `4.17.0-alpha.1`
   - With build metadata: `1.0.0+20130313144700`
   - Variants: `0.15.0-beta.12`, `10.2.0-beta.5`

3. **Calendar Versioning (CalVer)**
   - Year.Month: `2025.12.0`, `2020.10`
   - Year.Month.Patch: `2025.12.5`
   - With beta: `2026.1.0b2`, `2025.12.0b9`
   - Date format: `2025-05-21`, `October 2022`
   - Weekly: `weekly.2024.22`
   - Extended: `22000.348.40.7` (possibly build numbers)

4. **Package-Scoped Versions**
   - NPM-style: `@gradio/chatbot@0.26.16`, `@astrojs/react@2.3.2`, `@pankod/refine-core@3.76.0`
   - Python-style: `langchain-community==0.3.1`
   - Product prefix: `eslint-plugin-react-hooks@5.0.0`

5. **Product-Named Releases**
   - Format: `ProductName vX.Y.Z`
   - Examples: `Bun v1.1.39`, `Hyperswitch v1.18.0`, `Ventoy 1.0.67 release`
   - With separator: `puppeteer: v19.7.1`, `electron v23.3.7`

6. **Development Builds**
   - Nightly: `Nightly build 2026.01.03`, `v7.0.1-nightly.20230405`
   - Canary: `v13.2.5-canary.32`, `Turborepo v2.7.5-canary.2`
   - Dev: `v1.68.1.dev2`, `v1.77.7.dev10`
   - Snapshot: `snapshot-2023-11-12`

7. **Descriptive/Named Releases**
   - Generic: `Bugfix Release`, `Minor Bug Fix Release`, `Major Feature Release`
   - Specific: `Better traceback formatting`, `Support for unicode letters.`
   - With version: `Release v1.6.2`, `Release 1.3.2`
   - Product releases: `Brackets 1.13`, `Metabase 0.23.0`, `Elasticsearch 6.8.23`

8. **Non-Standard Formats**
   - Build numbers only: `b6119`
   - Milestone: `Kotlin M7`
   - Simple major: `4.0`, `Roadmap 4.0`

#### Parsing Strategy

**Phase 1: Version Scheme Detection**

Use a waterfall approach to classify each release into one of these categories:

```python
1. Check if release_name is empty → use tag_name
2. Try SemVer parsing (strictest)
3. Try CalVer detection (date patterns)
4. Try package-scoped extraction (@package@version, package==version)
5. Try product-named extraction (ProductName vX.Y.Z)
6. Try development build detection (nightly, canary, dev, snapshot)
7. Try "Release vX.Y.Z" pattern extraction
8. Flag as descriptive/non-parseable
```

**Phase 2: Component Extraction**

For each detected scheme, extract:

**SemVer Components**:
```regex
^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$
```
- Prefix: `v`, `release-`, `version-` (or none)
- Major: `\d+`
- Minor: `\d+`
- Patch: `\d+`
- Pre-release: `alpha`, `beta`, `rc`, `canary`, `dev`, `nightly`, etc.
- Build metadata: anything after `+`

**CalVer Components**:
```regex
^(\d{4})\.(\d{1,2})(?:\.(\d+))?(?:b(\d+))?$
```
- Year: `YYYY`
- Month: `MM`
- Micro/Patch: optional
- Beta suffix: optional

**Package-Scoped**:
```regex
(@?[^@]+)@(.+)
```
- Package name: everything before final `@` or before `==`
- Version: everything after (parse as SemVer/CalVer)

**Product-Named**:
```regex
^(.+?)\s+v?(\d+\.\d+(?:\.\d+)?.*)$
```
- Product name: initial text
- Version: remainder (parse as SemVer/CalVer)

#### Output Schema Enhancement

Add these fields to `releases.csv`:

**Classification Fields**:
- `version_scheme`: `semver` | `calver` | `package_scoped` | `product_named` | `dev_build` | `descriptive` | `unknown`
- `parseable`: boolean (whether we could extract version components)

**Version Components** (nullable):
- `major_version`: integer
- `minor_version`: integer
- `patch_version`: integer
- `year`: integer (for CalVer)
- `month`: integer (for CalVer)

**Metadata Fields**:
- `version_prefix`: `v`, `release-`, etc.
- `prerelease_tag`: `alpha`, `beta`, `rc`, `canary`, `nightly`, `dev`, etc.
- `prerelease_number`: integer (e.g., `alpha.1` → `1`)
- `build_metadata`: string
- `is_dev_build`: boolean (nightly/canary/dev/snapshot)
- `product_name`: string (extracted product name, if applicable)
- `package_name`: string (extracted package name, if scoped)

**Version Type Classification** (for SemVer only):
- `version_type`: `major` | `minor` | `patch` | `prerelease` | `unknown`
  - Requires comparing with previous release to detect bump type
  - Initial implementation can skip this, add in analysis phase

#### Implementation Approach

**Step 3.1: Create Version Parser Module** (`src/parse_versions.py`)
- Implement detection waterfall
- Create regex patterns for each scheme
- Build extraction functions for each type
- Handle edge cases (malformed versions, unusual formats)

**Step 3.2: Enhance CSV with Parsed Data**
- Read existing `data/releases.csv`
- Apply parser to each row
- Add new columns with parsed components
- Save enhanced version (or create new file `data/releases_parsed.csv`)

**Step 3.3: Generate Parsing Report**
- Count releases by `version_scheme`
- Report parsing success rate (`parseable=true` %)
- Log unparseable versions to `data/unparseable_versions.txt` for manual review
- Create summary statistics

**Step 3.4: Quality Validation**
- Validate that major.minor.patch are numeric where present
- Check for anomalies (e.g., major version > 1000)
- Verify CalVer years are reasonable (e.g., 2010-2026)
- Flag suspicious patterns for review

#### Edge Cases to Handle

1. **Multiple versions in one name**: `"19.1.4 (December 11th, 2024)"` → extract `19.1.4`
2. **Emoji and special chars**: `Inso CLI 2.9.0-beta.0 📦` → strip emoji
3. **Case variations**: `v1.0.0` vs `V1.0.0` vs `Version 1.0.0`
4. **Whitespace**: Leading/trailing spaces
5. **Quotes**: CSV escaping may include quotes
6. **Incomplete versions**: `v1.0` (assume `.0` for patch)
7. **Very long versions**: `v1.2.3.4.5.6` (take first 3 components)

#### Success Metrics

- **Target**: Successfully parse 85%+ of releases
- **SemVer detection**: Should catch most v-prefixed and X.Y.Z patterns
- **CalVer detection**: Should catch YYYY.MM patterns
- **Fallback coverage**: Descriptive category should be < 15%

#### Testing Strategy

- Create unit tests with known version strings
- Test each regex pattern independently
- Validate edge cases
- Test full pipeline with sample data (100 rows)
- Review unparseable versions for pattern discovery

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

- [x] **Project Setup**
  - [x] Initialize Python project with `uv`
  - [x] Add dependencies (requests, pandas, semver)
  - [x] Create project structure (src/, data/, notebooks/)
  - [x] Setup .gitignore for data files and credentials

- [x] **GitHub API Client**
  - [x] Create GitHub API client with authentication
  - [x] Implement rate limiting with exponential backoff
  - [x] Add retry logic for failed requests
  - [x] Setup error logging

- [x] **Repository Fetcher**
  - [x] Implement search API pagination (10 pages × 100 repos)
  - [x] Extract and store repository metadata
  - [x] Save to `data/repositories.csv`
  - [x] Handle API errors gracefully

- [x] **Release Fetcher** (`src/fetch_releases.py`)
  - [x] Implement releases endpoint fetcher with pagination
  - [x] Implement tags endpoint as fallback
  - [x] Fetch commit dates for tags (with progress indicator)
  - [x] Save to `data/releases.csv`
  - [x] Add progress tracking to `data/fetch_progress.json`
  - [x] Implement incremental CSV saving (resume from crashes)
  - [x] Add retry logic with exponential backoff
  - [x] Track repos with no releases in `data/no_releases.txt`
  - [x] Handle 5xx server errors gracefully with partial result saving

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
