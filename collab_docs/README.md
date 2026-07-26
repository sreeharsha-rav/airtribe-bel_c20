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
python manage.py test tests.test_db         # Postgres connectivity + persistence (needs docker compose up)

# Verbose output
python manage.py test tests --verbosity=2
```

> `tests.test_db` requires the Postgres container to be running (`docker compose up -d`).
> `tests.test_register` and `tests.test_login` run without Docker.

---

## Project Structure

```
collab_docs/
├── manage.py
├── docker-compose.yml
├── schema.yml                 # generated OpenAPI schema — `manage.py spectacular --file schema.yml`
├── .env                       # local secrets — never commit
├── .env.sample                # safe template to share with the team
├── tests/
│   ├── __init__.py
│   └── test_db.py             # Postgres connectivity + model/signal persistence tests
├── collab_docs/                # project package
│   ├── settings.py             # all config read from env via python-dotenv
│   ├── urls.py                 # admin, /api/schema/, /api/docs/, includes core.urls
│   ├── middleware.py           # JSON request logging + request-ID correlation
│   └── wsgi.py / asgi.py
└── core/                       # the single app — all models/views live here
    ├── models.py                # User, Workspace, WorkspaceMember, Document, DocumentVersion, Comment, Tag, AuditLog
    ├── serializers.py           # ModelSerializers + per-action serializers (summary/stats/tag-add/member-add)
    ├── views.py                 # ModelViewSets + @action endpoints (members, summary, versions, stats, tags)
    ├── signals.py                # post_save on Document → AuditLog (created/updated)
    ├── urls.py                   # DRF DefaultRouter registrations
    ├── admin.py
    ├── apps.py                   # wires signals.py into AppConfig.ready()
    └── migrations/
```

---

## Demo Walkthrough (Swagger)

A click-through script for `http://localhost:8000/api/docs/`, in the order that
naturally builds up data. Every step names the Swagger folder it's in, the body
to send, and the exact response to expect.

> **Auth note**: authentication isn't built yet (out of scope for this phase), so
> `DEFAULT_PERMISSION_CLASSES` is temporarily `AllowAny` — every endpoint below is
> reachable with no token. This will change once login/JWT issuance exists.

Start `python manage.py runserver` in a terminal you keep visible — you'll need it
for step 12.

1. **Create two users** — folder **Users**. `POST /api/users/` twice (unique
   `email`/`phone` each time) — one will be a workspace owner, one a collaborator.
   Expect `201` with a UUID `id`.

2. **Create a workspace** — folder **Workspaces**. `POST /api/workspaces/` with
   `owner` = the first user's id. Expect `201`. Then `GET /api/workspaces/{id}/members/`
   — the owner is already listed with `role: admin`, without ever calling the
   members endpoint yourself. That's the one-shot proof that `WorkspaceViewSet.
   perform_create` ran the workspace insert *and* the admin-member insert inside
   one `transaction.atomic()`.

3. **Add the second user as a member** — folder **Workspaces**.
   `POST /api/workspaces/{id}/members/` with `user` = the second user's id,
   `role: editor`. Expect `201`. Repeat the exact same call — expect **`409`**
   `{"detail": "This user is already a member of this workspace."}` (the
   `UniqueConstraint` caught via an explicit `IntegrityError` handler). A bogus
   `user` UUID → **`404`**; `role: "bogus"` → **`400`**.

4. **Show: aggregation endpoint #1** — folder **Workspaces**.
   `GET /api/workspaces/{id}/summary/` → `200` with `document_count`,
   `member_count`, `comment_count`, each computed via one `aggregate()` call
   using `Count(..., distinct=True)`.

5. **Create a document** — folder **Documents**. `POST /api/documents/` with
   `workspace`/`created_by` from steps 2–3. Expect `201`. Then
   `GET /api/documents/{id}/versions/` — one version, `version_number: 1`,
   created atomically alongside the document.

6. **Show: AuditLog written by the signal** — folder **Audit Logs**.
   `GET /api/audit-logs/?actor={created_by id}` → one entry:
   `action: "created"`, `model_name: "Document"`, `object_id` = the document's id.

7. **Update the document** — folder **Documents**. `PUT /api/documents/{id}/`
   with new `content` (same `workspace`/`created_by`). Expect `200`.
   `GET /api/documents/{id}/versions/` now shows two versions. Re-run step 6's
   query — now shows **two** entries, `created` and `updated`. The `updated` row
   is written by the same `post_save` signal, firing synchronously inside
   `perform_update`'s `transaction.atomic()` block — see step 11 for proof that
   a failure there would roll back the document edit too.

8. **Show: aggregation endpoint #2** — folder **Documents**.
   `GET /api/documents/{id}/stats/` → `version_count: 2`, `comment_count`, and
   `contributor_count` (via `values_list(...).distinct()`, correctly excluding
   any version with a null `saved_by`).

9. **Tag and filter** — folder **Documents**. `POST /api/documents/{id}/tags/`
   with `{"tag_names": ["python", "backend"]}`. Then
   `GET /api/documents/?tag=python,backend` — the document appears **once**
   (the `.distinct()` after the `tags__name__in` filter prevents the M2M join
   from duplicating the row). `GET /api/documents/?search=revised` — matches
   via `Q(title__icontains=...) | Q(content__icontains=...)`.

10. **Comments** — folder **Comments**. `POST /api/comments/` (top-level),
    then again with `parent` set to the first comment's id (a reply). Both
    `201`. `GET /api/comments/?document={id}` — the top-level comment's
    `reply_count` is now `1`. A reply whose `parent` belongs to a *different*
    document → **`400`** (`CommentSerializer.validate()`).

11. **Show: atomic rollback on failure.** There's no naturally-reachable
    "second write fails" path through the API alone for a brand-new
    workspace/document — nothing collides on a first insert. So this is
    proven directly against the real `perform_create` code, from a terminal,
    by forcing the second write to fail and checking the first write didn't
    persist:

    ```bash
    python manage.py shell
    ```
    ```python
    from unittest.mock import patch
    from core.models import User, Workspace, WorkspaceMember
    from core.serializers import WorkspaceSerializer
    from core.views import WorkspaceViewSet

    owner = User.objects.create(
        first_name="Rollback", last_name="Demo",
        email="rollback-demo@example.com", phone="9998887770",
    )
    serializer = WorkspaceSerializer(data={"name": "Rollback Demo Workspace", "owner": str(owner.id)})
    serializer.is_valid(raise_exception=True)

    view = WorkspaceViewSet()
    print(Workspace.objects.filter(name="Rollback Demo Workspace").count())  # 0

    with patch("core.models.WorkspaceMember.objects.create", side_effect=RuntimeError("simulated failure")):
        try:
            view.perform_create(serializer)
        except RuntimeError as e:
            print("caught:", e)

    print(Workspace.objects.filter(name="Rollback Demo Workspace").count())  # still 0 — rolled back
    ```

    **Verified while writing this doc**: both counts printed `0` — even though
    `serializer.save()` (the `Workspace` INSERT) ran to completion before the
    simulated failure on the second write, `transaction.atomic()` rolled it
    back. `WorkspaceMember.objects.filter(user=owner).count()` was also `0`
    afterward.

12. **Show: middleware logs.** Throughout steps 1–11, the `runserver` terminal
    printed one JSON line per request, e.g.:
    ```json
    {"timestamp": "...", "level": "INFO", "logger": "collab_docs.request", "message": "POST /api/documents/ 201 12.34ms", "request_id": "...", "method": "POST", "path": "/api/documents/", "status_code": 201, "duration_ms": 12.34, "user": "anonymous"}
    ```
    That's `RequestLoggingMiddleware` (`collab_docs/middleware.py`) — every
    request gets a correlation id (also returned as the `X-Request-ID` response
    header) and a timed log line, on success or exception alike.

---

## Why Swagger, Not Postman

Swagger UI (`/api/docs/`, served from the schema generated by `drf-spectacular`)
is the primary way to exercise this API, not Postman, for a few concrete reasons:

- **The schema and the docs can't drift apart.** `drf-spectacular` derives the
  request/response shapes straight from the actual `ModelViewSet`/serializer
  code (`@extend_schema`/`@extend_schema_view` only add summaries, tags, and
  examples on top). A Postman collection is a separate hand-maintained artifact
  that silently goes stale the moment a serializer field changes.
- **Nothing to export or share.** `schema.yml` (`manage.py spectacular --file
  schema.yml`) is a plain, committable, diffable file — anyone can regenerate
  and read it without importing a collection into a separate tool or account.
- **The folders come from the code.** The Users/Workspaces/Documents/Comments/
  Tags/Audit Logs grouping in Swagger UI is the `tags=[...]` already declared on
  each view — a Postman collection would need that structure rebuilt and
  maintained by hand, twice.
- **Good enough for this project's needs.** Postman earns its keep for chained
  multi-request flows, environment variables, and scripted pre/post-request
  logic — none of which this project currently needs; every step above is one
  request with a copy-pasted id from the previous response.
