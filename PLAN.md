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

- [x] **Project Setup**
  - [x] Initialize Python project with `uv`
  - [x] Add dependencies (requests, pandas, semver)
  - [x] Create project structure (src/, data/, notebooks/)
  - [x] Setup .gitignore for data files and credentials

- [ ] **GitHub API Client**
  - [x] Create GitHub API client with authentication
  - [ ] Implement rate limiting with exponential backoff
  - [ ] Add retry logic for failed requests
  - [ ] Setup error logging

- [x] **Repository Fetcher**
  - [x] Implement search API pagination (10 pages × 100 repos)
  - [x] Extract and store repository metadata
  - [x] Save to `data/repositories.csv`
  - [x] Handle API errors gracefully

- [ ] **Release Fetcher**
  - [ ] Implement releases endpoint fetcher with pagination
  - [ ] Implement tags endpoint as fallback
  - [ ] Fetch commit dates for tags
  - [ ] Save to `data/releases.csv`
  - [ ] Add progress tracking for 1000 repos
  - [ ] Implement incremental CSV saving (resume from crashes)
  - [ ] Add retry logic with exponential backoff
  - [ ] Track repos with no releases separately

### Release Fetcher - Detailed Implementation Plan

**File**: `src/fetch_releases.py`

#### Core Logic Flow

```
For each repository in repositories.csv:
  1. Check if already processed (skip if in releases.csv)
  2. Try: Fetch releases from /repos/{owner}/{repo}/releases
     - Paginate through all pages until exhausted
     - Save releases incrementally to CSV
  3. If no releases found, try: Fetch tags from /repos/{owner}/{repo}/tags
     - Paginate through all pages
     - For each tag, fetch commit date from /repos/{owner}/{repo}/commits/{sha}
     - Save as releases with source="tag"
  4. If no tags either, log to no_releases.txt
  5. Update progress tracker
  6. Sleep to respect rate limits
```

#### Pagination Detection

**Method 1: Using Link Header (Preferred)**
GitHub API provides a `Link` header with pagination URLs:
```
Link: <https://api.github.com/repos/owner/repo/releases?page=2>; rel="next",
      <https://api.github.com/repos/owner/repo/releases?page=5>; rel="last"
```

Check for `rel="next"` to determine if more pages exist.

**Method 2: Response Size Check**
If response has fewer items than `per_page`, we've reached the end:
```python
releases = response.json()
if len(releases) < per_page:
    # Last page reached
    break
```

**Method 3: Empty Response**
When no releases exist or we've exhausted all pages:
```python
releases = response.json()
if not releases:  # Empty list
    # No more releases
    break
```

#### Handling Repos Without Releases

1. **Primary Check**: Fetch `/repos/{owner}/{repo}/releases?per_page=1`
   - If returns `[]`, repo has no formal releases

2. **Fallback to Tags**: Fetch `/repos/{owner}/{repo}/tags?per_page=1`
   - If returns `[]`, repo has no tags either

3. **Logging**: Append to `data/no_releases.txt`:
   ```
   facebook/react,no_releases_no_tags
   torvalds/linux,has_tags_only
   ```

4. **Statistics**: Track count of:
   - Repos with releases
   - Repos with tags only
   - Repos with neither

#### Crash Recovery & Incremental Saving

**Problem**: Fetching 1000 repos × ~50 releases each = ~50,000 API calls.
Will take hours and may crash/timeout.

**Solution: Incremental CSV Appending**

1. **Resume Logic**:
   ```python
   def load_processed_repos(releases_csv: Path) -> set:
       """Load set of repos already processed."""
       if not releases_csv.exists():
           return set()

       processed = set()
       with open(releases_csv, 'r') as f:
           reader = csv.DictReader(f)
           for row in reader:
               processed.add(row['repo_full_name'])
       return processed
   ```

2. **Incremental Writing**:
   - Open CSV in append mode after writing header initially
   - After fetching releases for ONE repository, append to CSV immediately
   - Flush file buffer to ensure data is written to disk

   ```python
   # Initial setup
   if not releases_csv.exists():
       with open(releases_csv, 'w') as f:
           writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
           writer.writeheader()

   # For each repo
   with open(releases_csv, 'a', newline='') as f:
       writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
       for release in releases:
           writer.writerow(release)
       f.flush()  # Force write to disk
   ```

3. **Progress Tracking** (Optional but Recommended):
   Create `data/fetch_progress.json`:
   ```json
   {
     "last_processed": "facebook/react",
     "total_processed": 245,
     "total_repos": 1000,
     "started_at": "2025-12-22T10:00:00Z",
     "last_updated": "2025-12-22T12:30:00Z",
     "repos_with_releases": 180,
     "repos_with_tags_only": 45,
     "repos_with_nothing": 20
   }
   ```

4. **Resume on Restart**:
   - Load `processed_repos` set from existing releases.csv
   - Skip repos already in the set
   - Continue from where we left off

#### Rate Limiting Strategy

GitHub API limits:
- **Authenticated**: 5,000 requests/hour
- **Search API**: 30 requests/minute (already used for repos)
- **Core API**: 5,000 requests/hour

**Estimated Requests**:
- 1 request per repo minimum (releases endpoint) = 1,000
- Avg 2-3 pages per repo (pagination) = 2,000-3,000
- Some repos need tags endpoint = +500-1,000
- Tag commit lookups = +1,000-2,000
- **Total**: 4,500-7,500 requests

**Strategy**:
```python
def fetch_with_rate_limit_check(url, headers):
    response = requests.get(url, headers=headers)

    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

    if remaining < 100:  # Buffer of 100 requests
        wait_time = reset_time - time.time()
        if wait_time > 0:
            print(f"⏳ Rate limit low, waiting {int(wait_time)}s...")
            time.sleep(wait_time + 1)

    return response
```

**Sleep Between Repos**:
- Small delay between repositories: `time.sleep(0.5)`
- Prevents hitting burst limits
- Total time: ~8 minutes for basic fetching + API time

#### Error Handling & Retry Logic

```python
def fetch_with_retry(url, headers, max_retries=3):
    """Fetch with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"⏳ Timeout, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Repo deleted or moved
                return None
            elif e.response.status_code == 403:
                # Rate limit or access denied
                check_rate_limit_and_wait(e.response)
                continue
            else:
                raise
```

#### Data Output

**releases.csv** structure:
```csv
repo_full_name,github_release_id,tag_name,release_name,published_at,is_prerelease,is_draft,source,fetched_at
facebook/react,123456,v18.2.0,React 18.2.0,2023-06-15T10:30:00Z,false,false,release,2025-12-22T12:00:00Z
torvalds/linux,,v6.5,Linux 6.5,2023-08-27T18:00:00Z,false,false,tag,2025-12-22T12:01:00Z
```

**no_releases.txt**:
```
owner/repo-name,reason
vercel/next,no_releases_found
```

**fetch_progress.json**:
```json
{
  "last_processed": "microsoft/vscode",
  "total_processed": 458,
  "timestamp": "2025-12-22T14:30:00Z"
}
```

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
