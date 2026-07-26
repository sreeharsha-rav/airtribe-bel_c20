# Auth Test Report — ClearLedger

**Scope:** `accounts` app — models (`User`, `UserProfile`), serializers (`RegisterSerializer`, `CustomTokenObtainPairSerializer`, `UserSerializer`, `ProfileSerializer`), and the five auth endpoints (`register`, `login`, `token/refresh`, `logout`, `profile`).

**Run command:** `python manage.py test accounts`

**Result:** 35 / 35 passed, 0 failures, 0 errors — runtime ~95s (dominated by PBKDF2 password hashing on every `create_user()` call, expected for Django's default hasher).

---

## Coverage by module

| Test module | Class | Tests | What it verifies |
|---|---|---|---|
| `test_models.py` | `UserModelTests` | 3 | Default role is `owner`; custom role persists; `__str__` format |
| | `UserProfileModelTests` | 3 | Default currency `USD`; `__str__` format; one profile per user (`OneToOneField` uniqueness → `IntegrityError`) |
| `test_serializers.py` | `RegisterSerializerTests` | 3 | Password is hashed on save; password `min_length=8` rejects short passwords; explicit `role` is accepted |
| | `CustomTokenObtainPairSerializerTests` | 2 | `role`/`email` embedded in JWT payload (`get_token`) and in `validate()` response data |
| | `UserSerializerTests` | 1 | Serialized fields are exactly `username`, `email`, `role` (password never exposed) |
| | `ProfileSerializerTests` | 1 | Nested `user` field is read-only — attempting to write it through `ProfileSerializer` is silently ignored |
| `test_register_api.py` | `RegisterAPITests` | 5 | 201 + tokens on success; role defaults to `owner`; explicit role honored; duplicate username → 400; short password → 400; password never appears in response |
| `test_login_api.py` | `LoginAPITests` | 4 | 200 + `role`/`email`/tokens on success; JWT payload carries the same claims; wrong password → 401; unknown user → 401 |
| `test_token_refresh_api.py` | `TokenRefreshAPITests` | 3 | Valid refresh → new access + new refresh; **reusing a rotated refresh token fails with 401** (blacklist-after-rotation enforced); malformed token → 401 |
| `test_logout_api.py` | `LogoutAPITests` | 4 | Logout requires authentication (401 without a bearer token); valid logout blacklists the refresh token (verified by a subsequent failed refresh attempt); invalid token → 400; missing `refresh` field → 400 |
| `test_profile_api.py` | `ProfileAPITests` | 6 | Profile endpoint requires authentication; `GET` auto-creates the profile (`get_or_create`) on first access with `USD` default; `GET` returns an existing profile without duplicating it; `PATCH` updates `currency_preference`; `PATCH` cannot alter the nested `user` object; `PUT` is rejected with 405 (only `get`/`patch` allowed) |

**Total: 35 tests** across 3 model/serializer modules and 5 endpoint modules.

## Notable behaviors verified

- **Token rotation + blacklisting**: confirmed end-to-end that `ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION` actually invalidate the old refresh token — a naive test suite might only check the happy path and miss this.
- **JWT claim embedding**: `role` and `email` are checked both in the HTTP response body *and* by decoding the actual `AccessToken` payload, not just the API-level response.
- **Read-only field enforcement**: `ProfileSerializer`'s nested `user` field and `ProfileView`'s restricted `http_method_names` are both exercised to catch accidental privilege escalation via profile updates.
- **Negative/edge cases**: duplicate usernames, undersized passwords, wrong credentials, unauthenticated access, malformed tokens, and disallowed HTTP methods are all covered, not just the success paths.

## Known gaps / not yet covered

- No test hits the DB uniqueness/format constraints Django enforces natively on `email` (it's not unique at the model level, so none needed here).
- Rate limiting / brute-force protection on `login` — not implemented in the view, so not tested.
- `accounts`, `transactions`, and `budgets` CRUD endpoints are not yet implemented (per `todos.md`), so this report is scoped to auth only.