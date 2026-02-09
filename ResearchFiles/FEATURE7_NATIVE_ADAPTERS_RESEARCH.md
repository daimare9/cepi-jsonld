# FEATURE 7: Native Adapters People Actually Use — Deep-Dive Research

**Date:** 2026-01-14
**Status:** Research Complete
**Author:** AI Research Agent

---

## Executive Summary

This report evaluates seven integration targets across three categories for native
adapter support in `ceds-jsonld`:

| Category | Target | Python Library | Maturity | Adapter Fit |
|---|---|---|---|---|
| **Spreadsheet** | Google Sheets | `gspread` v6.2.1 | ★★★★★ | Excellent — `get_all_records()` returns `list[dict]` |
| **SIS Platform** | Canvas LMS | `canvasapi` v3.4.0 | ★★★★☆ | Good — paginated REST, `PaginatedList` objects |
| **SIS Platform** | PowerSchool | `httpx` (generic) | ★★★☆☆ | Moderate — REST plugin API, no official Python SDK |
| **SIS Platform** | Infinite Campus | `httpx` (generic) | ★★☆☆☆ | Low — OneRoster API, limited docs |
| **SIS Platform** | Blackbaud (SKY) | `httpx` (generic) | ★★★☆☆ | Moderate — REST/OAuth2, no official Python SDK |
| **Cloud Warehouse** | Snowflake | `snowflake-connector-python` v4.2.0 | ★★★★★ | Excellent — PEP 249, `DictCursor` |
| **Cloud Warehouse** | BigQuery | `google-cloud-bigquery` v3.40.0 | ★★★★★ | Excellent — `query().result()` yields Row dicts |
| **Cloud Warehouse** | Databricks | `databricks-sql-connector` v4.2.5 | ★★★★★ | Excellent — PEP 249, `Row.asDict()` |

**Key Recommendation:** Implement in priority order:
1. **Google Sheets adapter** — highest demand in K-12 education, trivial to implement
2. **Snowflake / BigQuery / Databricks adapters** — share a common DB-API 2.0 pattern,
   can be built as thin wrappers around our existing `DatabaseAdapter` pattern
3. **Canvas LMS adapter** — most open SIS platform, best Python library
4. **PowerSchool / Blackbaud adapters** — build as specialized `APIAdapter` configurations,
   not full custom adapters (REST APIs work with our existing `APIAdapter`)

---

## Table of Contents

1. [Existing Adapter Architecture](#1-existing-adapter-architecture)
2. [Google Sheets (gspread)](#2-google-sheets-gspread)
3. [Canvas LMS (canvasapi)](#3-canvas-lms-canvasapi)
4. [PowerSchool SIS](#4-powerschool-sis)
5. [Infinite Campus](#5-infinite-campus)
6. [Blackbaud SKY API](#6-blackbaud-sky-api)
7. [Snowflake](#7-snowflake)
8. [Google BigQuery](#8-google-bigquery)
9. [Databricks SQL](#9-databricks-sql)
10. [Cloud Warehouse Unified Pattern](#10-cloud-warehouse-unified-pattern)
11. [Proposed Adapter Designs](#11-proposed-adapter-designs)
12. [Optional Dependency Groups](#12-optional-dependency-groups)
13. [Implementation Priority & Effort](#13-implementation-priority--effort)
14. [Risk Register](#14-risk-register)

---

## 1. Existing Adapter Architecture

All adapters extend `SourceAdapter` (ABC) from `src/ceds_jsonld/adapters/base.py`:

```python
class SourceAdapter(ABC):
    @abstractmethod
    def read(self, **kwargs) -> Iterator[dict]:
        """Yield one dict per source record."""

    def read_batch(self, batch_size: int = 1000, **kwargs) -> Iterator[list[dict]]:
        """Yield batches of dicts (default: chunks of 1000)."""

    def count(self) -> int | None:
        """Return total record count, or None if unknown."""
```

**Key design constraints:**
- Adapters yield plain Python `dict` objects — no pandas dependency in the hot path
- Optional dependencies are lazy-imported inside methods (e.g., `httpx` in `APIAdapter`)
- Each adapter is a single file in `src/ceds_jsonld/adapters/`
- Extras are defined in `pyproject.toml` (e.g., `pip install ceds-jsonld[api]`)

**Existing adapters and their optional deps:**

| Adapter | Optional Dep | Extra Name |
|---|---|---|
| `CSVAdapter` | (stdlib) | — |
| `ExcelAdapter` | `openpyxl` | `excel` |
| `NDJSONAdapter` | (stdlib) | — |
| `DictAdapter` | (stdlib) | — |
| `APIAdapter` | `httpx` | `api` |
| `DatabaseAdapter` | `sqlalchemy` | `database` |

---

## 2. Google Sheets (gspread)

### Library Overview

| Property | Value |
|---|---|
| **Package** | `gspread` |
| **Version** | 6.2.1 (latest as of 2026-01) |
| **License** | MIT |
| **Python** | ≥3.8 |
| **Dependencies** | `google-auth`, `google-auth-oauthlib`, `google-auth-httplib2` |
| **Downloads** | ~8M/month (very popular) |
| **Maintenance** | Active, well-maintained |

### Authentication Patterns

gspread supports three authentication modes:

1. **Service Account (headless / server-side):**
   ```python
   import gspread
   gc = gspread.service_account(filename="service_account.json")
   ```
   - Uses a JSON key file from Google Cloud Console
   - **Best for server-side / automated pipelines** — no user interaction needed

2. **OAuth (interactive / user-facing):**
   ```python
   gc = gspread.oauth()
   ```
   - Opens browser for consent, caches token locally
   - Good for CLI / desktop usage

3. **API Key (read-only, public sheets):**
   ```python
   gc = gspread.api_key(api_key="YOUR_API_KEY")
   ```
   - Limited to publicly shared sheets

**Recommendation for our adapter:** Accept `credentials` (pre-built `google.auth.credentials.Credentials`)
or `service_account_file` (path to JSON key file). The service account pattern is
most appropriate for data pipelines.

### Data Access API

```python
# Open a spreadsheet
sh = gc.open("Student Enrollment Data")       # by title
sh = gc.open_by_key("1BxiMVs0XRA5...")       # by spreadsheet ID
sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1Bxi...")  # by URL

# Select worksheet
ws = sh.sheet1                 # first sheet
ws = sh.worksheet("Sheet2")   # by title

# Get all data as list of dicts (PERFECT for our adapter)
records = ws.get_all_records()
# Returns: [{"FirstName": "John", "LastName": "Doe", "Grade": 10}, ...]

# Get all data as list of lists (with header row)
values = ws.get_all_values()
# Returns: [["FirstName", "LastName", "Grade"], ["John", "Doe", "10"], ...]

# Get specific range
cell_range = ws.get("A1:C100")

# Row count
row_count = ws.row_count
```

### Rate Limits

| Limit | Value |
|---|---|
| Per project | 300 requests / 60 seconds |
| Per user per project | 60 requests / 60 seconds |
| Read requests per minute per user | 60 |
| Write requests per minute per user | 60 |

**Implication:** For large sheets (>10K rows), `get_all_records()` returns all data in a
single API call (one request). Rate limits only matter when opening multiple spreadsheets
or switching worksheets frequently. Batch operations (`batch_get()`, `batch_update()`)
help reduce call count.

### Adapter Mapping to SourceAdapter

| SourceAdapter Method | gspread Implementation |
|---|---|
| `read()` | `ws.get_all_records()` → iterate dicts |
| `read_batch()` | Chunk the `get_all_records()` result |
| `count()` | `len(ws.get_all_records())` or `ws.row_count - 1` |

### Proposed Constructor

```python
class GoogleSheetsAdapter(SourceAdapter):
    def __init__(
        self,
        spreadsheet: str,               # title, key, or URL
        worksheet: str | int = 0,        # sheet name or index
        *,
        credentials: Any | None = None,  # google.auth.credentials.Credentials
        service_account_file: str | Path | None = None,
        api_key: str | None = None,
        header_row: int = 1,             # row number containing headers
    ): ...
```

### Effort Estimate

**Small** — 80-120 lines of adapter code. `get_all_records()` returns exactly what
`SourceAdapter.read()` needs. The main complexity is authentication configuration.

---

## 3. Canvas LMS (canvasapi)

### Platform Overview

Canvas LMS by Instructure is the most widely-used LMS in US higher education and
increasingly adopted in K-12. It has the most open and well-documented API among
SIS/LMS platforms.

### API Characteristics

| Property | Value |
|---|---|
| **API Style** | REST over HTTPS |
| **Auth** | OAuth2 Bearer tokens (personal access tokens or OAuth2 flow) |
| **Response Format** | JSON |
| **Pagination** | Link-header pagination (RFC 5988) — 10 items/page default |
| **Rate Limiting** | 700 requests/10 min per user (cost-based) |
| **OpenAPI Spec** | Available (OpenAPI 3.0) |
| **Base URL Pattern** | `https://<institution>.instructure.com/api/v1/` |

### Relevant Endpoints for Education Data

| Endpoint | Returns | CEDS Relevance |
|---|---|---|
| `GET /api/v1/accounts/:id/users` | User list | Person shape |
| `GET /api/v1/courses` | Course list | Course shape |
| `GET /api/v1/courses/:id/enrollments` | Enrollment records | Enrollment shape |
| `GET /api/v1/courses/:id/students` | Students in course | Person + Enrollment |
| `GET /api/v1/users/:id/profile` | User profile | Person shape (detailed) |
| `GET /api/v1/accounts/:id/sis_imports` | SIS Import jobs | Bulk data import |
| `GET /api/v1/courses/:id/assignments` | Assignments | Assessment |
| `GET /api/v1/courses/:id/gradebook_history` | Grade history | Assessment results |

### Python Library: canvasapi

| Property | Value |
|---|---|
| **Package** | `canvasapi` |
| **Version** | 3.4.0 |
| **License** | MIT |
| **Python** | ≥3.7 |
| **Dependencies** | `requests` |

```python
from canvasapi import Canvas

API_URL = "https://example.instructure.com"
API_KEY = "your_api_token"

canvas = Canvas(API_URL, API_KEY)

# Get users
users = canvas.get_account(1).get_users()
for user in users:  # PaginatedList — auto-paginates
    print(user.name, user.email, user.sis_user_id)

# Get enrollments
course = canvas.get_course(12345)
enrollments = course.get_enrollments()
for e in enrollments:
    print(e.user_id, e.course_id, e.type, e.enrollment_state)
```

**Key features:**
- `PaginatedList` objects auto-paginate through all pages transparently
- SIS ID support: most objects have `sis_user_id`, `sis_course_id`, etc.
- Objects have a `__dict__` or attribute access pattern — easy to convert to dict

### Adapter Mapping

| SourceAdapter Method | canvasapi Implementation |
|---|---|
| `read()` | Iterate `PaginatedList`, convert each object to dict |
| `read_batch()` | Chunk the paginated iteration |
| `count()` | Not directly available (would need to iterate all) |

### SIS Data Export

Canvas also supports **SIS Imports** (CSV-based bulk import) and **Provisioning Reports**
(CSV exports of all enrollment data). These could be handled by our existing
`CSVAdapter` after download, making the adapter optionally a thin orchestration layer.

### Effort Estimate

**Medium** — 120-180 lines. Need to handle `PaginatedList` → dict conversion,
multiple endpoint configurations (users, enrollments, courses), and flexible
resource targeting (account ID, course ID).

---

## 4. PowerSchool SIS

### Platform Overview

PowerSchool is the largest K-12 SIS in North America (~45M students). It provides
a REST-based plugin API for data access.

### API Characteristics

| Property | Value |
|---|---|
| **API Style** | REST (Plugin Data Access API) |
| **Auth** | OAuth2 Client Credentials (plugin-based) |
| **Response Format** | JSON |
| **Pagination** | Page-based (`page` + `pagesize` params) |
| **Rate Limiting** | Varies by district installation |
| **Base URL Pattern** | `https://<district>.powerschool.com/ws/v1/` |
| **Python SDK** | None official — use `httpx` or `requests` |

### Key Endpoints

| Endpoint | Returns | CEDS Relevance |
|---|---|---|
| `/ws/v1/district/student` | Student list | Person shape |
| `/ws/v1/district/staff` | Staff list | Person shape |
| `/ws/v1/district/school` | School list | Organization shape |
| `/ws/v1/district/section` | Course sections | Course/Section |
| `/ws/v1/district/enrollment` | Enrollment records | Enrollment |
| `/ws/v1/school/:id/student` | Students in school | Person + Org |

**Typical response structure:**
```json
{
  "students": {
    "student": [
      {
        "id": 12345,
        "local_id": "STU001",
        "name": {"first_name": "John", "last_name": "Doe"},
        "demographics": {"birth_date": "2010-05-15", "gender": "M"}
      }
    ]
  }
}
```

### Authentication Flow

1. Register a plugin in PowerSchool Admin
2. Obtain `client_id` and `client_secret`
3. POST to `/oauth/access_token` with `grant_type=client_credentials`
4. Use Bearer token for subsequent requests

### Adapter Recommendation

**Do NOT build a custom adapter.** PowerSchool's API is standard REST with OAuth2
and JSON responses — our existing `APIAdapter` with `pagination_style="offset"`
can handle it directly:

```python
adapter = APIAdapter(
    url="https://district.powerschool.com/ws/v1/district/student",
    method="GET",
    headers={"Authorization": f"Bearer {token}"},
    results_key="students.student",
    pagination_style="offset",
    page_size=100,
)
```

If we add anything, it should be a **convenience factory function** or **configuration
template**, not a full adapter class.

### Effort Estimate

**Minimal** — A helper function (20-40 lines) that creates a pre-configured `APIAdapter`
with PowerSchool-specific defaults and OAuth token management.

---

## 5. Infinite Campus

### Platform Overview

Infinite Campus is the second-largest K-12 SIS in the US. It supports the
**OneRoster** standard (IMS Global) for interoperability.

### API Characteristics

| Property | Value |
|---|---|
| **API Style** | OneRoster 1.1 / REST |
| **Auth** | OAuth 1.0a (older) or OAuth 2.0 (newer deployments) |
| **Response Format** | JSON (OneRoster format) |
| **Pagination** | `offset` + `limit` params |
| **Python SDK** | None official |
| **Documentation** | District-hosted, not publicly accessible |

### OneRoster Standard

OneRoster is an IMS Global standard that defines a common API across SIS platforms:

| OneRoster Endpoint | Returns | CEDS Relevance |
|---|---|---|
| `/ims/oneroster/v1p1/users` | Users (students + staff) | Person shape |
| `/ims/oneroster/v1p1/orgs` | Organizations (schools + districts) | Organization shape |
| `/ims/oneroster/v1p1/enrollments` | Enrollment records | Enrollment |
| `/ims/oneroster/v1p1/courses` | Courses | Course |
| `/ims/oneroster/v1p1/classes` | Class sections | Section |
| `/ims/oneroster/v1p1/academicSessions` | Terms/semesters | Academic session |

**OneRoster response format:**
```json
{
  "users": [
    {
      "sourcedId": "user-001",
      "status": "active",
      "givenName": "John",
      "familyName": "Doe",
      "role": "student",
      "email": "john.doe@school.edu",
      "orgs": [{"sourcedId": "org-001", "type": "school"}]
    }
  ]
}
```

### Adapter Recommendation

**Build a OneRoster adapter**, not an Infinite Campus–specific adapter. The OneRoster
standard is used by multiple SIS platforms (Infinite Campus, ClassLink, Clever,
Aeries, and others). A `OneRosterAdapter` would be broadly useful.

Our existing `APIAdapter` can almost handle it, but a specialized adapter would
add value by:
- Understanding OneRoster JSON envelope (`users`, `orgs`, `enrollments`)
- Handling OneRoster-specific filtering (e.g., `filter=role='student'`)
- Flattening nested objects (e.g., `orgs[0].sourcedId` → `org_id`)

### Effort Estimate

**Medium** — 100-150 lines for a `OneRosterAdapter` that works with any
OneRoster-compliant SIS.

---

## 6. Blackbaud SKY API

### Platform Overview

Blackbaud serves K-12 private/independent schools, higher education advancement,
and nonprofits. SKY API provides REST access to products like **Education Management**
(K-12 SIS), **Raiser's Edge NXT** (advancement), and **Financial Edge NXT**.

### API Characteristics

| Property | Value |
|---|---|
| **API Style** | REST over HTTPS |
| **Auth** | OAuth 2.0 Authorization Code flow |
| **Response Format** | JSON |
| **Pagination** | `offset` + `limit` or continuation tokens |
| **Rate Limiting** | Varies by subscription tier |
| **Base URL** | `https://api.sky.blackbaud.com/` |
| **Python SDK** | None official |
| **Developer Portal** | developer.blackbaud.com/skyapi |

### Key Endpoints (Education Management)

| Endpoint | Returns | CEDS Relevance |
|---|---|---|
| `/school/v1/users` | Users | Person shape |
| `/school/v1/students` | Students | Person shape |
| `/school/v1/sections` | Course sections | Section |
| `/school/v1/enrollment` | Enrollment records | Enrollment |
| `/school/v1/schools` | Schools | Organization |
| `/school/v1/academics/courses` | Courses | Course |

### Authentication Complexity

Blackbaud's auth is more complex than typical OAuth2:

1. **Register an application** at `developer.blackbaud.com`
2. Application produces `client_id` and `client_secret`
3. A Blackbaud customer **admin must authorize** the app for their environment
4. OAuth2 Authorization Code flow with required `Bb-Api-Subscription-Key` header
5. Subscription key is tied to a paid developer subscription

**This is the most complex auth setup of all platforms evaluated.** It requires
both developer (API provider) and customer (data owner) cooperation.

### Adapter Recommendation

Like PowerSchool, Blackbaud's API is standard REST + OAuth2. A **configuration
template / factory function** for `APIAdapter` is more practical than a dedicated
adapter class. The auth complexity should be documented but delegated to the user
(they pass in their Bearer token and subscription key).

### Effort Estimate

**Minimal** — Factory function (30-50 lines) + documentation. The main effort is
documenting the multi-party OAuth setup.

---

## 7. Snowflake

### Library Overview

| Property | Value |
|---|---|
| **Package** | `snowflake-connector-python` |
| **Version** | 4.2.0 (2026-01-07) |
| **License** | Apache 2.0 |
| **Python** | ≥3.9 |
| **API Standard** | PEP 249 (Python DB-API 2.0) |
| **Downloads** | ~15M/month |
| **Key Feature** | `DictCursor` for dict-based results |

### Authentication Options

| Method | Use Case |
|---|---|
| Username/password | Basic (not recommended for prod) |
| Key-pair auth | Service accounts, CI/CD |
| OAuth (Authorization Code) | Interactive apps |
| OAuth (Client Credentials) | Server-to-server |
| External browser (SSO) | Interactive, SSO-enabled environments |
| Workload Identity | Cloud-native (AWS/GCP/Azure) |

### Data Access API

```python
import snowflake.connector

# Connect
conn = snowflake.connector.connect(
    account="myorg-myaccount",
    user="etl_user",
    private_key_file="/path/to/key.p8",
    warehouse="compute_wh",
    database="education_db",
    schema="public",
)

# DictCursor — returns dicts instead of tuples (PERFECT for our adapter)
cur = conn.cursor(snowflake.connector.DictCursor)
cur.execute("SELECT * FROM students WHERE grade = %s", (10,))

for row in cur:
    print(row)  # {'FIRST_NAME': 'John', 'LAST_NAME': 'Doe', 'GRADE': 10}

# Fetch as pandas (optional, for large datasets)
cur.execute("SELECT * FROM students")
df = cur.fetch_pandas_all()

# Batch fetch
for batch in cur.fetch_pandas_batches():
    process(batch)
```

### Key Features for Our Adapter

1. **`DictCursor`** — Returns `dict` per row, exactly what `SourceAdapter.read()` needs
2. **`fetch_pandas_batches()`** — Efficient batch iteration for large datasets
3. **`ResultBatch`** objects — Can distribute work across workers
4. **`write_pandas()`** — Could be useful for future write-back features
5. **Connection file** (`~/.snowflake/connections.toml`) — Named connections

### Why Not Use DatabaseAdapter + SQLAlchemy?

Our existing `DatabaseAdapter` uses SQLAlchemy, and there's a `snowflake-sqlalchemy`
package. However, the native connector is:
- **Simpler** — No ORM layer, direct SQL
- **Faster** — Arrow-native data path, `fetch_pandas_batches()` uses parallel downloads
- **Feature-rich** — DictCursor, async queries, ResultBatch distribution
- **Better supported** — Official Snowflake driver vs. community SQLAlchemy dialect

**Recommendation:** Build a dedicated `SnowflakeAdapter` using the native connector.

### Effort Estimate

**Small** — 80-120 lines. `DictCursor` + iteration is trivially mapped to
`SourceAdapter.read()`. Main complexity: connection parameter handling.

---

## 8. Google BigQuery

### Library Overview

| Property | Value |
|---|---|
| **Package** | `google-cloud-bigquery` |
| **Version** | 3.40.0 (2026-01-07) |
| **License** | Apache 2.0 |
| **Python** | ≥3.9 |
| **Downloads** | ~30M/month |
| **Key Feature** | Server-side query execution, Row iteration |

### Authentication

BigQuery uses Google Cloud's unified auth:

```python
from google.cloud import bigquery

# Default credentials (ADC — Application Default Credentials)
# Checks: GOOGLE_APPLICATION_CREDENTIALS env var → gcloud CLI → compute metadata
client = bigquery.Client()

# Explicit service account
from google.oauth2 import service_account
creds = service_account.Credentials.from_service_account_file("key.json")
client = bigquery.Client(credentials=creds, project="my-project")
```

### Data Access API

```python
from google.cloud import bigquery

client = bigquery.Client()

# Run a query
query = "SELECT * FROM `my-project.education.students` WHERE grade = @grade"
job_config = bigquery.QueryJobConfig(
    query_parameters=[bigquery.ScalarQueryParameter("grade", "INT64", 10)]
)
query_job = client.query(query, job_config=job_config)

# Iterate rows (Row objects support dict-like access)
for row in query_job.result():
    print(dict(row))  # {'first_name': 'John', 'last_name': 'Doe', 'grade': 10}

# Convert to pandas (for large results)
df = query_job.result().to_dataframe()

# List rows from a table (no SQL needed)
rows = client.list_rows("my-project.education.students", max_results=1000)
for row in rows:
    print(dict(row))
```

### Key Features for Our Adapter

1. **`Row` objects** — Support `dict(row)` conversion → perfect for `SourceAdapter.read()`
2. **`list_rows()`** — Direct table access without SQL
3. **Parameterized queries** — Proper SQL injection protection
4. **Pagination** — Automatic behind the scenes via `result()` iterator
5. **`to_dataframe()`** — Optional pandas integration
6. **`total_rows`** — Row count from `QueryJob.result().total_rows`

### Effort Estimate

**Small** — 80-120 lines. `dict(row)` iteration maps directly to `SourceAdapter.read()`.
Main complexity: project/dataset configuration and authentication setup.

---

## 9. Databricks SQL

### Library Overview

| Property | Value |
|---|---|
| **Package** | `databricks-sql-connector` |
| **Version** | 4.2.5 (2026-01-14) |
| **License** | Apache 2.0 |
| **Python** | ≥3.9 |
| **API Standard** | PEP 249 (Python DB-API 2.0) |
| **Downloads** | ~5M/month |
| **Key Feature** | Arrow data exchange, `Row.asDict()` |

### Authentication Options

| Method | Use Case |
|---|---|
| Personal Access Token | Development, CI/CD |
| OAuth M2M (Client Credentials) | Service accounts |
| OAuth U2M (Browser) | Interactive |

### Data Access API

```python
from databricks import sql
import os

# Connect
with sql.connect(
    server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
    http_path=os.getenv("DATABRICKS_HTTP_PATH"),
    access_token=os.getenv("DATABRICKS_TOKEN"),
) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM education.students LIMIT ?", [100])

        # fetchall returns list of Row objects
        rows = cursor.fetchall()
        for row in rows:
            print(row.asDict())  # {'first_name': 'John', 'last_name': 'Doe'}

        # Batch fetch (Arrow-backed)
        cursor.execute("SELECT * FROM education.students")
        while True:
            batch = cursor.fetchmany(1000)
            if not batch:
                break
            for row in batch:
                process(row.asDict())
```

### Key Features for Our Adapter

1. **`Row.asDict()`** — Converts row to dict → perfect for `SourceAdapter.read()`
2. **`fetchmany(size)`** — True batch fetching with configurable size
3. **`fetchall_arrow()` / `fetchmany_arrow()`** — Arrow-native for large datasets
4. **Context managers** — Clean resource management
5. **Cloud Fetch** — Direct cloud storage downloads for large results
6. **Unity Catalog** — Supports `catalog.schema.table` three-level naming

### Effort Estimate

**Small** — 80-120 lines. `Row.asDict()` + batch fetching maps cleanly to
`SourceAdapter`. Main complexity: connection parameter handling.

---

## 10. Cloud Warehouse Unified Pattern

All three cloud warehouse connectors follow remarkably similar patterns:

```
┌────────────────────────────────────┐
│         SourceAdapter ABC          │
│  read() → Iterator[dict]           │
│  read_batch() → Iterator[list]     │
│  count() → int | None              │
└───────────────┬────────────────────┘
                │
    ┌───────────┴───────────┐
    │ CloudWarehouseAdapter │  ← shared base (optional)
    │ query: str            │
    │ batch_size: int       │
    └───────────┬───────────┘
                │
    ┌───────────┼───────────┐
    │           │           │
    ▼           ▼           ▼
Snowflake   BigQuery   Databricks
DictCursor  dict(row)  Row.asDict()
```

### Common Interface

All three share:
- **SQL query execution** → row iteration
- **Dict-convertible rows** (`DictCursor`, `dict(row)`, `Row.asDict()`)
- **Batch fetching** (`fetchmany`, `fetch_pandas_batches`, `fetchmany_arrow`)
- **Connection with server + auth** (account/hostname + credentials)
- **Optional pandas/Arrow integration** for large datasets

### Unified vs. Separate Adapters

**Option A: Unified `CloudWarehouseAdapter`** with a `backend` parameter:
- Pro: Less code duplication
- Con: Leaky abstraction — each connector has unique params

**Option B: Separate adapters** with shared patterns:
- Pro: Each adapter cleanly wraps its connector's idiomatic API
- Con: More files

**Recommendation: Option B (separate adapters).** The connection parameters are
too different to unify cleanly (Snowflake: account/warehouse/role; BigQuery:
project/dataset; Databricks: hostname/http_path). Keep them separate but follow
a consistent internal pattern.

---

## 11. Proposed Adapter Designs

### 11.1 GoogleSheetsAdapter

```python
class GoogleSheetsAdapter(SourceAdapter):
    """Read education data from Google Sheets via gspread."""

    def __init__(
        self,
        spreadsheet: str,                          # title, key, or URL
        worksheet: str | int = 0,                   # name or 0-based index
        *,
        credentials: Any | None = None,             # google.auth Credentials
        service_account_file: str | Path | None = None,
        api_key: str | None = None,
        header_row: int = 1,
        value_render_option: str = "FORMATTED_VALUE",
    ):
        ...

    def read(self, **kwargs) -> Iterator[dict]:
        gc = self._get_client()
        sh = self._open_spreadsheet(gc)
        ws = self._select_worksheet(sh)
        records = ws.get_all_records(
            head=self.header_row,
            value_render_option=self.value_render_option,
        )
        yield from records

    def count(self) -> int | None:
        # Subtract header row from total row count
        return self._get_worksheet().row_count - self.header_row
```

**Extra:** `pip install ceds-jsonld[sheets]` → `gspread`

### 11.2 CanvasAdapter

```python
class CanvasAdapter(SourceAdapter):
    """Read education data from Canvas LMS via canvasapi."""

    def __init__(
        self,
        base_url: str,                  # https://school.instructure.com
        api_key: str,                   # personal access token
        resource: str,                  # "users", "enrollments", "courses"
        *,
        account_id: int | str = "self",
        course_id: int | None = None,
        include: list[str] | None = None,  # e.g. ["email", "enrollments"]
        per_page: int = 100,
    ):
        ...

    def read(self, **kwargs) -> Iterator[dict]:
        canvas = self._get_canvas()
        paginated = self._get_resource(canvas)
        for obj in paginated:
            yield self._to_dict(obj)

    def _to_dict(self, obj) -> dict:
        """Convert canvasapi object to flat dict."""
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
```

**Extra:** `pip install ceds-jsonld[canvas]` → `canvasapi`

### 11.3 OneRosterAdapter

```python
class OneRosterAdapter(SourceAdapter):
    """Read education data from any OneRoster 1.1 compliant SIS."""

    def __init__(
        self,
        base_url: str,                  # SIS OneRoster endpoint
        resource: str,                  # "users", "orgs", "enrollments", etc.
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        bearer_token: str | None = None,
        filter_expr: str | None = None,  # OneRoster filter, e.g. "role='student'"
        page_size: int = 100,
    ):
        ...

    def read(self, **kwargs) -> Iterator[dict]:
        for page in self._paginate():
            for record in page[self.resource]:
                yield self._flatten(record)
```

**Extra:** `pip install ceds-jsonld[oneroster]` → `httpx` (same as `api` extra)

### 11.4 SnowflakeAdapter

```python
class SnowflakeAdapter(SourceAdapter):
    """Read education data from Snowflake via native connector."""

    def __init__(
        self,
        query: str,
        *,
        account: str,
        user: str | None = None,
        password: str | None = None,
        private_key_file: str | Path | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        role: str | None = None,
        authenticator: str | None = None,
        connection_name: str | None = None,  # from connections.toml
        params: dict | None = None,          # bind parameters
    ):
        ...

    def read(self, **kwargs) -> Iterator[dict]:
        conn = self._connect()
        try:
            cur = conn.cursor(self._get_dict_cursor_class())
            cur.execute(self.query, self.params)
            yield from cur
        finally:
            conn.close()

    def read_batch(self, batch_size: int = 1000, **kwargs) -> Iterator[list[dict]]:
        conn = self._connect()
        try:
            cur = conn.cursor(self._get_dict_cursor_class())
            cur.execute(self.query, self.params)
            while True:
                batch = cur.fetchmany(batch_size)
                if not batch:
                    break
                yield list(batch)
        finally:
            conn.close()

    def count(self) -> int | None:
        return None  # Count requires separate query; not worth the round-trip
```

**Extra:** `pip install ceds-jsonld[snowflake]` → `snowflake-connector-python`

### 11.5 BigQueryAdapter

```python
class BigQueryAdapter(SourceAdapter):
    """Read education data from Google BigQuery."""

    def __init__(
        self,
        query: str | None = None,
        table: str | None = None,          # project.dataset.table
        *,
        project: str | None = None,
        credentials: Any | None = None,
        service_account_file: str | Path | None = None,
        params: dict | None = None,
        max_results: int | None = None,
    ):
        ...

    def read(self, **kwargs) -> Iterator[dict]:
        client = self._get_client()
        if self.query:
            job = client.query(self.query, job_config=self._job_config())
            for row in job.result():
                yield dict(row)
        else:
            for row in client.list_rows(self.table, max_results=self.max_results):
                yield dict(row)

    def count(self) -> int | None:
        if self.table:
            client = self._get_client()
            table_ref = client.get_table(self.table)
            return table_ref.num_rows
        return None
```

**Extra:** `pip install ceds-jsonld[bigquery]` → `google-cloud-bigquery`

### 11.6 DatabricksAdapter

```python
class DatabricksAdapter(SourceAdapter):
    """Read education data from Databricks SQL."""

    def __init__(
        self,
        query: str,
        *,
        server_hostname: str,
        http_path: str,
        access_token: str | None = None,
        credentials_provider: Any | None = None,
        auth_type: str | None = None,
        catalog: str | None = None,
        schema: str | None = None,
        params: list | None = None,
    ):
        ...

    def read(self, **kwargs) -> Iterator[dict]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(self.query, self.params)
                for row in cursor.fetchall():
                    yield row.asDict()

    def read_batch(self, batch_size: int = 1000, **kwargs) -> Iterator[list[dict]]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(self.query, self.params)
                while True:
                    batch = cursor.fetchmany(batch_size)
                    if not batch:
                        break
                    yield [row.asDict() for row in batch]
```

**Extra:** `pip install ceds-jsonld[databricks]` → `databricks-sql-connector`

---

## 12. Optional Dependency Groups

Update `pyproject.toml` with new extras:

```toml
[project.optional-dependencies]
# Existing
excel = ["openpyxl>=3.0"]
api = ["httpx>=0.24"]
database = ["sqlalchemy>=2.0"]

# New — Feature 7
sheets = ["gspread>=6.0"]
canvas = ["canvasapi>=3.0"]
oneroster = ["httpx>=0.24"]             # shares api extra
snowflake = ["snowflake-connector-python>=3.0"]
bigquery = ["google-cloud-bigquery>=3.0"]
databricks = ["databricks-sql-connector>=3.0"]

# Convenience bundles
sis = ["canvasapi>=3.0", "httpx>=0.24"]
warehouse = [
    "snowflake-connector-python>=3.0",
    "google-cloud-bigquery>=3.0",
    "databricks-sql-connector>=3.0",
]
all-adapters = [
    "openpyxl>=3.0",
    "httpx>=0.24",
    "sqlalchemy>=2.0",
    "gspread>=6.0",
    "canvasapi>=3.0",
    "snowflake-connector-python>=3.0",
    "google-cloud-bigquery>=3.0",
    "databricks-sql-connector>=3.0",
]
```

---

## 13. Implementation Priority & Effort

| Priority | Adapter | Effort | Justification |
|---|---|---|---|
| **P1** | `GoogleSheetsAdapter` | 1-2 days | Highest K-12 demand, simplest to build |
| **P2** | `SnowflakeAdapter` | 1-2 days | Most requested cloud warehouse, `DictCursor` is trivial |
| **P2** | `BigQueryAdapter` | 1-2 days | Second most popular, `dict(row)` pattern |
| **P2** | `DatabricksAdapter` | 1-2 days | Growing fast in education, `Row.asDict()` pattern |
| **P3** | `CanvasAdapter` | 2-3 days | Most open SIS, good Python library |
| **P3** | `OneRosterAdapter` | 2-3 days | Standard across many SIS platforms |
| **P4** | PowerSchool template | 0.5 day | Factory function for `APIAdapter` |
| **P4** | Blackbaud template | 0.5 day | Factory function for `APIAdapter` |

**Total estimated effort:** 10-15 days for all adapters with tests and documentation.

### Suggested Implementation Phases

**Phase A (Week 1):** Google Sheets + Snowflake + BigQuery + Databricks
- These are independent, well-documented, and straightforward
- All four share the "yield dicts" pattern with well-tested libraries

**Phase B (Week 2):** Canvas + OneRoster
- These involve paginated REST APIs with more complex data shapes
- OneRoster covers Infinite Campus and other SIS platforms

**Phase C (Week 3):** PowerSchool/Blackbaud templates + documentation
- Factory functions leveraging existing `APIAdapter`
- Comprehensive docs with auth setup guides for each platform

---

## 14. Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Google Sheets rate limiting for large datasets | Medium | Low | `get_all_records()` is single API call; only matters for > 5M cells |
| Canvas API changes or deprecation | Low | Medium | Pin `canvasapi>=3.0,<4.0`; Canvas has stable v1 API |
| PowerSchool API requires per-district plugin registration | High | Medium | Document clearly; provide auth setup guide |
| Blackbaud requires paid developer subscription | High | Medium | Document as prerequisite; not in our control |
| Snowflake connector has heavy dependencies (pyarrow) | Medium | Low | Mark pyarrow extras as optional (`snowflake-connector-python[pandas]`) |
| BigQuery requires GCP billing enabled | Medium | Low | Document; free tier (1TB/month queries) covers most education use |
| Databricks connector minimal on Windows | Low | Low | v4.2.5 has full Windows support |
| OneRoster implementations vary across SIS vendors | High | Medium | Test against reference implementations; allow config overrides |
| Auth token management (refresh, caching) | Medium | Medium | Delegate to user or provide token-refresh helpers |

---

## Appendix A: SIS Platform Market Share (K-12 US)

| Platform | Approx. Market Share | Student Count |
|---|---|---|
| PowerSchool | ~35% | ~45M students |
| Infinite Campus | ~20% | ~8M students |
| Tyler Technologies (Infinite Campus parent) | ~20% | Combined with IC |
| Skyward (now Powerschool) | ~10% | ~2M students |
| Aeries | ~5% | ~3M students (CA-heavy) |
| Others (Synergy, Aspen, etc.) | ~10% | Various |

**Canvas LMS** (distinct from SIS): ~30% of US higher education, growing in K-12.
**Blackbaud**: Dominant in private/independent schools (~40% market share).

## Appendix B: OneRoster Compliant Platforms

The following platforms support OneRoster 1.1 API (partially or fully):
- Infinite Campus
- ClassLink
- Clever
- Aeries
- Follett Destiny
- Illuminate Education
- Powerschool (recent versions)
- Canvas (via CSV, not API)

A single `OneRosterAdapter` would cover data access for all of these platforms.

---

## Appendix C: Library Version Compatibility Matrix

| Library | Min Version | Max Tested | Python Min | Notes |
|---|---|---|---|---|
| `gspread` | 6.0 | 6.2.1 | 3.8 | v6 had breaking changes from v5 |
| `canvasapi` | 3.0 | 3.4.0 | 3.7 | Stable API |
| `snowflake-connector-python` | 3.0 | 4.2.0 | 3.9 | v4 dropped DictCursor inheritance |
| `google-cloud-bigquery` | 3.0 | 3.40.0 | 3.9 | Stable Row API |
| `databricks-sql-connector` | 3.0 | 4.2.5 | 3.9 | v4 extracted SQLAlchemy |
| `httpx` | 0.24 | 0.28+ | 3.8 | Already in our deps |

---

*End of Feature 7 Research Report*
