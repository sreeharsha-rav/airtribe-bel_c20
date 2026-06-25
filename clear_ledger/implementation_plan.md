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

## Design Decisions

- **Category vs Label**: Categories are structural (used for budgets and reports); Labels are ad-hoc free-form tags. Both serve distinct purposes.
- **`Transaction.amount` always positive**: `transaction_type` (`credit`/`debit`) carries the sign semantics — avoids sign-error bugs.
- **`Budget.unique_together`** on `(user, category, month, year)` enforces one budget cap per category per month.
- **`UserProfile` currency** stores user preference for display; `Account.currency` stores the actual account currency — needed for multi-currency support.
- **Reports** are computed views (aggregation queries), not stored models — they use `django_filters` for query params and DRF's response layer.