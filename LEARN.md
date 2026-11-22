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

---

# Part 2: Accounts, statements and demo data (Forge90 day 11)

Budget: one 2-hour session, plus the quiz (45 min).

## 9. Key concepts

**The data model:**

| Model | Holds | Rule |
|---|---|---|
| `Account` | owner, IBAN, type (Current / Savings / Premier, the products in the chatbot's policies), balance, status (ACTIVE / FROZEN) | Read-only through the API: balances only change through transactions. |
| `Transaction` | account, direction (CREDIT in / DEBIT out), category, amount (always positive), `balance_after`, description, counterparty, unique reference | Immutable: a mistake is fixed with a new transaction, never an edit. That's how real ledgers work, and it keeps an audit trail. |

**Money is `Decimal`.** In floating point, `0.1 + 0.2 == 0.30000000000000004`. Banking needs exact cents, so every amount is `DecimalField(max_digits=14, decimal_places=2)`, and the API sends money as **strings** (`"1000.00"`) so a JavaScript client can't silently turn it into a float.

**The ledger invariant:** `balance == sum(credits) - sum(debits)`, and each transaction's `balance_after` is the running balance. A test checks it for every seeded account. That test found a real bug (below).

**IBAN:** `AE` + 2 check digits + 3-digit bank code + 16-digit account number = 23 characters. The check digits use **mod-97** (ISO 13616): move the first 4 characters to the end, turn letters into numbers (A=10 … Z=35), and the whole number mod 97 must be 1. It catches every single-digit typo. Ledgerly uses bank code `999`, which no real UAE bank uses.

**Broken object-level authorization (BOLA / IDOR), OWASP API #1.** The most common serious API bug: `/api/accounts/42/` returns account 42 to *anyone logged in*, because the code checks "is logged in" but not "owns this account". Here every query is filtered by `owner=request.user`, and:
- someone else's account → **404, not 403**. A 403 would confirm the account exists;
- a test checks that someone else's account and a non-existent one return the **identical** response;
- another test logs in as the real owner and gets 200, proving the 404 isn't just a broken endpoint.

**Filters that fail loudly.** `?direction=SIDEWAYS` returns **400**, not an empty list. An empty list would make a typo in a test or the UI look like "no transactions".

**Pagination:** 20 per page with `count`, `next` and `previous`. Tests check the boundary (25 rows → 20 + 5, and `next` is `null` on the last page).

**Deterministic seed data.** `python manage.py seed` creates 3 customers, 6 accounts and ~370 transactions over 90 days from `random.Random(42)`. Same seed + same `--today` = byte-identical data, so tests and demos can say "Sara has a frozen account" and stay true. It includes edge cases on purpose: a frozen account, a Premier account with a large balance, a savings account with interest. It refuses to run with DEBUG off (`LEDGERLY_ALLOW_SEED=true` to override), because the demo password is public.

## 10. Bugs found while building

1. **Broken running balance in the seed data.** Transactions on the same day got random times, so a card payment could be stamped *before* the salary it was paid from. Sorted by time, the statement showed a running balance that jumped around. `test_balance_after_is_a_consistent_running_balance_and_never_negative` caught it; same-day times now always increase. A tester looking at the statement screen would have reported exactly this.
2. **Schema warnings.** The views build their queryset from `request.user`, which doesn't exist while the OpenAPI schema is generated, so drf-spectacular couldn't tell which model the endpoints return. CI's `--fail-on-warn` stopped it; fixed with `queryset = Account.objects.none()` and a `swagger_fake_view` check.
3. Two of my own test mistakes (an IBAN's bank code isn't at the start; a fixture stored a balance as a string). Worth saying in an interview: not every red test is a product bug.

**Mutation check:** removing the owner filter from the account detail view (2 tests failed), from the statement view (1 failed), and making `date_to` exclusive (1 failed). All caught.

## 11. Run it

```bash
cd backend
python manage.py migrate
python manage.py seed --today 2026-11-22
python manage.py runserver
```

In Swagger (http://localhost:8000/api/docs), log in as `sara@example.com` / `Ledgerly-Demo-2026`:
- [ ] `GET /api/accounts/`, then a statement with `?category=CARD&min_amount=100`.
- [ ] Log in as `omar@example.com` and try one of Sara's account ids. What do you get?
- [ ] Try `?direction=SIDEWAYS`. Why is 400 better than an empty list?

## 12. Read it, in this order

| # | File | What to understand |
|---|---|---|
| 1 | `banking/models.py` | Decimal money, immutable transactions, the positive-amount constraint. |
| 2 | `banking/iban.py` | mod-97 in ~10 lines. |
| 3 | `banking/views.py` | Every queryset is filtered by owner; 404 vs 403. |
| 4 | `banking/filters.py` | Statement filters; inclusive dates. |
| 5 | `banking/seed.py` | Deterministic generation; increasing times; no overdraft. |
| 6 | `tests/test_accounts.py` | IDOR tests, filters, pagination, read-only. |
| 7 | `tests/test_seed.py` | Reproducibility, the ledger invariant, the production guard. |

## 13. Break it

1. [ ] In `AccountTransactions.get_queryset`, remove `owner=self.request.user`. Which test fails? Explain the attack in one sentence.
2. [ ] Change `DecimalField` to `FloatField` for `amount` (and migrate). Which tests break, and what would a customer see?
3. [ ] Seed with `--seed 1` and with `--seed 2`. Compare Sara's balances. Run `--seed 1` twice. Same?
4. [ ] Revert the "increasing times" fix in `seed.py` and run `test_seed.py`. Read the failure message: which transaction and which balances?

## 14. Explain it

1. What's BOLA/IDOR, and how do you test for it?
2. Why 404 rather than 403 for someone else's account?
3. Why must money never be a float, and how does the API send it?
4. Why are transactions immutable?
5. What does the mod-97 check catch?
6. Why must test data be deterministic? What's the risk with random data?
7. An invalid filter returns an empty list instead of 400. Why is that a bug?

## 15. Study material

- ⭐ [OWASP API1:2023 Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)
- ⭐ [DRF filtering](https://www.django-rest-framework.org/api-guide/filtering/) and [django-filter](https://django-filter.readthedocs.io/)
- [IBAN check digits (Wikipedia)](https://en.wikipedia.org/wiki/International_Bank_Account_Number#Validating_the_IBAN)
- [Python decimal module](https://docs.python.org/3/library/decimal.html): read "Quick-start tutorial"
- Martin Fowler, [Accounting patterns](https://martinfowler.com/eaaDev/AccountingNarrative.html): why ledgers append and never edit

## 16. Quiz (tonight)

**Part A: concepts (1 point each)**

1. What are the four parts of a UAE IBAN, and how long is it?
2. What does a CREDIT do to the balance? A DEBIT?
3. What status do you get for someone else's account, and why that one?
4. Why does the API send `"1000.00"` and not `1000.0`?
5. How many items per page, and how do you get page 2?
6. Name two edge cases the seed data includes on purpose.

**Part B: read the code (2 points each)**

7. In `is_valid_uae_iban`, why are the first four characters moved to the end?
8. Which line makes `/api/accounts/<someone else's id>/transactions/` a 404?
9. What does `test_a_missing_account_and_someone_elses_look_identical` compare, and why both status *and* body?
10. Why does `seed()` skip a debit instead of letting the balance go negative?

**Part C: predict, then run (3 points each)**

11. You add `?min_amount=420&max_amount=420` to the test statement. How many rows, and why?
12. A developer adds `PATCH /api/accounts/{id}/` to rename an account and copies `AccountList`'s queryset. Which existing test still protects you, and what new test would you add?
13. Production runs `python manage.py seed` by mistake. What happens? What if `LEDGERLY_ALLOW_SEED=true` is set there?

<details>
<summary>Answers</summary>

1. `AE`, 2 check digits, a 3-digit bank code, a 16-digit account number: 23 characters.
2. CREDIT adds money (in), DEBIT subtracts (out). The amount itself is always positive.
3. 404. A 403 would confirm the account exists; 404 reveals nothing.
4. Strings keep exact cents. A JSON number is parsed as a float by JavaScript and many other clients, which can't represent most cents exactly.
5. 20 per page; `?page=2` (the response's `next` field gives the full URL).
6. Any two of: a frozen account; a Premier account with a large balance; savings accounts with interest credits; salaries on the 25th; bills on the 3rd.
7. The IBAN standard defines the check that way: country code and check digits go to the end, letters become numbers, and the result mod 97 must equal 1.
8. `get_object_or_404(Account, pk=self.kwargs["pk"], owner=self.request.user)` in `AccountTransactions.get_queryset`.
9. Status code and JSON body for someone else's account vs a non-existent id. A different body (e.g. "permission denied" vs "not found") would leak existence just like a different status.
10. Demo customers have no overdraft facility; a negative balance would be unrealistic data and would break the "never negative" invariant tests rely on.
11. One row (the AED 420.00 bill): both filters are inclusive (`gte` / `lte`).
12. `test_api_security.py` still checks that anonymous requests get 401, but it can't catch BOLA. Add: Sara PATCHes Omar's account → 404 and the nickname is unchanged in the database. (And in code: `Account.objects.filter(owner=self.request.user)`.)
13. It refuses with "Refusing to seed demo users with DEBUG off" and creates nothing. With the override set, it would create three customers with a public password: the override exists for CI and demo environments only, which is why it's opt-in and named so loudly.

</details>
