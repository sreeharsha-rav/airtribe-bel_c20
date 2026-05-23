# devtrack

A backend API for tracking engineering issues — report bugs, assign priorities, and track status (similar to a stripped-down GitHub Issues).

## Configuration

No database or environment variables required. Data is persisted in two JSON files created automatically on first write:

- `reporters.json` — reporter records
- `issues.json` — issue records

Both files are created in the directory from which you run `manage.py`.

`rest_framework` and the `issues` app must be listed in `INSTALLED_APPS` (already set in `devtrack/settings.py`).

## Running

From the `devtrack/` directory:

```bash
python manage.py runserver
```

No migrations needed — the project does not use Django ORM.

## API Endpoints

### Reporters

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/reporters/` | List all reporters |
| GET | `/api/reporters/?id=<id>` | Get a single reporter by ID |
| POST | `/api/reporters/` | Create a new reporter |

**POST body:**
```json
{ "name": "Full Name", "email": "email@example.com" }
```

### Issues

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/issues/` | List all issues |
| GET | `/api/issues/?id=<id>` | Get a single issue by ID |
| GET | `/api/issues/?status=<status>` | Filter issues by status |
| POST | `/api/issues/` | Create a new issue |

Valid `status` values: `open`, `in_progress`, `resolved`, `closed`  
Valid `priority` values: `low`, `medium`, `high`, `critical`

**POST body:**
```json
{
  "title": "Issue Summary",
  "description": "Details",
  "status": "open",
  "priority": "high",
  "reporter": "Reporter Name or ID"
}
```

## Design Decisions

### Plain Python OOP with JSON storage

Instead of Django ORM and a database, domain logic is implemented as plain Python classes (`Reporter`, `Issue`, `CriticalIssue`, `LowPriorityIssue`) with JSON file persistence.

This demonstrates core OOP principles — inheritance, encapsulation, polymorphism — without database setup overhead. Priority-based polymorphism: `priority: "critical"` instantiates `CriticalIssue`, `priority: "low"` instantiates `LowPriorityIssue`, anything else uses the base `Issue` class. Each subclass overrides `describe()` to return a priority-appropriate message included in the POST response.
