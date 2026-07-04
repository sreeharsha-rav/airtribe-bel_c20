# TeamBoard - B2B Knowledge Base API Platform

Given AI-powered Knowledge Base, TeamBoard provides a curated database of questions and answers covering common technical topics such as APIs, databases, cloud infrastructure, backend frameworks, and more.

This service is designed for B2B integration, allowing companies to embed the API into their own products, such as internal helpdesks, developer portals, onboarding tools, or customer-facing chatbots. When a user submits a question, the product queries the TeamBoard API to retrieve relevant answers and display them.

## Concepts Demonstrated

- **Django REST Framework**: TeamBoard is built using Django and Django REST Framework, showcasing how to create a robust API service with authentication, permissions, and serialization.
- **Swagger/OpenAPI Documentation**: The API is documented using Swagger/OpenAPI, providing an interactive interface for developers to explore and test the endpoints.

---

## Data Models

### Company

### KBEntry

### QueryModel

---

## API Endpoints

### Auth

| Method     | Endpoint                    | Description                                          |
|------------|-----------------------------|------------------------------------------------------|
| POST       | `/api/auth/register/`       | Register — returns access + refresh tokens immediately |
| POST       | `/api/auth/login/`          | Login — returns access + refresh + role + email      |

### KBEntry

| Method     | Endpoint                    | Description                                          |
|------------|-----------------------------|------------------------------------------------------|
| POST       | `/api/kb/query/`            | Send a search term and receive relevant knowledge base answer |

---

## Setup

### Prerequisites

- Docker (for the PostgreSQL database)

### Installation

1. Install dependencies (if not setup in root using `uv` env):
```bash
python -m venv venv

source venv/bin/activate  # On Windows use `venv\Scripts\activate`

pip install -r requirements.txt
```

2. Create your `.env` file from the sample and adjust values if needed:
```bash
cp .env.sample .env   # On Windows use `copy .env.sample .env`
```

3. Start the PostgreSQL container:
```bash
docker compose up -d
```
This starts a `postgres:16-alpine` container named `teamboard_postgres`, using the `DB_*` credentials from `.env` and persisting data in the `teamboard_postgres_data` Docker volume.

4. Apply migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Run the development server:
```bash
python manage.py runserver
```

6. Open interactive API docs at `http://127.0.0.1:8000/api/docs`

### Database container management

```bash
docker compose ps          # check container/health status
docker compose logs -f db  # tail Postgres logs
docker compose down        # stop the container (keeps data volume)
docker compose down -v     # stop and wipe the data volume
```
