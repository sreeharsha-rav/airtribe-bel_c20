# Jobs API

A backend service for browsing and applying for jobs. Demonstrates Django models, ForeignKey relationships, TextChoices, migrations, admin registration, and management commands.

## Concepts Demonstrated

- **Models** — `Company`, `Job`, and `Application` models with ForeignKey relationships
- **TextChoices** — `Job.JobType` and `Application.Status` enums for constrained field values
- **Migrations** — schema creation via `makemigrations` / `migrate`
- **Admin** — models registered with `admin.site.register` for built-in CRUD UI
- **Management command** — `python manage.py seed` to populate the database for development

## Models

### Company

| Field    | Type      | Notes               |
|----------|-----------|---------------------|
| name     | CharField | Company name        |
| location | CharField | City / region       |
| website  | URLField  | Company website URL |

### Job

| Field      | Type         | Notes                                                       |
|------------|--------------|-------------------------------------------------------------|
| title      | CharField    | Job title                                                   |
| salary_min | DecimalField | Minimum salary                                              |
| salary_max | DecimalField | Maximum salary                                              |
| job_type   | CharField    | Choices: `full_time`, `part_time`, `contract`, `internship` |
| location   | CharField    | Job location                                                |
| company    | ForeignKey   | References `Company`; cascade deletes jobs                  |

### Application

| Field           | Type       | Notes                                                    |
|-----------------|------------|----------------------------------------------------------|
| job             | ForeignKey | References `Job`; cascade deletes applications           |
| applicant_name  | CharField  | Full name of the applicant                               |
| applicant_email | EmailField | Email address of the applicant                           |
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

_To be implemented with Django REST Framework._
