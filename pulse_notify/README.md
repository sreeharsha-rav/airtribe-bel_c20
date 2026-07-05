# PulseNotify — Flight Price Monitor & Alert System

PulseNotify is a flight price monitoring service that lets users set price alerts for specific routes. When a flight price drops below a user's target, the system sends a notification automatically.

**How it works:**
- Price checks run in the background at regular intervals — the user never waits.
- When a price drops below the configured threshold, a `NotificationLog` is created and the alert status is updated to `triggered`.
- Price data comes from an internal price feed endpoint.

---

## Data Models

### User *(extends AbstractUser)*

| Field    | Type       | Notes                                         |
|----------|------------|-----------------------------------------------|
| id       | AutoField  | Primary key                                   |
| username | CharField  | Inherited from `AbstractUser`                 |
| email    | EmailField | Inherited from `AbstractUser`                 |
| password | CharField  | Hashed via `create_user()`; write-only in API |
| role     | CharField  | Choices: `admin`, `user`; default `user`      |

### PriceAlert *(N per User)*

| Field           | Type          | Notes                                                        |
|-----------------|---------------|--------------------------------------------------------------|
| id              | AutoField     | Primary key                                                  |
| user            | ForeignKey    | References `User`; cascades on delete                        |
| origin          | CharField     | Origin airport code (e.g. `DEL`)                             |
| destination     | CharField     | Destination airport code (e.g. `BOM`)                        |
| threshold_price | DecimalField  | Target price to trigger the alert                            |
| status          | CharField     | Choices: `active`, `inactive`, `triggered`; default `active` |
| created_at      | DateTimeField | Auto-set on creation                                         |

### NotificationLog *(N per PriceAlert)*

| Field           | Type          | Notes                                         |
|-----------------|---------------|-----------------------------------------------|
| id              | AutoField     | Primary key                                   |
| alert           | ForeignKey    | References `PriceAlert`; cascades on delete   |
| triggered_price | DecimalField  | Price at which the notification fired         |
| message         | TextField     | e.g. `"Price dropped to ₹3900 for DEL → BOM"` |
| notified_at     | DateTimeField | Auto-set when the notification is created     |

---

## API Endpoints

| Method | Endpoint              | Auth   | Description              |
|--------|-----------------------|--------|--------------------------|
| POST   | `/api/auth/register/` | Public | Register a new user      |
| POST   | `/api/auth/login/`    | Public | Login and get JWT tokens |

Full interactive docs at `http://localhost:8000/api/docs/` once the server is running.

---

## Setup

### Prerequisites

- Python 3.13+
- Docker (for Postgres)

### 1. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the sample file and fill in your values:

```bash
cp .env.sample .env
```

| Variable            | Description                   | Default     |
|---------------------|-------------------------------|-------------|
| `SECRET_KEY`        | Django secret key             | *(required)*|
| `DEBUG`             | Enable debug mode             | `True`      |
| `ALLOWED_HOSTS`     | Comma-separated allowed hosts | *(empty)*   |
| `POSTGRES_USER`     | Postgres username             | *(required)*|
| `POSTGRES_PASSWORD` | Postgres password             | *(required)*|
| `POSTGRES_DB`       | Postgres database name        | *(required)*|
| `POSTGRES_HOST`     | Postgres host                 | `127.0.0.1` |
| `POSTGRES_PORT`     | Postgres port                 | `5432`      |

### 4. Start Postgres with Docker Compose

```bash
docker compose up -d
```

Wait for the healthcheck to pass before running migrations:

```bash
docker compose ps
# postgres should show: Up (healthy)
```

**Stop** (data preserved in the `pgdata` volume):
```bash
docker compose down
```

**Stop and destroy all data:**
```bash
docker compose down -v
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Start the development server

```bash
python manage.py runserver
```

### 7. Open the API docs

```
http://localhost:8000/api/docs/
```

---

## Running Tests

The test suite uses Django's test runner, which creates an isolated test database automatically.

```bash
# All tests
python manage.py test tests

# Individual suites
python manage.py test tests.test_register   # register endpoint
python manage.py test tests.test_login      # login endpoint
python manage.py test tests.test_db         # Postgres connectivity + persistence (needs docker compose up)

# Verbose output
python manage.py test tests --verbosity=2
```

> `tests.test_db` requires the Postgres container to be running (`docker compose up -d`).
> `tests.test_register` and `tests.test_login` run without Docker.

---

## Project Structure

```
pulse_notify/
├── manage.py
├── docker-compose.yml
├── .env                      # local secrets — never commit
├── .env.sample               # safe template to share with the team
├── tests/
│   ├── constants.py          # shared URL fixtures
│   ├── test_register.py      # register endpoint unit tests
│   ├── test_login.py         # login endpoint unit tests
│   └── test_db.py            # Postgres connectivity + persistence tests
├── pulse_notify/
│   ├── settings.py           # all config read from env via python-dotenv
│   ├── urls.py
│   ├── middleware.py         # JSON request logging + request-ID correlation
│   └── wsgi.py
└── pulse/
    ├── models.py             # User, PriceAlert, NotificationLog
    ├── serializers.py        # RegisterSerializer
    ├── views.py              # RegisterView, LoginView
    └── urls.py
```
