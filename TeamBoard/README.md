# TeamBoard - B2B Knowledge Base API Platform

Given AI-powered Knowledge Base, TeamBoard provides a curated database of questions and answers covering common technical topics such as APIs, databases, cloud infrastructure, backend frameworks, and more.

This service is designed for B2B integration, allowing companies to embed the API into their own products, such as internal helpdesks, developer portals, onboarding tools, or customer-facing chatbots. When a user submits a question, the product queries the TeamBoard API to retrieve relevant answers and display them.

## Concepts Demonstrated

- **Django REST Framework**: TeamBoard is built using Django and Django REST Framework, showcasing how to create a robust API service with authentication, permissions, and serialization.
- **Swagger/OpenAPI Documentation**: The API is documented using Swagger/OpenAPI, providing an interactive interface for developers to explore and test the endpoints.

---

## Data Models

### Company

| Field        | Type           | Notes                                                       |
|--------------|----------------|-------------------------------------------------------------|
| id           | AutoField      | Primary key                                                 |
| user         | OneToOneField  | References Django's built-in `User` model; cascade deletes company profile |
| company_name | CharField      | The display name of the company                              |
| api_key      | CharField      | Unique auto-generated key used for B2B requests             |
| role         | CharField      | Choices: `admin`, `client` (defaults to `client`)            |
| created_at   | DateTimeField  | Set automatically on creation                               |

### KBEntry

| Field      | Type          | Notes                                                       |
|------------|---------------|-------------------------------------------------------------|
| id         | AutoField     | Primary key                                                 |
| question   | TextField     | The question/topic text                                     |
| answer     | TextField     | The solution/article body                                   |
| category   | CharField     | Choices: `api`, `database`, `cloud`, `framework`, `general` |
| created_at | DateTimeField | Set automatically on creation                               |

### QueryLog

| Field         | Type          | Notes                                                       |
|---------------|---------------|-------------------------------------------------------------|
| id            | AutoField     | Primary key                                                 |
| company       | ForeignKey    | References `Company`; cascade deletes query logs            |
| search_term   | CharField     | The string searched                                         |
| results_count | IntegerField  | Number of matching knowledge base results                   |
| queried_at    | DateTimeField | Set automatically on creation                               |


---

## API Endpoints

### Auth

| Method     | Endpoint                    | Description                                          |
|------------|-----------------------------|------------------------------------------------------|
| POST       | `/api/auth/register/`       | Register new company — returns username, company_name, api_key, access token |
| POST       | `/api/auth/login/`          | Login — returns access token, company_name, and api_key |

### KBEntry

| Method     | Endpoint                    | Description                                          |
|------------|-----------------------------|------------------------------------------------------|
| POST       | `/api/kb/query/`            | Send a search term and receive relevant knowledge base answer |

### Admin

| Method     | Endpoint                    | Description                                          |
|------------|-----------------------------|------------------------------------------------------|
| GET        | `/api/admin/usage-summary/` | Returns platform-wide usage statistics (Admin role required) |

---

## Setup

### Prerequisites

- Python 3.12+
- Docker (for the PostgreSQL database)
- Docker Engine running (because `docker compose` is used to start Postgres)
- PgAdmin (optional, for database management)

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

### 6. Seed the database

```bash
python manage.py seed           # skips already-existing records
python manage.py seed --clear   # wipes and re-seeds from scratch
```

### 7. Start the development server

```bash
python manage.py runserver
```

### 8. Open the API docs

```
http://localhost:8000/api/docs/
```

### 9. Test with Postman

You can easily import the API into Postman by using the `schema.yml` file. Generate it via the following command:

```bash
python manage.py spectacular --file schema.yml
```

Import this file into Postman to automatically set up the API endpoints with prefilled data and descriptions.

#### Recommended Testing Scenarios

| #  | Scenario | Endpoint | Expected |
|----|----------|----------|----------|
| 1  | Register a new company | POST `/api/auth/register/` | 201 + api_key + JWT token |
| 2  | Register with duplicate username | POST `/api/auth/register/` | 400 |
| 3  | Login with valid credentials | POST `/api/auth/login/` | 200 + JWT token |
| 4  | Login with wrong password | POST `/api/auth/login/` | 401 |
| 5  | Query KB - no token | POST `/api/kb/query/` | 401 |
| 6  | Query KB - valid token, keyword with results | POST `/api/kb/query/` | 200 + results list |
| 7  | Query KB - valid token, no matching results | POST `/api/kb/query/` | 200 + empty list, count 0 |
| 8  | Query KB - missing search field | POST `/api/kb/query/` | 400 |
| 9  | Usage summary - CLIENT token | GET `/api/admin/usage-summary/` | 403 |
| 10 | Usage summary - Admin token | GET `/api/admin/usage-summary/` | 200 + stats |
| 11 | Verify QueryLog created | *Check PGAdmin after scenarios 6 & 7* | Row exists in `querylog` table |

---

## Running Tests

The test suite runs against a temporary database. A dynamic SQLite fallback is set up in `settings.py` so the tests can run without having Postgres/Docker running.

```bash
# Run all tests in the api app
python manage.py test api
```

