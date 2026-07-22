# CollabDocs - Collaborative Document Platform

CollabDocs is a backend REST API for a simplified collaborative document platform — create workspaces, invite collaborators, write and version documents, leave comments, and control access with role-based permissions.

## Data Models

### User

| Field      | Type          | Notes                                            |
|------------|---------------|---------------------------------------------------|
| id         | UUIDField     | Primary key; `uuid.uuid4`, `editable=False`        |
| first_name | CharField(50) |                                                     |
| last_name  | CharField(50) |                                                     |
| email      | CharField(254)| `unique=True` — use `CharField`, not `EmailField`  |
| phone      | CharField(15) | `unique=True`                                      |
| created_at | DateTimeField | `auto_now_add=True`                                |

### Workspace *(N per User, as owner)*

| Field      | Type          | Notes                                                                |
|------------|---------------|-----------------------------------------------------------------------|
| id         | UUIDField     | Primary key; `uuid.uuid4`, `editable=False`                           |
| name       | CharField(255)|                                                                        |
| owner      | ForeignKey    | References `User`; `on_delete=CASCADE`. Owner is also added as a `WorkspaceMember` with `role=admin` |
| is_active  | BooleanField  | `default=True`                                                        |
| created_at | DateTimeField | `auto_now_add=True`                                                   |

> Workspace creation adds the owner as a `WorkspaceMember` with `role=admin` inside a single `transaction.atomic()`.

### WorkspaceMember *(N per Workspace, N per User)*

| Field     | Type          | Notes                                        |
|-----------|---------------|-----------------------------------------------|
| id        | UUIDField     | Primary key; `uuid.uuid4`, `editable=False`    |
| workspace | ForeignKey    | References `Workspace`; `on_delete=CASCADE`    |
| user      | ForeignKey    | References `User`; `on_delete=CASCADE`         |
| role      | CharField     | `TextChoices`: `admin`, `editor`, `viewer`     |
| joined_at | DateTimeField | `auto_now_add=True`                            |

> `Meta.constraints` includes a `UniqueConstraint` on `(workspace, user)`:
> ```python
> class Meta:
>     constraints = [
>         models.UniqueConstraint(fields=['workspace', 'user'], name='unique_workspace_member')
>     ]
> ```

### Document *(N per Workspace)*

| Field      | Type          | Notes                                        |
|------------|---------------|-----------------------------------------------|
| id         | UUIDField     | Primary key; `uuid.uuid4`, `editable=False`    |
| title      | CharField(255)|                                                 |
| content    | TextField     |                                                 |
| workspace  | ForeignKey    | References `Workspace`; `on_delete=CASCADE`    |
| created_by | ForeignKey    | References `User`; `on_delete=SET_NULL`, `null=True` |
| status     | CharField     | `TextChoices`: `draft`, `published`, `archived`|
| updated_at | DateTimeField | `auto_now=True`                                |

> Every save must create a new `DocumentVersion` inside the same `transaction.atomic()` block.

### DocumentVersion *(N per Document)*

| Field         | Type               | Notes                                          |
|---------------|--------------------|--------------------------------------------------|
| id            | UUIDField          | Primary key; `uuid.uuid4`, `editable=False`       |
| document      | ForeignKey         | References `Document`; `on_delete=CASCADE`        |
| content       | TextField          | Snapshot of content at save time                  |
| version_number| PositiveIntegerField| Computed as `Document.versions.count() + 1` inside the atomic block (per-document numbering, no global counter) |
| saved_by      | ForeignKey         | References `User`; `on_delete=SET_NULL`, `null=True` |
| saved_at      | DateTimeField      | `auto_now_add=True`                               |

### Comment *(N per Document, self-referential)*

| Field      | Type          | Notes                                                                                  |
|------------|---------------|-------------------------------------------------------------------------------------------|
| id         | UUIDField     | Primary key; `uuid.uuid4`, `editable=False`                                                |
| document   | ForeignKey    | References `Document`; `on_delete=CASCADE`                                                 |
| author     | ForeignKey    | References `User`; `on_delete=SET_NULL`, `null=True`                                       |
| content    | TextField     |                                                                                             |
| parent     | ForeignKey    | Self-referential; `null=True, blank=True, on_delete=SET_NULL, related_name='replies'`. A comment with no parent is a top-level comment |
| created_at | DateTimeField | `auto_now_add=True`                                                                        |

### Tag *(M2M with Document)*

| Field     | Type              | Notes                                                                                    |
|-----------|-------------------|---------------------------------------------------------------------------------------------|
| id        | UUIDField         | Primary key; `uuid.uuid4`, `editable=False`                                                  |
| name      | CharField(100)    | `unique=True`                                                                                |
| documents | ManyToManyField   | `ManyToManyField(Document, related_name='tags', blank=True)` — declared on `Tag`, not `Document` |

> Django creates the join table automatically. Add tags via `tag.documents.add(doc)` or `doc.tags.add(tag)`. Filter docs by tag with `Document.objects.filter(tags__name='python')`.

### AuditLog

| Field      | Type          | Notes                                                |
|------------|---------------|---------------------------------------------------------|
| id         | UUIDField     | Primary key; `uuid.uuid4`, `editable=False`               |
| actor      | ForeignKey    | References `User`; `on_delete=SET_NULL`, `null=True`       |
| action     | CharField(50) | e.g. `'created'`, `'updated'`                              |
| model_name | CharField(100)| e.g. `'Document'`                                          |
| object_id  | CharField(100)| UUID as string                                             |
| timestamp  | DateTimeField | `auto_now_add=True`                                        |

> Written automatically via a `post_save` signal on `Document`. Use `instance._state.adding` to distinguish created vs. updated.

---

## API Endpoints

### Users

| Method | Endpoint          | Description       | Concept tested                                |
|--------|-------------------|--------------------|------------------------------------------------|
| POST   | `/api/users/`     | Create a user      | `ModelViewSet`, `ModelSerializer`, validation    |
| GET    | `/api/users/{id}/`| Get user by ID      | `UUIDField` PK, serializer response              |

### Workspaces

| Method | Endpoint                          | Description                                    | Concept tested                                 |
|--------|-----------------------------------|--------------------------------------------------|---------------------------------------------------|
| POST   | `/api/workspaces/`                | Create workspace + auto-add owner as admin member | `transaction.atomic()`, override `create()`        |
| GET    | `/api/workspaces/{id}/`           | Get workspace with member count                   | `annotate()`, `Count`                              |
| POST   | `/api/workspaces/{id}/members/`   | Add a member with a role                          | FK, `UniqueConstraint` handling, custom validation |
| GET    | `/api/workspaces/{id}/members/`   | List all members with their roles                 | `select_related`, serializer nesting               |
| GET    | `/api/workspaces/{id}/summary/`   | Doc count, member count, total comments           | `@action`, `aggregate()`, `annotate()`, `Count`     |

### Documents

| Method | Endpoint                         | Description                                         | Concept tested                                  |
|--------|-----------------------------------|--------------------------------------------------------|-----------------------------------------------------|
| POST   | `/api/documents/`                 | Create document + first version (atomic)               | `transaction.atomic()`, `version_number` logic       |
| PUT    | `/api/documents/{id}/`            | Update document content — saves a new version           | `transaction.atomic()`, override `update()`           |
| GET    | `/api/documents/`                 | List docs — filter by workspace, status, tag name; search title | `Q` objects, query params, `filter()`, `__icontains` |
| GET    | `/api/documents/{id}/versions/`   | All versions of a document in order                     | `filter()`, `order_by()`, FK reverse lookup           |
| GET    | `/api/documents/{id}/stats/`      | Version count, comment count, contributor count         | `@action`, `aggregate()`, `annotate()`, `Count`       |
| POST   | `/api/documents/{id}/tags/`       | Add one or more tags to a document                      | `@action`, `ManyToManyField.add()`                    |

### Comments

| Method | Endpoint                          | Description                            | Concept tested                                          |
|--------|-----------------------------------|-------------------------------------------|-------------------------------------------------------------|
| POST   | `/api/comments/`                  | Add a top-level comment or a reply         | Self-referential FK, `SerializerMethodField`, validation      |
| GET    | `/api/comments/?document={id}`    | List all comments for a document (threaded)| `filter()`, `select_related`, query params                    |

### Tags & Audit Logs

| Method | Endpoint            | Description                                  | Concept tested                             |
|--------|----------------------|-------------------------------------------------|-----------------------------------------------|
| POST   | `/api/tags/`          | Create a tag                                    | `ModelSerializer`, unique constraint handling   |
| GET    | `/api/audit-logs/`    | Audit logs filtered by actor ID and date range  | `filter()`, `__gte`, `__lte`, query params      |

Full interactive docs at `http://localhost:8000/api/docs/` once the server is running.

---

## Setup

### Pre-Requisites

- Python 3.12+
- Docker (for Postgres)
- Docker Engine running (because `docker compose` is used to start Postgres)
- PgAdmin (optional, for database management)
- Postman

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
# TODO
```
