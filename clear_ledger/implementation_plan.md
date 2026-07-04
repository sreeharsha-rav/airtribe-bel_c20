# ClearLedger — Implementation Plan

## Django Apps (3)

| App | Responsibility |
|---|---|
| `accounts` | Bank account linking, user profile & currency preferences |
| `transactions` | Transactions, categories, labels, M2M tagging |
| `budgets` | Monthly budget limits per category, spending reports |

---

## Models & Database Schema

### `accounts` app

#### `UserProfile` — extends Django's `User` (1:1)

| Field | Type | Notes |
|---|---|---|
| `user` | OneToOneField → User | `on_delete=CASCADE` |
| `currency_preference` | CharField(3) | default `'USD'` |
| `created_at` | DateTimeField | auto |
| `updated_at` | DateTimeField | auto |

#### `Account` — bank accounts linked to a user (User 1:N Account)

| Field | Type | Notes |
|---|---|---|
| `user` | ForeignKey → User | `on_delete=CASCADE` |
| `name` | CharField(100) | e.g. "HDFC Savings" |
| `bank_name` | CharField(100) | |
| `account_type` | CharField | choices: `checking`, `savings`, `credit`, `investment` |
| `currency` | CharField(3) | default `'USD'` |
| `balance` | DecimalField(12,2) | current balance |
| `is_active` | BooleanField | default `True` |
| `created_at` | DateTimeField | auto |

---

### `transactions` app

#### `Category` — user-defined spending categories

| Field | Type | Notes |
|---|---|---|
| `user` | ForeignKey → User | `on_delete=CASCADE` |
| `name` | CharField(100) | e.g. "Groceries" |
| `description` | CharField(255) | optional |
| `created_at` | DateTimeField | auto |

#### `Transaction` — financial entries on an account (Account 1:N Transaction)

| Field | Type | Notes |
|---|---|---|
| `account` | ForeignKey → Account | `on_delete=CASCADE` |
| `category` | ForeignKey → Category | `null=True`, `on_delete=SET_NULL` |
| `amount` | DecimalField(12,2) | always positive |
| `transaction_type` | CharField | choices: `credit`, `debit` |
| `description` | CharField(255) | |
| `date` | DateField | transaction date |
| `labels` | ManyToManyField → Label | through `TransactionLabel` |
| `created_at` | DateTimeField | auto |
| `updated_at` | DateTimeField | auto |

#### `Label` — user-defined free-form tags

| Field | Type | Notes |
|---|---|---|
| `user` | ForeignKey → User | `on_delete=CASCADE` |
| `name` | CharField(50) | e.g. "tax-deductible" |
| `color` | CharField(7) | hex color, optional |
| `created_at` | DateTimeField | auto |

#### `TransactionLabel` — M2M through table (Transaction M:N Label)

| Field | Type | Notes |
|---|---|---|
| `transaction` | ForeignKey → Transaction | `on_delete=CASCADE` |
| `label` | ForeignKey → Label | `on_delete=CASCADE` |
| `created_at` | DateTimeField | auto |
| | `unique_together` | `(transaction, label)` |

---

### `budgets` app

#### `Budget` — monthly limit per category per user

| Field | Type | Notes |
|---|---|---|
| `user` | ForeignKey → User | `on_delete=CASCADE` |
| `category` | ForeignKey → Category | `on_delete=CASCADE` |
| `amount` | DecimalField(12,2) | budget cap |
| `month` | PositiveSmallIntegerField | 1–12 |
| `year` | PositiveSmallIntegerField | e.g. 2026 |
| `created_at` | DateTimeField | auto |
| `updated_at` | DateTimeField | auto |
| | `unique_together` | `(user, category, month, year)` |

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

## API Endpoints

### Auth / Profile

| Method | Endpoint | Action |
|---|---|---|
| `POST` | `/api/auth/register/` | Register new user |
| `POST` | `/api/auth/login/` | Obtain token |
| `POST` | `/api/auth/logout/` | Invalidate token |
| `GET/PATCH` | `/api/auth/profile/` | Get or update UserProfile |

### Accounts

| Method | Endpoint | Action |
|---|---|---|
| `GET/POST` | `/api/accounts/` | List / link new account |
| `GET/PATCH/DELETE` | `/api/accounts/{id}/` | Retrieve / update / unlink |

### Categories

| Method | Endpoint | Action |
|---|---|---|
| `GET/POST` | `/api/categories/` | List / create |
| `GET/PATCH/DELETE` | `/api/categories/{id}/` | Retrieve / update / delete |

### Transactions

| Method | Endpoint | Action |
|---|---|---|
| `GET/POST` | `/api/transactions/` | List (filterable by account, category, date range) / create |
| `GET/PATCH/DELETE` | `/api/transactions/{id}/` | Retrieve / update / delete |
| `POST` | `/api/transactions/{id}/labels/` | Tag transaction with a label |
| `DELETE` | `/api/transactions/{id}/labels/{label_id}/` | Remove label from transaction |

### Labels

| Method | Endpoint | Action |
|---|---|---|
| `GET/POST` | `/api/labels/` | List / create |
| `GET/PATCH/DELETE` | `/api/labels/{id}/` | Retrieve / update / delete |

### Budgets

| Method | Endpoint | Action |
|---|---|---|
| `GET/POST` | `/api/budgets/` | List / create (filterable by month/year) |
| `GET/PATCH/DELETE` | `/api/budgets/{id}/` | Retrieve / update / delete |

### Reports

| Method | Endpoint | Action |
|---|---|---|
| `GET` | `/api/reports/spending/` | Spending totals by category (`?month=&year=`) |
| `GET` | `/api/reports/budget-vs-actual/` | Budget cap vs actual spend (`?month=&year=`) |

---

## Authentication — JWT

### Custom User Model

`accounts.User` extends `AbstractUser` with a `role` field:

| Role | Value | Purpose |
|---|---|---|
| Owner | `owner` | Full read/write access to all resources |
| Accountant | `accountant` | Can manage transactions and budgets |
| Viewer | `viewer` | Read-only access |

`AUTH_USER_MODEL = 'accounts.User'` must be set before the first migration.

### JWT Configuration (`SIMPLE_JWT`)

| Setting | Value | Reason |
|---|---|---|
| `ACCESS_TOKEN_LIFETIME` | 15 minutes | Short-lived; stateless, cannot be revoked |
| `REFRESH_TOKEN_LIFETIME` | 7 days | Long-lived; stored server-side for blacklisting |
| `ROTATE_REFRESH_TOKENS` | `True` | Issues a new refresh token on every `/token/refresh/` call |
| `BLACKLIST_AFTER_ROTATION` | `True` | Old refresh token is invalidated after rotation |
| `UPDATE_LAST_LOGIN` | `True` | Keeps `User.last_login` current |
| `ALGORITHM` | `HS256` | HMAC-SHA256 symmetric signing |
| `AUTH_HEADER_TYPES` | `Bearer` | Standard `Authorization: Bearer <token>` header |

`rest_framework_simplejwt.token_blacklist` must be in `INSTALLED_APPS` for blacklisting to work.

### Custom Token Serializer (`CustomTokenObtainPairSerializer`)

Extends `TokenObtainPairSerializer` to embed `role` and `email` in:
- The **JWT payload** (via `get_token()`) — readable by the client without an extra API call
- The **login response body** (via `validate()`) — convenient for immediate use after login

```
POST /api/auth/login/
→ { access, refresh, role, email }
   JWT payload: { user_id, role, email, exp, ... }
```

### Auth Flow

```
Register ──▶ returns access + refresh tokens immediately
Login    ──▶ validates credentials → returns access + refresh tokens
Refresh  ──▶ POST refresh token → returns new access + new refresh (old refresh blacklisted)
Logout   ──▶ POST refresh token → blacklisted; access token expires naturally (15 min)
```

### View Design Choices

| View | Base Class | Why |
|---|---|---|
| `RegisterView` | `generics.CreateAPIView` | Single POST operation; returns tokens in custom response |
| `LoginView` | `TokenObtainPairView` | simplejwt base; swaps in custom serializer only |
| `LogoutView` | `APIView` | No model/queryset; just calls `token.blacklist()` |
| `ProfileView` | `generics.RetrieveUpdateAPIView` | GET + PATCH on a single user-scoped object |

`ModelViewSet` is intentionally not used for auth — each endpoint does something structurally different (not standard CRUD on one resource). ViewSets are appropriate for `accounts`, `transactions`, `budgets`, and `categories`.

---

## Design Decisions

- **Category vs Label**: Categories are structural (used for budgets and reports); Labels are ad-hoc free-form tags. Both serve distinct purposes.
- **`Transaction.amount` always positive**: `transaction_type` (`credit`/`debit`) carries the sign semantics — avoids sign-error bugs.
- **`Budget.unique_together`** on `(user, category, month, year)` enforces one budget cap per category per month.
- **`UserProfile` currency** stores user preference for display; `Account.currency` stores the actual account currency — needed for multi-currency support.
- **Reports** are computed views (aggregation queries), not stored models — they use `django_filters` for query params and DRF's response layer.
- **JWT over session auth**: Stateless access tokens suit API clients (mobile, SPA). Refresh token rotation + blacklisting provides logout support without sacrificing statelessness for the access token.