# eventhub

A backend API for managing events and registrations.

## Configuration

Uses Django ORM with SQLite (default). No additional environment variables required.

`rest_framework` and the `events` app must be listed in `INSTALLED_APPS` (already set in `eventhub/settings.py`).

## Running

From the `eventhub/` directory:

```bash
python manage.py migrate
python manage.py runserver
```

Run migrations before starting the server — this project uses Django ORM and SQLite.

## API Endpoints

_To be defined._

## Design Decisions

_To be defined._
