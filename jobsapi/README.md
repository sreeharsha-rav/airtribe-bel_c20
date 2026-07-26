# Jobs API

A backend service for browsing and applying for jobs. Demonstrates Django models, ForeignKey relationships, TextChoices, migrations, admin registration, management commands, and a REST API built with Django REST Framework.

## Concepts Demonstrated

- **Models** — `Company`, `Job`, and `Application` models with ForeignKey relationships
- **TextChoices** — `Job.JobType` and `Application.Status` enums for constrained field values
- **Migrations** — schema creation via `makemigrations` / `migrate`
- **Admin** — models registered with `admin.site.register` for built-in CRUD UI
- **Management command** — `python manage.py seed` to populate the database for development
- **DRF ModelViewSet** — full CRUD in a single class; custom actions via `@action`
- **DRF DefaultRouter** — auto-generates all standard URL patterns from `router.register()`
- **DRF Serializers** — field-level and object-level validation, nested read serializers, split read/write FK fields, `create` override, computed fields, state machine validation
- **DRF Pagination** — `PageNumberPagination` wraps all list responses in `{count, next, previous, results}`
- **DRF Filtering** — `DjangoFilterBackend` for exact-match and range filters; `SearchFilter` for full-text search; `OrderingFilter` for sort control
- **OpenAPI / Swagger** — `drf-spectacular` generates a fully annotated schema with `@extend_schema` / `@extend_schema_view`; served at `/api/docs/`
- **Middleware** — `RequestTimingMiddleware` logs method, path, status, and duration for every request

## Data Models

### Company

| Field    | Type      | Notes               |
|----------|-----------|---------------------|
| id       | AutoField | Primary key         |
| name     | CharField | Company name        |
| location | CharField | City / region       |
| website  | URLField  | Company website URL |

### Job

| Field      | Type          | Notes                                                       |
|------------|---------------|-------------------------------------------------------------|
| id         | AutoField     | Primary key                                                 |
| title      | CharField     | Job title                                                   |
| salary_min | DecimalField  | Minimum salary (1–500,000)                                  |
| salary_max | DecimalField  | Maximum salary (1–500,000); must be ≥ salary_min            |
| job_type   | CharField     | Choices: `full_time`, `part_time`, `contract`, `internship` |
| location   | CharField     | Job location                                                |
| company    | ForeignKey    | References `Company`; cascade deletes jobs                  |
| created_at | DateTimeField | Set automatically on creation                               |

### Application

| Field           | Type          | Notes                                                                                                   |
|-----------------|---------------|---------------------------------------------------------------------------------------------------------|
| id              | AutoField     | Primary key (read-only)                                                                                 |
| job             | ForeignKey    | References `Job`; cascade deletes applications                                                          |
| applicant_name  | CharField     | Full name of the applicant                                                                              |
| applicant_email | EmailField    | Email address of the applicant (validated by regex)                                                     |
| status          | CharField     | Read-only on create (always `pending`); writable on PATCH/PUT following state machine rules (see below) |
| applied_at      | DateTimeField | Set automatically on creation (read-only)                                                               |

#### Application Status State Machine

```
pending ──► reviewed ──► accepted
       │            └──► rejected
       └──► withdrawn  (terminal — via PATCH or POST /withdrawn/)
```

| From         | Allowed transitions          |
|--------------|------------------------------|
| `pending`    | `reviewed`, `withdrawn`      |
| `reviewed`   | `accepted`, `rejected`       |
| `accepted`   | — (terminal)                 |
| `rejected`   | — (terminal)                 |
| `withdrawn`  | — (terminal)                 |

Status always starts as `pending` on creation — the field is read-only on POST and any value sent is silently ignored. Clients advance it via PATCH (or PUT with a full body). Sending the current status again (same → same) is a no-op and always succeeds.

## Setup

1. Apply migrations:
```bash
python manage.py migrate
```

2. Seed the database:
```bash
python manage.py seed           # skips already-existing records
python manage.py seed --clear   # wipes and re-seeds from scratch
```

3. Run the development server:
```bash
python manage.py runserver
```

4. Open the admin panel at `http://localhost:8000/admin/`

## API Endpoints

Base URL: `http://localhost:8000/api/`

A browsable API root listing all endpoints is available at `http://localhost:8000/api/`.

### Companies

| Method | Endpoint               | Description              |
|--------|------------------------|--------------------------|
| GET    | `/api/companies/`      | List all companies       |
| POST   | `/api/companies/`      | Create a company         |
| GET    | `/api/companies/{id}/` | Get a company            |
| PUT    | `/api/companies/{id}/` | Replace a company        |
| PATCH  | `/api/companies/{id}/` | Partially update company |
| DELETE | `/api/companies/{id}/` | Delete a company         |

### Jobs

| Method | Endpoint                | Description                                          |
|--------|-------------------------|------------------------------------------------------|
| GET    | `/api/jobs/`            | List jobs (supports filtering, search, and ordering) |
| POST   | `/api/jobs/`            | Create a job                                         |
| GET    | `/api/jobs/{id}/`       | Get a job                                            |
| PUT    | `/api/jobs/{id}/`       | Replace a job                                        |
| PATCH  | `/api/jobs/{id}/`       | Partially update a job                               |
| DELETE | `/api/jobs/{id}/`       | Delete a job                                         |
| POST   | `/api/jobs/{id}/apply/` | Apply for a job                                      |

### Applications

| Method | Endpoint                           | Description                        |
|--------|------------------------------------|------------------------------------|
| GET    | `/api/applications/`               | List all applications              |
| POST   | `/api/applications/`               | Create an application              |
| GET    | `/api/applications/{id}/`          | Get an application                 |
| PUT    | `/api/applications/{id}/`          | Replace an application             |
| PATCH  | `/api/applications/{id}/`          | Partially update (e.g. status)     |
| DELETE | `/api/applications/{id}/`          | Delete an application              |
| POST   | `/api/applications/{id}/withdrawn/`| Withdraw a pending application     |

## Pagination

All list endpoints return a paginated envelope instead of a bare array.

**Default page size:** 10

**Response shape:**
```json
{
  "count": 42,
  "next": "http://localhost:8000/api/jobs/?page=3",
  "previous": "http://localhost:8000/api/jobs/?page=1",
  "results": [ ... ]
}
```

| Field      | Description                                              |
|------------|----------------------------------------------------------|
| `count`    | Total number of records across all pages                 |
| `next`     | URL of the next page, or `null` if on the last page      |
| `previous` | URL of the previous page, or `null` if on the first page |
| `results`  | Array of objects for the current page                    |

**Navigating pages:**
```bash
GET /api/jobs/          # page 1 (default)
GET /api/jobs/?page=2   # page 2
GET /api/jobs/?page=3   # page 3
```

## Filtering, Search, and Ordering

The `GET /api/jobs/` endpoint supports query parameters for filtering, full-text search, and ordering. Parameters can be combined freely.

### Filtering

Exact-match filters and salary range filters:

| Parameter    | Type    | Description                                           | Example                      |
|--------------|---------|-------------------------------------------------------|------------------------------|
| `job_type`   | string  | Exact match on job type                               | `?job_type=full_time`        |
| `location`   | string  | Exact match on location                               | `?location=Remote`           |
| `salary_min` | number  | Return jobs where `salary_min` is **≥** this value    | `?salary_min=60000`          |
| `salary_max` | number  | Return jobs where `salary_max` is **≤** this value    | `?salary_max=150000`         |

**Valid `job_type` values:** `full_time`, `part_time`, `contract`, `internship`

**Combine filters for a salary range:**
```bash
GET /api/jobs/?salary_min=60000&salary_max=150000
```

### Search

Full-text search on job `title`:

```bash
GET /api/jobs/?search=engineer
GET /api/jobs/?search=backend
```

The `search` parameter matches any job whose title contains the given term (case-insensitive).

### Ordering

Sort results by a field. Prefix with `-` for descending order:

| Parameter            | Description                           |
|----------------------|---------------------------------------|
| `?ordering=created_at`  | Oldest postings first              |
| `?ordering=-created_at` | Newest postings first (default)    |
| `?ordering=salary_min`  | Lowest minimum salary first        |
| `?ordering=-salary_min` | Highest minimum salary first       |

**Combined example — remote full-time jobs, salary 60k–150k, sorted by newest:**
```bash
GET /api/jobs/?job_type=full_time&location=Remote&salary_min=60000&salary_max=150000&ordering=-created_at
```

## Withdraw Endpoint

`POST /api/applications/{id}/withdrawn/`

Allows an applicant to cancel a pending application. No request body is required.

**Rules:**
- Only applications in `pending` status can be withdrawn
- Returns `400` if the application is already `withdrawn`
- Returns `400` if the application has progressed past `pending` (`reviewed`, `accepted`, or `rejected`)
- Returns `404` if the application does not exist

**Successful withdrawal — 200:**
```bash
curl -X POST http://localhost:8000/api/applications/1/withdrawn/
```
```json
{
  "id": 1,
  "job": { "id": 1, "title": "Backend Engineer", "..." },
  "applicant_name": "Jane Doe",
  "applicant_email": "jane@example.com",
  "status": "withdrawn",
  "applied_at": "2024-01-15T10:30:00Z"
}
```

**Already past pending — 400:**
```json
{"detail": "Cannot withdraw an application with status 'reviewed'."}
```

**Already withdrawn — 400:**
```json
{"detail": "Application is already withdrawn."}
```

## Swagger / OpenAPI Docs

Interactive API documentation is served automatically via `drf-spectacular`.

| URL              | Description                                        |
|------------------|----------------------------------------------------|
| `/api/docs/`     | Swagger UI — browse and try all endpoints live     |
| `/api/schema/`   | Raw OpenAPI 3 schema (JSON/YAML, for tooling)      |

All endpoints are annotated with `@extend_schema` / `@extend_schema_view` providing:
- Business-area **tags** (`companies`, `jobs`, `applications`, `admin`)
- Human-readable **summaries** and **descriptions**
- Typed **request** and **response** schemas
- **Error response** examples for `400` (with distinct cases) and `404`

### Generate the schema YAML

Export a static `schema.yaml` for use with code generators, API gateways, or CI validation:

```bash
# Generate and validate (fails on any warnings)
python manage.py spectacular --color --file schema.yaml --validate --fail-on-warn

# Generate without strict validation
python manage.py spectacular --file schema.yaml
```

The generated file is an OpenAPI 3.0 document importable into Postman, Insomnia, or any OpenAPI-compatible tool.

## Running Tests

```bash
# Run all tests
python manage.py test jobs.tests

# Run a single test module
python manage.py test jobs.tests.test_companies
python manage.py test jobs.tests.test_jobs
python manage.py test jobs.tests.test_applications

# Run with verbose output (shows each test name)
python manage.py test jobs.tests --verbosity=2

# Run with coverage (install once: pip install coverage)
python -m coverage run --source=jobs manage.py test jobs.tests
python -m coverage report -m          # terminal report
python -m coverage html -d htmlcov    # HTML report → open htmlcov/index.html
```

## Test Coverage

47 automated tests across 3 modules, using Django's `APITestCase` and an in-memory SQLite database. All tests run isolated — no shared state between tests.

### Test files

```
jobs/tests/
├── factories.py            # make_company / make_job / make_application helpers
├── test_companies.py       # CRUD, pagination envelope, multi-page, cascade delete
├── test_jobs.py            # CRUD, pagination envelope, multi-page, salary validation
└── test_applications.py    # CRUD, pagination, state machine, withdraw endpoint
```

### Test summary by area

| Area         | What is covered |
|--------------|-----------------|
| Companies    | Pagination envelope; multi-page navigation; CRUD; PUT requires all fields; cascade delete; invalid website URL; 404 |
| Jobs         | Pagination envelope; multi-page navigation; nested company; `days_since_posted`; CRUD; `salary_min > salary_max`; salary bounds; invalid `job_type`; non-existent `company_id`; PATCH cross-field validation; 404 |
| Applications | Pagination envelope; multi-page navigation; nested `job → company`; create via `/applications/` and `/jobs/{id}/apply/`; `status` read-only on create; `applied_at` read-only; duplicate detection; PUT self-duplicate false-positive fix; genuine duplicate still blocked; same email across different jobs; invalid email; non-existent `job_id`; same-status no-op; valid state transitions; invalid transitions; PATCH without `status` unchanged; error message content; withdraw happy path; withdraw 400 for all non-pending statuses; withdraw 404; PATCH blocked after withdrawal; DELETE + 404 |

---

## Sample Workflow

### 1. Create a company

```bash
curl -X POST http://localhost:8000/api/companies/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "location": "San Francisco", "website": "https://acme.com"}'
```

```json
{"id": 1, "name": "Acme Corp", "location": "San Francisco", "website": "https://acme.com"}
```

### 2. Post a job

```bash
curl -X POST http://localhost:8000/api/jobs/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Backend Engineer", "job_type": "full_time", "location": "Remote", "salary_min": "80000", "salary_max": "120000", "company_id": 1}'
```

```json
{
  "id": 1,
  "title": "Backend Engineer",
  "job_type": "full_time",
  "location": "Remote",
  "salary_min": "80000.00",
  "salary_max": "120000.00",
  "company": {"id": 1, "name": "Acme Corp", "location": "San Francisco", "website": "https://acme.com"},
  "days_since_posted": 0
}
```

### 3. Search and filter jobs

```bash
# Full-text search
curl "http://localhost:8000/api/jobs/?search=backend"

# Salary range
curl "http://localhost:8000/api/jobs/?salary_min=60000&salary_max=150000"

# Combined: remote full-time jobs, newest first
curl "http://localhost:8000/api/jobs/?job_type=full_time&location=Remote&ordering=-created_at"
```

### 4. Apply for a job

```bash
curl -X POST http://localhost:8000/api/jobs/1/apply/ \
  -H "Content-Type: application/json" \
  -d '{"applicant_name": "Jane Doe", "applicant_email": "jane@example.com"}'
```

```json
{
  "id": 1,
  "job": {"id": 1, "title": "Backend Engineer", "...": "..."},
  "applicant_name": "Jane Doe",
  "applicant_email": "jane@example.com",
  "status": "pending",
  "applied_at": "2024-01-15T10:30:00Z"
}
```

### 5. Advance application status

```bash
curl -X PATCH http://localhost:8000/api/applications/1/ \
  -H "Content-Type: application/json" \
  -d '{"status": "reviewed"}'
```

Invalid transitions return a 400:

```json
{"status": ["Cannot transition from 'reviewed' to 'pending'."]}
```

### 6. Withdraw an application

```bash
curl -X POST http://localhost:8000/api/applications/1/withdrawn/
```

```json
{
  "id": 1,
  "job": {"id": 1, "title": "Backend Engineer", "...": "..."},
  "applicant_name": "Jane Doe",
  "applicant_email": "jane@example.com",
  "status": "withdrawn",
  "applied_at": "2024-01-15T10:30:00Z"
}
```
