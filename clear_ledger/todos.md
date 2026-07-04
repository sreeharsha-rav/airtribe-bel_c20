# ClearLedger — TODOs

## Setup
- [x] Register `accounts`, `transactions`, `budgets` in `settings.py` `INSTALLED_APPS`
- [x] Configure `rest_framework`, `django_filters`, `drf_spectacular` in `INSTALLED_APPS`
- [ ] Wire up root `urls.py` with API and schema endpoints

## Authentication
- [x] Create custom `User` model
- [x] Create `UserProfile` model
- [x] Create serializers for `User` and `UserProfile`
- [x] Create views for register, login, logout, profile
- [x] Setup JWT authentication with `rest_framework_simplejwt`

## `accounts` app
- [x] Create `UserProfile` model
- [x] Create `Account` model
- [ ] Create serializers for `UserProfile` and `Account`
- [ ] Create views (register, login, logout, profile, accounts CRUD)
- [ ] Write URL patterns for `accounts` app
- [ ] Run `makemigrations accounts` and `migrate`

## `transactions` app
- [x] Create app: `python manage.py startapp transactions`
- [x] Create `Category` model
- [x] Create `Label` model
- [x] Create `TransactionLabel` model (M2M through)
- [x] Create `Transaction` model
- [ ] Create serializers for all models
- [ ] Create views (categories, labels, transactions CRUD + label tagging)
- [ ] Write URL patterns for `transactions` app
- [ ] Run `makemigrations transactions` and `migrate`

## `budgets` app
- [x] Create app: `python manage.py startapp budgets`
- [x] Create `Budget` model
- [ ] Create serializers for `Budget`
- [ ] Create views (budgets CRUD)
- [ ] Write URL patterns for `budgets` app
- [ ] Run `makemigrations budgets` and `migrate`

## Reports
- [ ] Create spending report view (`/api/reports/spending/`)
- [ ] Create budget-vs-actual report view (`/api/reports/budget-vs-actual/`)
- [ ] Add `django_filters` filter classes for month/year query params

## Final
- [ ] Run full `migrate`
- [ ] Add admin registrations for all models
- [ ] Test all endpoints via `/api/schema/swagger-ui/`
