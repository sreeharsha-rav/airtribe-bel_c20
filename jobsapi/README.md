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
| status          | CharField     | State machine: `pending` → `reviewed` → `accepted` / `rejected` (see below)  |
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

Status always starts as `pending` on creation. Clients update it via PATCH.

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

61 automated tests across 3 modules, using Django's `APITestCase` and an in-memory SQLite database. All tests run isolated — no shared state between tests.

### Test files

```
jobs/tests/
├── factories.py            # make_company / make_job / make_application helpers
├── test_companies.py       # 15 tests — CRUD, cascade delete, PUT validation
├── test_jobs.py            # 17 tests — CRUD, salary cross-field, job_type choices, PATCH partial
└── test_applications.py    # 29 tests — CRUD, duplicate detection, email validation, state machine
```

### Coverage report

```
Name                                    Stmts   Miss  Cover
-----------------------------------------------------------
jobs/models.py                             38      3    92%
jobs/serializers.py                        59      2    97%
jobs/views.py                              21      0   100%
jobs/urls.py                                8      0   100%
jobs/tests/test_companies.py               76      0   100%
jobs/tests/test_jobs.py                   102      0   100%
jobs/tests/test_applications.py           182      0   100%
-----------------------------------------------------------
TOTAL (app code only)                     573     45    92%
```

> `seed.py` is excluded from meaningful coverage — it is a dev-only management command, not application logic.  
> The 5 uncovered lines are `__str__` methods on models (lines 13, 32, 56) and a `created_at is None` guard in `get_days_since_posted` (line 28 of serializers) that can't be triggered via the API since the field uses `auto_now_add`.

### Test summary by area

| Area | Tests | What is covered |
|------|------:|-----------------|
| Companies | 15 | List, create, retrieve, PUT, PATCH, DELETE; PUT requires all fields; cascade delete; invalid website URL; 404 |
| Jobs | 17 | List (nested company, `days_since_posted`), create, retrieve, PUT, PATCH, DELETE; `salary_min > salary_max`; salary bounds; invalid `job_type`; non-existent `company_id`; PATCH cross-field validation; 404 |
| Applications | 29 | List (nested `job → company`, `applied_at`); create via `/applications/` and `/jobs/{id}/apply/`; `status` forced to `pending` on create; `applied_at` is read-only; duplicate detection on both endpoints; same email allowed on different jobs; invalid email; non-existent `job_id`; all 3 valid state transitions; 6 invalid transitions (backward + terminal); PATCH without `status` unchanged; error message content; DELETE + 404 |

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

### 3. Apply for the job

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

### 4. Advance application status

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

### 5. Create an application directly

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
