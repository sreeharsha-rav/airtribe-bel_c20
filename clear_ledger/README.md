# ClearLedger

A personal finance ledger API built with Django REST Framework. Users register with JWT-based auth, link bank accounts, categorize and tag transactions, set monthly budgets per category, and query spending reports. The project demonstrates custom user models, JWT authentication with token rotation, nested serializers, and OpenAPI documentation.

## Concepts Demonstrated

- **Custom AbstractUser** — `User` extends `AbstractUser` with a `role` field (`owner`, `accountant`, `viewer`); `AUTH_USER_MODEL` set before first migration
- **JWT Authentication** — `djangorestframework-simplejwt` for stateless access tokens (15 min) + refresh tokens (7 days); `role` and `email` embedded in both JWT payload and response body via a custom `TokenObtainPairSerializer`
- **Token blacklisting** — `rest_framework_simplejwt.token_blacklist` + `ROTATE_REFRESH_TOKENS` enables server-side logout and automatic rotation on every refresh
- **ModelSerializer** — `RegisterSerializer`, `ProfileSerializer`; `extra_kwargs` for write-only fields; `read_only_fields`; `create_user()` for password hashing
- **Nested serializers** — `ProfileSerializer` composes `UserSerializer` as a nested read-only field instead of `source=` traversal
- **Custom token serializer** — `CustomTokenObtainPairSerializer` overrides `get_token()` to embed claims in the JWT payload and `validate()` to surface them in the response body
- **Generic views** — `generics.CreateAPIView` (register), `generics.RetrieveUpdateAPIView` (profile), `APIView` (logout), `TokenObtainPairView` (login)
- **OneToOneField / ForeignKey / ManyToManyField** — `UserProfile` (1:1), `Account` / `Transaction` / `Budget` (1:N), `Transaction ↔ Label` (M:N through `TransactionLabel`)
- **`unique_together`** — `Budget(user, category, month, year)` and `TransactionLabel(transaction, label)`
- **`django-filter`** — query-param filtering on list endpoints
- **OpenAPI / Swagger** — `drf-spectacular` generates a fully annotated schema; `@extend_schema` / `@extend_schema_view` on every auth view; `inline_serializer` for token response shapes; `COMPONENT_SPLIT_REQUEST` separates read/write schemas

---

## Data Models

### User *(extends AbstractUser)*

| Field      | Type      | Notes                                             |
|------------|-----------|---------------------------------------------------|
| id         | AutoField | Primary key                                       |
| username   | CharField | Inherited from `AbstractUser`                     |
| email      | EmailField | Inherited from `AbstractUser`                    |
| password   | CharField | Hashed via `create_user()`; write-only in API     |
| role       | CharField | Choices: `owner`, `accountant`, `viewer`; default `owner` |

### UserProfile *(1:1 with User)*

| Field               | Type          | Notes                                    |
|---------------------|---------------|------------------------------------------|
| id                  | AutoField     | Primary key                              |
| user                | OneToOneField | References `User`; cascade deletes profile |
| currency_preference | CharField(3)  | Display currency preference; default `USD` |
| created_at          | DateTimeField | Set automatically on creation            |
| updated_at          | DateTimeField | Updated automatically on save            |

### Account *(N per User)*

| Field        | Type          | Notes                                                            |
|--------------|---------------|------------------------------------------------------------------|
| id           | AutoField     | Primary key                                                      |
| user         | ForeignKey    | References `User`; cascade deletes accounts                      |
| name         | CharField     | e.g. "HDFC Savings"                                              |
| account_type | CharField     | Choices: `checking`, `savings`, `credit`, `investment`           |
| currency     | CharField(3)  | Account currency; default `USD`                                  |
| balance      | DecimalField  | Current balance (12 digits, 2 decimal places)                    |
| is_active    | BooleanField  | Soft-deactivation flag; default `True`                           |
| created_at   | DateTimeField | Set automatically on creation                                    |

### Category *(N per User)*

| Field       | Type          | Notes                                          |
|-------------|---------------|------------------------------------------------|
| id          | AutoField     | Primary key                                    |
| user        | ForeignKey    | References `User`; cascade deletes categories  |
| name        | CharField     | e.g. "Groceries"                               |
| description | CharField     | Optional; max 255 chars                        |
| created_at  | DateTimeField | Set automatically on creation                  |

### Transaction *(N per Account)*

| Field            | Type          | Notes                                                     |
|------------------|---------------|-----------------------------------------------------------|
| id               | AutoField     | Primary key                                               |
| account          | ForeignKey    | References `Account`; cascade deletes transactions        |
| category         | ForeignKey    | References `Category`; nullable; `SET_NULL` on delete     |
| amount           | DecimalField  | Always positive — `transaction_type` carries sign semantics |
| transaction_type | CharField     | Choices: `credit`, `debit`                                |
| description      | CharField     | Max 255 chars                                             |
| date             | DateField     | Transaction date                                          |
| labels           | ManyToManyField | References `Label` through `TransactionLabel`           |
| created_at       | DateTimeField | Set automatically on creation                             |
| updated_at       | DateTimeField | Updated automatically on save                             |

### Label *(N per User)*

| Field      | Type          | Notes                                     |
|------------|---------------|-------------------------------------------|
| id         | AutoField     | Primary key                               |
| user       | ForeignKey    | References `User`; cascade deletes labels |
| name       | CharField(50) | e.g. "tax-deductible"                     |
| color      | CharField(7)  | Hex color code; optional                  |
| created_at | DateTimeField | Set automatically on creation             |

### TransactionLabel *(M:N through table)*

| Field       | Type          | Notes                                               |
|-------------|---------------|-----------------------------------------------------|
| id          | AutoField     | Primary key                                         |
| transaction | ForeignKey    | References `Transaction`; cascade deletes           |
| label       | ForeignKey    | References `Label`; cascade deletes                 |
| created_at  | DateTimeField | Set automatically on creation                       |
|             | unique_together | `(transaction, label)` — no duplicate tagging     |

### Budget *(N per User)*

| Field      | Type                  | Notes                                              |
|------------|-----------------------|----------------------------------------------------|
| id         | AutoField             | Primary key                                        |
| user       | ForeignKey            | References `User`; cascade deletes budgets         |
| category   | ForeignKey            | References `Category`; cascade deletes             |
| amount     | DecimalField          | Budget cap for the month                           |
| month      | PositiveSmallIntegerField | 1–12                                           |
| year       | PositiveSmallIntegerField | e.g. 2026                                      |
| created_at | DateTimeField         | Set automatically on creation                      |
| updated_at | DateTimeField         | Updated automatically on save                      |
|            | unique_together       | `(user, category, month, year)` — one cap per category per month |

---

## Entity Relationships

```
User ──1:1──▶ UserProfile
User ──1:N──▶ Account ──1:N──▶ Transaction ──N:M──▶ Label
                                    │
                                    ▼ (FK, nullable)
User ──1:N──▶ Category ◀──────────────────────────────
                   │
User ──1:N──▶ Budget (category + month + year)
```

---

## JWT Authentication Flow

```
Register ──▶ returns access + refresh tokens immediately (no separate login)
Login    ──▶ username + password → access + refresh + role + email
Refresh  ──▶ POST refresh token → new access + new refresh (old refresh blacklisted)
Logout   ──▶ POST refresh token → blacklisted; access token expires naturally (15 min)
```

Both the **JWT payload** and the **response body** carry `role` and `email` — the client can read them from the token itself without an extra profile API call.

---

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Apply migrations:
```bash
python manage.py migrate
```

3. Run the development server:
```bash
python manage.py runserver
```

4. Open interactive API docs at `http://127.0.0.1:8000/api/docs`

---

## Testing

Unit and API tests for the `accounts` app (models, serializers, and all auth endpoints) live under `accounts/tests/` as one module per concern:

| Module | Covers |
|---|---|
| `test_models.py` | `User`, `UserProfile` model behavior |
| `test_serializers.py` | `RegisterSerializer`, `CustomTokenObtainPairSerializer`, `UserSerializer`, `ProfileSerializer` |
| `test_register_api.py` | `POST /api/auth/register/` |
| `test_login_api.py` | `POST /api/auth/login/` |
| `test_token_refresh_api.py` | `POST /api/auth/token/refresh/` |
| `test_logout_api.py` | `POST /api/auth/logout/` |
| `test_profile_api.py` | `GET`/`PATCH /api/auth/profile/` |

Run the full suite:
```bash
python manage.py test accounts
```

Run a single module or test case:
```bash
python manage.py test accounts.tests.test_login_api
python manage.py test accounts.tests.test_login_api.LoginAPITests.test_login_success_returns_role_and_email
```

Run with verbose per-test output:
```bash
python manage.py test accounts -v 2
```

See [TEST_REPORT.md](TEST_REPORT.md) for a full breakdown of what each test verifies and current coverage gaps.

---

## API Endpoints

### Auth

| Method     | Endpoint                    | Description                                          |
|------------|-----------------------------|------------------------------------------------------|
| POST       | `/api/auth/register/`       | Register — returns access + refresh tokens immediately |
| POST       | `/api/auth/login/`          | Login — returns access + refresh + role + email      |
| POST       | `/api/auth/token/refresh/`  | Rotate refresh token, get new access token           |
| POST       | `/api/auth/logout/`         | Blacklist refresh token                              |
| GET        | `/api/auth/profile/`        | Get current user's profile                           |
| PATCH      | `/api/auth/profile/`        | Update currency preference                           |

### Accounts

| Method       | Endpoint               | Description                    |
|--------------|------------------------|--------------------------------|
| GET          | `/api/accounts/`       | List user's linked accounts    |
| POST         | `/api/accounts/`       | Link a new account             |
| GET          | `/api/accounts/{id}/`  | Retrieve account               |
| PATCH        | `/api/accounts/{id}/`  | Update account                 |
| DELETE       | `/api/accounts/{id}/`  | Unlink account                 |

### Categories

| Method       | Endpoint                  | Description                 |
|--------------|---------------------------|-----------------------------|
| GET          | `/api/categories/`        | List user's categories      |
| POST         | `/api/categories/`        | Create category             |
| GET          | `/api/categories/{id}/`   | Retrieve category           |
| PATCH        | `/api/categories/{id}/`   | Update category             |
| DELETE       | `/api/categories/{id}/`   | Delete category             |

### Transactions

| Method       | Endpoint                                    | Description                                   |
|--------------|---------------------------------------------|-----------------------------------------------|
| GET          | `/api/transactions/`                        | List (filter by account, category, date range) |
| POST         | `/api/transactions/`                        | Create transaction                            |
| GET          | `/api/transactions/{id}/`                   | Retrieve transaction                          |
| PATCH        | `/api/transactions/{id}/`                   | Update transaction                            |
| DELETE       | `/api/transactions/{id}/`                   | Delete transaction                            |
| POST         | `/api/transactions/{id}/labels/`            | Tag transaction with a label                  |
| DELETE       | `/api/transactions/{id}/labels/{label_id}/` | Remove label from transaction                 |

### Labels

| Method       | Endpoint             | Description          |
|--------------|----------------------|----------------------|
| GET          | `/api/labels/`       | List user's labels   |
| POST         | `/api/labels/`       | Create label         |
| GET          | `/api/labels/{id}/`  | Retrieve label       |
| PATCH        | `/api/labels/{id}/`  | Update label         |
| DELETE       | `/api/labels/{id}/`  | Delete label         |

### Budgets

| Method       | Endpoint              | Description                          |
|--------------|-----------------------|--------------------------------------|
| GET          | `/api/budgets/`       | List budgets (filter by month/year)  |
| POST         | `/api/budgets/`       | Create budget                        |
| GET          | `/api/budgets/{id}/`  | Retrieve budget                      |
| PATCH        | `/api/budgets/{id}/`  | Update budget                        |
| DELETE       | `/api/budgets/{id}/`  | Delete budget                        |

### Reports

| Method | Endpoint                        | Description                                        |
|--------|---------------------------------|----------------------------------------------------|
| GET    | `/api/reports/spending/`        | Spending totals by category (`?month=&year=`)      |
| GET    | `/api/reports/budget-vs-actual/`| Budget cap vs actual spend (`?month=&year=`)       |

---

## Swagger / OpenAPI Docs

Interactive API documentation is served automatically via `drf-spectacular`.

| URL                              | Description                                    |
|----------------------------------|------------------------------------------------|
| `/api/schema/swagger-ui/`        | Swagger UI — browse and try all endpoints live |
| `/api/schema/`                   | Raw OpenAPI 3 schema (JSON/YAML, for tooling)  |

All auth endpoints are annotated with `@extend_schema` / `@extend_schema_view` providing:
- Business-area **tags** (`Auth`)
- Human-readable **summaries** and **descriptions**
- Typed **request** and **response** schemas via `inline_serializer` for token shapes
- **Error response** descriptions for `400`, `401`

### Generate the schema YAML

```bash
# Generate and validate (fails on any warnings)
python manage.py spectacular --color --file schema.yaml --validate --fail-on-warn

# Generate without strict validation
python manage.py spectacular --file schema.yaml
```

---

## Sample Workflow

### 1. Register

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "secret123"}'
```

```json
{
  "user": { "id": 1, "username": "alice", "email": "alice@example.com", "role": "owner" },
  "access": "<access_token>",
  "refresh": "<refresh_token>"
}
```

### 2. Login

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret123"}'
```

```json
{
  "access": "<access_token>",
  "refresh": "<refresh_token>",
  "role": "owner",
  "email": "alice@example.com"
}
```

### 3. Get profile

```bash
curl http://127.0.0.1:8000/api/auth/profile/ \
  -H "Authorization: Bearer <access_token>"
```

```json
{
  "user": { "username": "alice", "email": "alice@example.com", "role": "owner" },
  "currency_preference": "USD",
  "created_at": "2026-07-04T10:00:00Z",
  "updated_at": "2026-07-04T10:00:00Z"
}
```

### 4. Update currency preference

```bash
curl -X PATCH http://127.0.0.1:8000/api/auth/profile/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"currency_preference": "EUR"}'
```

```json
{
  "user": { "username": "alice", "email": "alice@example.com", "role": "owner" },
  "currency_preference": "EUR",
  "created_at": "2026-07-04T10:00:00Z",
  "updated_at": "2026-07-04T10:05:00Z"
}
```

### 5. Rotate the access token

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```

```json
{
  "access": "<new_access_token>",
  "refresh": "<new_refresh_token>"
}
```

The old refresh token is now blacklisted. Using it again returns `401`.

### 6. Logout

```bash
curl -X POST http://127.0.0.1:8000/api/auth/logout/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```

Returns `204 No Content`. The refresh token is blacklisted. The access token expires naturally after its remaining lifetime.