# Jobs API

A backend service for browsing and applying for jobs. Demonstrates Django models, ForeignKey relationships, TextChoices, migrations, admin registration, management commands, and a REST API built with Django REST Framework.

## Concepts Demonstrated

- **Models** — `Company`, `Job`, and `Application` models with ForeignKey relationships
- **TextChoices** — `Job.JobType` and `Application.Status` enums for constrained field values
- **Migrations** — schema creation via `makemigrations` / `migrate`
- **Admin** — models registered with `admin.site.register` for built-in CRUD UI
- **Management command** — `python manage.py seed` to populate the database for development
- **DRF APIView** — class-based views with manual serialization control
- **DRF Serializers** — field-level and object-level validation, nested read serializers, computed fields
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

| Field            | Type         | Notes                                                       |
|------------------|--------------|-------------------------------------------------------------|
| id               | AutoField    | Primary key                                                 |
| title            | CharField    | Job title                                                   |
| salary_min       | DecimalField | Minimum salary (1–500,000)                                  |
| salary_max       | DecimalField | Maximum salary (1–500,000); must be ≥ salary_min            |
| job_type         | CharField    | Choices: `full_time`, `part_time`, `contract`, `internship` |
| location         | CharField    | Job location                                                |
| company          | ForeignKey   | References `Company`; cascade deletes jobs                  |
| created_at       | DateTimeField| Set automatically on creation                               |

### Application

| Field           | Type       | Notes                                                     |
|-----------------|------------|-----------------------------------------------------------|
| id              | AutoField  | Primary key                                               |
| job             | ForeignKey | References `Job`; cascade deletes applications            |
| applicant_name  | CharField  | Full name of the applicant                                |
| applicant_email | EmailField | Email address of the applicant (validated by regex)       |
| status          | CharField  | Choices: `applied`, `interviewing`, `offered`, `rejected` |

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

### Companies

| Method | Endpoint               | Description         |
|--------|------------------------|---------------------|
| GET    | `/api/companies/`      | List all companies  |
| POST   | `/api/companies/`      | Create a company    |
| GET    | `/api/companies/{id}/` | Get a company       |
| PUT    | `/api/companies/{id}/` | Update a company    |
| DELETE | `/api/companies/{id}/` | Delete a company    |

### Jobs

| Method | Endpoint              | Description                        |
|--------|-----------------------|------------------------------------|
| GET    | `/api/jobs/`          | List all jobs                      |
| POST   | `/api/jobs/`          | Create a job                       |
| GET    | `/api/jobs/{id}/`     | Get a job                          |
| PUT    | `/api/jobs/{id}/`     | Update a job                       |
| DELETE | `/api/jobs/{id}/`     | Delete a job                       |
| POST   | `/api/jobs/{id}/apply/` | Apply for a job                  |

### Applications

| Method | Endpoint                    | Description            |
|--------|-----------------------------|------------------------|
| GET    | `/api/applications/`        | List all applications  |
| POST   | `/api/applications/`        | Create an application  |
| GET    | `/api/applications/{id}/`   | Get an application     |
| PUT    | `/api/applications/{id}/`   | Update an application  |
| DELETE | `/api/applications/{id}/`   | Delete an application  |

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
{"id": 1, "job": 1, "applicant_name": "Jane Doe", "applicant_email": "jane@example.com", "status": "applied"}
```

### 4. Check all applications

```bash
curl http://localhost:8000/api/applications/
```

### 5. Update application status

```bash
curl -X PUT http://localhost:8000/api/applications/1/ \
  -H "Content-Type: application/json" \
  -d '{"status": "interviewing"}'
```

```json
{"id": 1, "job": 1, "applicant_name": "Jane Doe", "applicant_email": "jane@example.com", "status": "interviewing"}
```
