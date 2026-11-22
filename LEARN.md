# LEARN: how to study this repo

Ledgerly Bank is the app the rest of the portfolio tests. You don't need to become a Django developer, but you need to **explain every rule it enforces and how each one is tested**, because interviewers will ask "how do you know this API is secure?"

Each part follows the same loop: key concepts → run it → read it in order → break it → explain it → quiz.

---

# Part 1: API scaffold and authentication (Forge90 day 10)

Budget: one 2-hour session, plus the quiz (45 min).

## 1. Key concepts

**Django + Django REST Framework (DRF).** Django gives the database layer (models, migrations), admin and settings; DRF adds the REST layer: serializers (validate input, shape output), views, authentication, permissions, throttling, pagination.

**Project layout:**

| Folder | Job |
|---|---|
| `config/` | Settings, URL routing. `settings_test.py` = production settings + a fast password hasher. |
| `users/` | Custom user (email login), register, login, refresh, profile. |
| `core/` | Health check for Docker/Kubernetes probes. |
| `tests/` | pytest-django tests. |

**Custom user model from day one.** Django's default user logs in with a username. Banks use email. Switching the user model later is painful (every foreign key points at it), so it's done before the first migration.

**JWT (JSON Web Token) auth.** Login returns two tokens:
- **Access token:** sent as `Authorization: Bearer <token>` on every request; expires in 15 minutes.
- **Refresh token:** used only at `/api/auth/refresh/` to get a new access token; lasts 1 day.

A JWT is `header.payload.signature`. Anyone can *read* the payload (it's base64, not encrypted), but nobody can *change* it without the signing key: change one character and the signature check fails (`test_a_tampered_token_is_rejected`).

**Rotation + blacklist.** Every refresh returns a *new* refresh token. With `BLACKLIST_AFTER_ROTATION`, the old one is recorded as used and stops working, so a stolen refresh token that was already used can't be replayed. Without the blacklist, rotation is cosmetic. The mutation check proved the test catches that.

**Secure by default.** DRF's default permission is `IsAuthenticated`; only 4 operations opt out (health, register, login, refresh). `test_api_security.py` reads the **OpenAPI schema** and calls every other operation without a token, expecting 401. When later days add endpoints, they're tested automatically.

**No user enumeration.** A wrong password and an unknown email return the *same* 401 body. Otherwise the login form tells an attacker which emails are customers.

**Rate limiting.** Auth endpoints allow 10 requests per minute per client (`ScopedRateThrottle` + `throttle_scope = "auth"`). The 11th gets **429 Too Many Requests**.

**OpenAPI contract.** `drf-spectacular` generates `backend/openapi.yaml` from the code. It's committed, and CI fails if the code and the file disagree. So any API change shows up as a diff in review, and the Angular app, API tests (P-05) and contract tests can all use the same file.

**CI on two databases.** Tests run on SQLite (fast, no setup) and Postgres 17 (what production would use). They differ in real ways: case sensitivity, locking, constraint timing. A bug that only appears on Postgres would otherwise reach production.

## 2. Three bugs the tests found while building this

1. **Login wasn't rate limited at all.** `throttle_scope = "auth"` looks like it enables throttling, but DRF ignores it unless the view also uses `ScopedRateThrottle`, and there are no default throttle classes. `test_login_is_rate_limited` got 401 on the 11th attempt instead of 429.
2. **The JWT signing key was too short.** PyJWT warned that the key was 21 bytes; HS256 needs at least 32 (RFC 7518). Now the app refuses to start with a short key when DEBUG is off.
3. **The test secret was set too late.** pytest-django loads the settings before any `conftest.py` runs, so the tests only passed because `DJANGO_DEBUG` happened to be set in the shell. Fixed with `config/settings_test.py`. Lesson: a test suite that passes only with a variable that happens to be set in your shell will fail in CI.

## 3. Run it

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Open http://localhost:8000/api/docs and, in Swagger:
- [ ] `POST /api/auth/register/` with your own email and a strong password.
- [ ] `POST /api/auth/login/`, copy the `access` token, click **Authorize**, paste it.
- [ ] `GET /api/auth/me/`. Then paste a wrong token and try again.
- [ ] Log in 11 times quickly with a wrong password. What status do you get on the 11th?

Tests:

```bash
pytest -q
```

## 4. Read it, in this order

| # | File | What to understand |
|---|---|---|
| 1 | `config/settings.py` | Everything from env vars; secret key rules; DRF defaults (auth, permissions, throttling); JWT lifetimes. |
| 2 | `users/models.py` | Email as the login field; `set_password` hashes. |
| 3 | `users/serializers.py` | Case-insensitive duplicate check; Django's password validators. |
| 4 | `users/views.py`, `users/urls.py` | Which views are public and rate limited. |
| 5 | `core/views.py` | Why health returns 503 instead of crashing. |
| 6 | `tests/conftest.py` | Fixtures: `user`, `auth_api` logs in through the real endpoint. |
| 7 | `tests/test_auth.py`, `tests/test_api_security.py` | Every rule, tested both ways. |
| 8 | `.github/workflows/ci.yml` | Matrix on SQLite + Postgres; migration and OpenAPI checks. |

## 5. Break it

1. [ ] Delete `throttle_classes = [ScopedRateThrottle]` from `LoginView`. Which test fails?
2. [ ] Add `permission_classes = [AllowAny]` to `MeView`. How many tests fail, and which file catches it even though you never wrote a test for that view specifically?
3. [ ] Add a field to `UserSerializer` without regenerating `openapi.yaml`. Run the CI command `python manage.py spectacular --file /tmp/o.yaml && diff openapi.yaml /tmp/o.yaml`. What does the diff show?
4. [ ] Paste an access token into https://jwt.io (it's fake data, so that's fine). What's in the payload? What would an attacker gain from reading it?

## 6. Explain it

1. What's the difference between authentication and authorization? Which DRF setting handles each?
2. Why do JWTs expire after 15 minutes, and how does the user stay logged in?
3. What is refresh-token rotation, and why does it need a blacklist?
4. Why should a wrong password and an unknown email return the same error?
5. How do you prove that *every* endpoint requires a login, including ones added next month?
6. Why run tests on SQLite and Postgres?
7. Why commit the OpenAPI file instead of only serving it?

## 7. Study material

- ⭐ [DRF tutorial](https://www.django-rest-framework.org/tutorial/quickstart/) (quickstart + parts 1–4)
- ⭐ [OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/): read API1 (broken object-level authorization: day 11's IDOR tests) and API2 (broken authentication: today)
- [Simple JWT docs](https://django-rest-framework-simplejwt.readthedocs.io/): settings, blacklist app
- [jwt.io introduction](https://jwt.io/introduction)
- [drf-spectacular](https://drf-spectacular.readthedocs.io/)

## 8. Quiz (tonight)

**Part A: concepts (1 point each)**

1. Name the two tokens login returns and how long each lasts.
2. What are the three parts of a JWT, and which one stops tampering?
3. Which four operations are public?
4. What HTTP status does the 11th login attempt in a minute get?
5. Why was the custom user model created before the first migration?
6. Which two databases does CI test on?

**Part B: read the code (2 points each)**

7. In `RegisterSerializer.validate`, why does it build a `User(...)` object that's never saved?
8. Why does `auth_api` log in through `/api/auth/login/` instead of forcing authentication?
9. In `test_api_security.py`, how does `/api/accounts/{id}/` get turned into a URL the test can call?
10. What does the CI step "OpenAPI schema is valid and committed" do when they differ?

**Part C: predict, then run (3 points each)**

11. You remove `BLACKLIST_AFTER_ROTATION`. Which test fails, and what attack becomes possible?
12. Someone sets `DJANGO_SECRET_KEY=short` with DEBUG off. What happens when the server starts, and why is that better than starting?
13. A new endpoint `GET /api/statements/` is added and someone forgets the permission class. But the default is `IsAuthenticated`. Does `test_api_security.py` still matter? When would it catch something?

<details>
<summary>Answers</summary>

1. Access token (15 minutes) and refresh token (1 day).
2. Header, payload, signature. The signature: it's computed with the secret key over header and payload, so changing either breaks it.
3. `GET /api/health/`, `POST /api/auth/register/`, `POST /api/auth/login/`, `POST /api/auth/refresh/`.
4. 429 Too Many Requests.
5. Every foreign key to users points at the user model; changing it after tables and data exist means painful migrations. Django's docs recommend a custom user at project start.
6. SQLite and Postgres 17.
7. Django's `UserAttributeSimilarityValidator` compares the password with the user's attributes (email, name), so it needs a user object; it isn't saved because validation runs before creation.
8. So every test that uses it also exercises the real login path (serializer, token creation). A shortcut would skip the code the tests are meant to protect.
9. `re.sub(r"\{[^}]+\}", "1", path)` replaces each `{param}` with `1`. Authentication runs before the object lookup, so an anonymous request gets 401 whether or not object 1 exists.
10. It prints the diff and fails with an error telling you to regenerate `openapi.yaml`, so API changes can't merge unreviewed.
11. `test_an_old_refresh_token_stops_working_after_rotation`. A stolen refresh token stays usable for its whole lifetime even after the real user refreshed: replay.
12. It refuses to start (`RuntimeError`). A server running with a guessable signing key would let anyone forge JWTs; failing loudly at startup is far safer than a quiet security hole.
13. Yes. The default protects you only if nobody overrides it. It catches: someone adding `permission_classes = [AllowAny]` "temporarily", a view that sets `authentication_classes = []`, or a copy-pasted public view. The test checks behaviour, not configuration.

</details>
