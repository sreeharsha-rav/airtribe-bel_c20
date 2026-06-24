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

| Field           | Type          | Notes                                                                         |
|-----------------|---------------|-------------------------------------------------------------------------------|
| id              | AutoField     | Primary key (read-only)                                                       |
| job             | ForeignKey    | References `Job`; cascade deletes applications                                |
| applicant_name  | CharField     | Full name of the applicant                                                    |
| applicant_email | EmailField    | Email address of the applicant (validated by regex)                           |
| status          | CharField     | Read-only on create (always `pending`); writable on PATCH/PUT following state machine rules (see below) |
| applied_at      | DateTimeField | Set automatically on creation (read-only)                                     |

#### Application Status State Machine

```
pending ──► reviewed ──► accepted
                    └──► rejected
```

| From       | Allowed transitions      |
|------------|--------------------------|
| `pending`  | `reviewed`               |
| `reviewed` | `accepted`, `rejected`   |
| `accepted` | — (terminal)             |
| `rejected` | — (terminal)             |

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

| Method | Endpoint                  | Description              |
|--------|---------------------------|--------------------------|
| GET    | `/api/jobs/`              | List all jobs            |
| POST   | `/api/jobs/`              | Create a job             |
| GET    | `/api/jobs/{id}/`         | Get a job                |
| PUT    | `/api/jobs/{id}/`         | Replace a job            |
| PATCH  | `/api/jobs/{id}/`         | Partially update a job   |
| DELETE | `/api/jobs/{id}/`         | Delete a job             |
| POST   | `/api/jobs/{id}/apply/`   | Apply for a job          |

### Applications

| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| GET    | `/api/applications/`        | List all applications          |
| POST   | `/api/applications/`        | Create an application          |
| GET    | `/api/applications/{id}/`   | Get an application             |
| PUT    | `/api/applications/{id}/`   | Replace an application         |
| PATCH  | `/api/applications/{id}/`   | Partially update (e.g. status) |
| DELETE | `/api/applications/{id}/`   | Delete an application          |

## Pagination

All list endpoints (`GET /api/companies/`, `GET /api/jobs/`, `GET /api/applications/`) return a paginated envelope instead of a bare array.

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

| Field | Description |
|-------|-------------|
| `count` | Total number of records across all pages |
| `next` | URL of the next page, or `null` if on the last page |
| `previous` | URL of the previous page, or `null` if on the first page |
| `results` | Array of objects for the current page |

**Navigating pages:**
```bash
GET /api/jobs/          # page 1 (default)
GET /api/jobs/?page=2   # page 2
GET /api/jobs/?page=3   # page 3
```

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

# Run with coverage (install once: python -m ensurepip && python -m pip install coverage)
python -m coverage run --source=jobs manage.py test jobs.tests
python -m coverage report -m          # terminal report
python -m coverage html -d htmlcov    # HTML report → open htmlcov/index.html
```

## Test Coverage

77 automated tests across 3 modules, using Django's `APITestCase` and an in-memory SQLite database. All tests run isolated — no shared state between tests.

### Test files

```
jobs/tests/
├── factories.py            # make_company / make_job / make_application helpers
├── test_companies.py       # 21 tests — CRUD, pagination envelope, multi-page, cascade delete
├── test_jobs.py            # 23 tests — CRUD, pagination envelope, multi-page, salary validation
└── test_applications.py    # 41 tests — CRUD, pagination envelope, multi-page, status read-only
                            #             on create, duplicate detection, state machine
```

### Coverage report

```
Name                                    Stmts   Miss  Cover
-----------------------------------------------------------
jobs/models.py                             43      3    93%
jobs/serializers.py                        66      2    97%
jobs/views.py                              21      0   100%
jobs/urls.py                                8      0   100%
jobs/tests/test_companies.py              102      0   100%
jobs/tests/test_jobs.py                   123      0   100%
jobs/tests/test_applications.py           239      0   100%
-----------------------------------------------------------
TOTAL (app code only)                     689     45    93%
```

> `seed.py` is excluded from meaningful coverage — it is a dev-only management command, not application logic.  
> The 5 uncovered lines are `__str__` methods on models and a `created_at is None` guard in `get_days_since_posted` that cannot be reached via the API since `auto_now_add` always sets the field.

### Test summary by area

| Area | Tests | What is covered |
|------|------:|-----------------|
| Companies | 21 | Pagination envelope (count, next, previous, results); 12-item dataset — 10 on page 1, 2 on page 2; single-page next/previous null; CRUD; PUT requires all fields; cascade delete; invalid website URL; 404 |
| Jobs | 23 | Pagination envelope; multi-page navigation; nested company in list; `days_since_posted`; CRUD; `salary_min > salary_max`; salary bounds; invalid `job_type`; non-existent `company_id`; PATCH cross-field validation; 404 |
| Applications | 41 | Pagination envelope; multi-page navigation; nested `job → company`; `applied_at` and `status` present; create via `/applications/` and `/jobs/{id}/apply/`; `status` read-only on create (both endpoints); `applied_at` read-only; duplicate detection; PUT self-duplicate false-positive fix; genuine duplicate still blocked; same email across different jobs; invalid email; non-existent `job_id`; same-status no-op; 3 valid state transitions; 6 invalid transitions; PATCH without `status` unchanged; error message content; DELETE + 404 |

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

### 2. List jobs (paginated)

```bash
curl http://localhost:8000/api/jobs/
```

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
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
  ]
}
```

### 3. Post a job

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

### 4. Apply for the job

```bash
curl -X POST http://localhost:8000/api/jobs/1/apply/ \
  -H "Content-Type: application/json" \
  -d '{"applicant_name": "Jane Doe", "applicant_email": "jane@example.com"}'
```

```json
{
  "id": 1,
  "job": {
    "id": 1,
    "title": "Backend Engineer",
    "job_type": "full_time",
    "location": "Remote",
    "salary_min": "80000.00",
    "salary_max": "120000.00",
    "company": {"id": 1, "name": "Acme Corp", "location": "San Francisco", "website": "https://acme.com"},
    "days_since_posted": 0
  },
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

```json
{
  "id": 1,
  "job": {"id": 1, "title": "Backend Engineer", ...},
  "applicant_name": "Jane Doe",
  "applicant_email": "jane@example.com",
  "status": "reviewed",
  "applied_at": "2024-01-15T10:30:00Z"
}
```

Invalid transitions return a 400:

```bash
curl -X PATCH http://localhost:8000/api/applications/1/ \
  -H "Content-Type: application/json" \
  -d '{"status": "pending"}'
```

```json
{"status": ["Cannot transition from 'reviewed' to 'pending'."]}
```

### 6. Create an application directly

```bash
curl -X POST http://localhost:8000/api/applications/ \
  -H "Content-Type: application/json" \
  -d '{"job_id": 1, "applicant_name": "Jane Doe", "applicant_email": "jane@example.com"}'
```

```json
{
  "id": 1,
  "job": {"id": 1, "title": "Backend Engineer", ...},
  "applicant_name": "Jane Doe",
  "applicant_email": "jane@example.com",
  "status": "pending",
  "applied_at": "2024-01-15T10:30:00Z"
}
```
