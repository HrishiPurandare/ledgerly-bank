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

---

# Part 3: Beneficiaries and transfers (Forge90 day 12)

The heart of a bank: moving money. Every rule here is one an interviewer can ask you to test, and the tricky ones (boundaries, time zones, races, retries) are where real banking bugs live.

Budget: two 2-hour sessions (concepts and running it in the first; the tests and break-it in the second), plus the quiz.

## 17. Key concepts

**The rules, straight from the bank's policy** (`data/policies/transfers-and-limits.md` in the chatbot repo):

| Rule | Code | Error code |
|---|---|---|
| AED 50,000 per customer per day, across all accounts | `rules.sent_today` | `daily_limit_exceeded` |
| AED 10,000 to a new beneficiary in the first 24 hours | `rules.in_cooling_off`, `sent_to_new_beneficiary` | `new_beneficiary_limit` |
| Up to 100 beneficiaries | `add_beneficiary` | `too_many_beneficiaries` |
| Adding a beneficiary needs an OTP | `confirm_beneficiary` | `otp_invalid`, `otp_expired`, `otp_locked` |
| UAE IBAN: AE + 23 characters | `is_valid_uae_iban` (+ mod-97) | `invalid_iban` |

Plus rules any bank has: enough balance (`insufficient_funds`), no frozen accounts (`account_frozen`, `destination_unavailable`), two different accounts (`same_account`), a confirmed beneficiary (`beneficiary_not_active`).

**Decisions the policy didn't make (and you should be able to defend):**
- **Own-account transfers don't count toward the daily limit.** The limit is about money leaving the customer; moving it between their own accounts doesn't.
- **"Day" means the customer's local day in Dubai**, not UTC. 00:30 in Dubai is still the previous day in UTC; a UTC day would reset the limit at 4 AM local time.
- **The 24 hours start when the beneficiary is confirmed**, not when it was first added.

**Error codes, not just messages.** Every rejection returns `{"code": "daily_limit_exceeded", "detail": "..."}`. Tests and the UI match on the code; the wording can change freely.

**Three kinds of transfer:** OWN (between your accounts), INTERNAL (to another Ledgerly customer: both sides update instantly), LOCAL (to another UAE bank: only your side is debited and the transfer is PENDING. Day 13 turns it into an ISO 20022 pacs.008 message). Each transfer gets a **UETR**, a UUID that identifies the payment end to end across banks.

**OTP done properly:**
- generated with `secrets` (unpredictable), not `random`;
- sent by email, never in the API response;
- stored as an HMAC hash, so a database leak doesn't reveal live codes;
- compared in constant time (`hmac.compare_digest`);
- expires after 5 minutes, and 3 wrong attempts lock the beneficiary for good;
- a malformed code ("12345") is a 400 that does **not** use up an attempt.

One subtle bug avoided: the wrong-attempt counter is saved **outside** a database transaction. If it were inside one, raising the error would roll the counter back, and an attacker would get unlimited guesses. A mutation test proves it.

**Atomicity.** `_execute` runs in `transaction.atomic`: either the debit, the credit, both balance updates and the transfer record all happen, or none do. `test_one_fils_more_than_the_balance_is_refused_and_nothing_changes` checks that a refusal leaves no transaction, no transfer and unchanged balances.

**Race conditions and locks.** Two requests at the same instant both read "balance 5,000", both pass the check, both debit 1,000 each... ten times over. The fix is `SELECT ... FOR UPDATE` (row locks):
1. **Lock the customer row first.** Otherwise two transfers from *different* accounts both read "AED 0 sent today" and together send AED 60,000.
2. **Then lock the accounts in id order.** Always the same order, so two transfers between the same accounts in opposite directions can't deadlock.
3. **Re-read the balances after locking**; values read before the lock may be stale.

`tests/test_concurrency.py` fires 10 transfers at the same instant with threads (10 × AED 1,000 from AED 5,000 → exactly 5 succeed). SQLite ignores `FOR UPDATE`, so these run only in CI's Postgres job. That's one more reason CI tests on both databases.

**Idempotency.** The network drops the response, the app retries, the customer double-clicks: the same transfer arrives twice. The client sends an `Idempotency-Key` header (a UUID per transfer):
- same key + same body → the **original response** again, header `Idempotent-Replayed: true`, no money moves;
- same key + different body → **409 Conflict** (a client bug);
- no key → 400;
- keys are per customer; a unique constraint in the database makes the guarantee hold even when two identical requests race (the loser hits `IntegrityError` and answers like a replay).

Stripe's API works the same way; mentioning that in an interview shows you know the pattern.

## 18. Bugs found while building

- **A pasted IBAN was rejected.** Customers paste `AE07 0331 2345 6789 0123 456` (27 characters with spaces). The serializer's `max_length=23` refused it before the code that removes spaces could run. The input now accepts up to 34 characters and stores the clean 23.
- **A race the lock didn't stop (found later, by CI on Postgres).** The concurrency test passed on the first CI run and failed on the second: two AED 30,000 transfers from different accounts both went through. The customer lock worked; the *time window* didn't. Each request reads `now` before waiting for the lock, and `sent_today` only counted transfers up to that `now`. If request B read the clock first but lost the race for the lock, request A's transfer was stamped a moment after B's `now`, so B never saw it. Fix: count everything since the start of the Dubai day (no upper bound). `test_a_transfer_stamped_after_now_still_counts_toward_the_limit` reproduces it on every run, with no threads and no luck. Lessons: a concurrency test that passes once proves little; and when a flaky failure appears, turn it into a deterministic test before fixing it.
- Mutation check, 6 of 6 caught: refusing the exact balance, the daily limit off by one fils, counting own transfers toward the limit, using the UTC day, not detecting key reuse, not saving wrong OTP attempts.

## 19. Run it

```bash
cd backend
python manage.py migrate
python manage.py seed --reset
python manage.py runserver
```

In Swagger, as `sara@example.com` / `Ledgerly-Demo-2026`:
- [ ] `POST /api/beneficiaries/` with `{"name": "Omar Ali", "iban": "<Omar's IBAN from GET /api/accounts/ as omar>"}`. The OTP email prints in the **server terminal**. Confirm it with `POST /api/beneficiaries/{id}/confirm/`.
- [ ] `POST /api/transfers/` with header `Idempotency-Key: test-1` and AED 12,000 to that beneficiary. Which error, and why?
- [ ] Send AED 9,000, then send it again with the **same** key. Check the response header and Sara's balance.

## 20. Read it, in this order

| # | File | What to understand |
|---|---|---|
| 1 | `payments/rules.py` | The policy as pure functions over `now`; the Dubai day. |
| 2 | `payments/otp.py` | secrets, HMAC, constant-time compare. |
| 3 | `payments/services.py` `add_beneficiary`, `confirm_beneficiary` | Why confirm isn't atomic. |
| 4 | `payments/services.py` `create_transfer`, `_execute` | Idempotency, lock order, the rule checks, atomic money movement. |
| 5 | `payments/views.py` | Idempotency-Key header, the replay header. |
| 6 | `tests/test_beneficiaries.py`, `tests/test_transfers.py` | Boundaries, "nothing changes" checks. |
| 7 | `tests/test_concurrency.py` | Threads + barrier; why Postgres only. |

## 21. Break it

1. [ ] Remove the line that locks the customer (`get_user_model().objects.select_for_update()...`). Do the SQLite tests notice? Which Postgres test would? Explain the attack.
2. [ ] Move `confirm_beneficiary` inside `@transaction.atomic`. Which test fails, and what can an attacker now do?
3. [ ] Change `start_of_day` to use UTC. Which test fails? At what Dubai time would a customer's limit reset?
4. [ ] Send the same transfer twice with **different** keys. Is that a bug? What would a real bank add (hint: duplicate-payment warnings)?

## 22. Explain it

1. What's idempotency, and how does the API guarantee a retry never pays twice?
2. Why lock the customer row and not just the accounts?
3. Why lock accounts in a fixed order?
4. Why must the daily limit use Dubai's day, and what would go wrong with UTC?
5. How is the OTP protected: in transit, at rest, and against guessing?
6. Why are the concurrency tests skipped on SQLite, and what does that say about testing on only one database?
7. How do you test a "first 24 hours" rule without waiting 24 hours?

## 23. Study material

- ⭐ [Stripe: idempotent requests](https://docs.stripe.com/api/idempotent_requests) and Brandur Leach, [Implementing Stripe-like idempotency keys in Postgres](https://brandur.org/idempotency-keys)
- ⭐ [Django: select_for_update](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update) and [database transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/)
- [OWASP: testing for race conditions](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/10-Business_Logic_Testing/README) (business logic testing chapter)
- [OWASP Multifactor Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html)

## 24. Quiz (tonight)

**Part A: concepts (1 point each)**

1. What are the three kinds of transfer, and which one stays PENDING?
2. What's the daily limit, and which transfers don't count toward it?
3. When does the new-beneficiary limit start and end?
4. What does the `Idempotent-Replayed: true` header mean?
5. What status does reusing a key for a different transfer get?
6. How many wrong OTPs lock a beneficiary, and does "12345" count as one?

**Part B: read the code (2 points each)**

7. In `_execute`, why are balances re-read *after* `select_for_update`?
8. In `create_transfer`, what happens on `IntegrityError`, and when does that happen?
9. Why does `confirm_beneficiary` not use `@transaction.atomic`?
10. In `test_the_daily_limit_spans_all_accounts`, why 46,000 + 4,000.01?

**Part C: predict, then run (3 points each)**

11. Sara has AED 5,000 and fires 10 simultaneous AED 1,000 transfers on Postgres. With the locks, what happens? Without any locks?
12. At 00:30 on 23 Nov (Dubai), Sara has sent AED 45,000 since 00:00 on 22 Nov. How much can she send now, and why?
13. A beneficiary was confirmed 23 hours ago and has received AED 6,000. Sara sends AED 5,000. What's the error message? And 2 hours later?

<details>
<summary>Answers</summary>

1. OWN, INTERNAL, LOCAL. LOCAL (another bank) stays PENDING until the payment network settles it.
2. AED 50,000 per customer per Dubai day, across all accounts. Transfers between the customer's own accounts don't count.
3. It starts when the beneficiary is confirmed with the OTP (`activated_at`) and lasts 24 hours.
4. The request was a retry with an already-used key and the same body: this is the original response, and no money moved.
5. 409 Conflict, code `idempotency_key_reused`.
6. Three wrong codes. "12345" isn't 6 digits, so it's rejected as a 400 by the serializer before checking, and doesn't count as an attempt.
7. Values read before the lock may have been changed by another transaction that committed in between; only values read under the lock are safe to check and update.
8. Two identical requests with the same key raced past the "already exists?" check; the database's unique constraint stopped the second insert. The code looks the transfer up again and answers like a replay (or 409 if the bodies differ).
9. A wrong attempt raises an error; inside an atomic block that error would roll back the saved attempt counter, giving unlimited guesses.
10. 46,000 + 4,000 = 50,000 exactly, the limit; the extra 0.01 tips it over. It also proves the limit adds up transfers from *different* accounts.
11. With locks: exactly 5 succeed, 5 get `insufficient_funds`, balance ends at 0.00. Without locks: several requests read 5,000 before any write, so more than 5 can succeed and the balance can go negative (or updates overwrite each other).
12. AED 50,000: it's a new Dubai day since 00:00 on 23 Nov, so yesterday's AED 45,000 doesn't count.
13. `new_beneficiary_limit`: "New beneficiaries are limited to AED 10000.00 for 24 hours. You can send AED 4000.00 more until then." Two hours later the beneficiary is over 24 hours old, so only the daily limit applies and AED 5,000 goes through.

</details>

---

# Part 4: ISO 20022 pacs.008 messages (Forge90 day 13)

You've tested FedNow, Fedwire, SWIFT and ACH payments at work; this is the part of the portfolio that shows it. A transfer to another bank isn't a database update: it's a **message** sent through a payment network, and the message format is ISO 20022.

Budget: one 2-hour session, plus the quiz (45 min).

## 25. Key concepts

**ISO 20022** is the global standard for financial messages: XML documents with strictly defined elements. SWIFT cross-border payments, FedNow, the European SEPA schemes and the UAE's instant payment platform all use it (or are moving to it). Message names read like `pacs.008.001.08`:
- `pacs` = payments clearing and settlement (bank to bank);
- `008` = FI to FI customer credit transfer ("move a customer's money to another bank");
- `001.08` = variant 1, version 8.

Others you've met: `pain.001` (customer → bank instruction), `pacs.002` (payment status report), `camt.053` (statement).

**What Ledgerly puts in the message:**

| Element | Meaning | Ledgerly value |
|---|---|---|
| `GrpHdr/MsgId` | This message's id | `MSG-<reference>` |
| `GrpHdr/CreDtTm` | When it was created, with time zone | transfer time, Dubai +04:00 |
| `GrpHdr/SttlmInf/SttlmMtd` | How banks settle | `CLRG` (through the local clearing system) |
| `PmtId/EndToEndId` | Id that stays the same end to end | the transfer reference |
| `PmtId/UETR` | Unique end-to-end transaction reference (a version-4 UUID), tracked across every bank (SWIFT gpi) | `transfer.uetr` |
| `IntrBkSttlmAmt` + `Ccy` | Amount banks settle | `1250.75` `AED` |
| `IntrBkSttlmDt` | Settlement date | from the 2 PM cut-off rule |
| `ChrgBr` | Who pays charges | `SLEV` (per the clearing system's service level) |
| `Dbtr` / `DbtrAcct` / `DbtrAgt` | Payer, their IBAN, their bank | the customer, their IBAN, Ledgerly's (fictional) BIC |
| `Cdtr` / `CdtrAcct` / `CdtrAgt` | Payee, their IBAN, their bank | the beneficiary, their IBAN, the bank code from the IBAN |
| `RmtInf/Ustrd` | Free-text remittance info | the transfer remarks, left out when empty |

**The subset XSD.** An XSD (XML Schema) is a machine-checkable contract: element names, order, which elements are required, patterns (IBAN, BIC, UUID v4) and code lists (`CLRG`, `SLEV`...). `payments/schemas/pacs.008.001.08.subset.xsd` was written for this project from the published message definition: real namespace, names, order and rules, minus the optional elements Ledgerly never sends. It isn't the official file (that comes from iso20022.org), and the header comment says so. Say it the same way in interviews: "validated against a subset schema I wrote from the standard; before a real network I'd validate against the official XSD and the network's usage guidelines."

**Settlement date** (policy: "before 2:00 PM on a business day ... credited the same day"):
- before 14:00 Dubai time, Monday to Friday → same day;
- 14:00 exactly, later, or on a weekend → next business day;
- the UAE weekend has been **Saturday and Sunday since 2022** (before that, Friday and Saturday). A mutation test with the old weekend broke 4 tests;
- public holidays aren't modelled (a real bank reads a holiday calendar).

**Testing XML, four ways:**
1. **Schema validation:** the message obeys the contract.
2. **Content assertions with XPath:** the *right* amount, IBANs, UETR. A schema-valid message can still carry the wrong payment.
3. **Golden file:** the exact bytes for a fixed transfer, reviewed once and committed (`tests/golden/pacs008_local.xml`). Any change to the output fails the test until someone reviews the diff and updates the file. Great for catching unintended changes; useless if people update the file without reading it.
4. **Test the validator itself:** five deliberately broken messages (bad code, lower-case currency, bad IBAN, non-numeric count, wrong UUID version) must all be rejected. While writing this, one "broken" message turned out to still be valid: my replacement edited the wrong `-4` in the UUID. Without this test, that mistake would have gone unnoticed.

**XML security:**
- **Injection:** a customer could name a beneficiary `</Nm><Nm>Evil`. lxml escapes `&`, `<` and `>` when setting text, so the name round-trips intact and the message stays valid (`test_special_characters_in_names_are_escaped_not_injected`).
- **XXE (XML external entities):** a document can declare `<!ENTITY x SYSTEM "file:///etc/passwd">` and make a careless parser read local files or call URLs. The parser here never resolves entities or touches the network, and any message with a DOCTYPE is rejected outright, since payment messages never need one. Found while building: with entities off, lxml's schema validator crashed with an "internal error" on the unresolved entity; the DOCTYPE rule and error handling turned that into a clean validation error.

## 26. Run it

```bash
cd backend
python manage.py runserver
```

As Sara in Swagger: add and confirm a beneficiary with the IBAN `AE070331234567890123456` (another bank), send a transfer, then:

```bash
curl -s -H "Authorization: Bearer <access token>" localhost:8000/api/transfers/<id>/pacs008/
```

- [ ] Find the UETR in the XML and compare it with `GET /api/transfers/<id>/`.
- [ ] Note the settlement date. What would it be at 14:05 on a Friday?

## 27. Read it, in this order

| # | File | What to understand |
|---|---|---|
| 1 | `tests/golden/pacs008_local.xml` | What a message looks like. |
| 2 | `payments/schemas/pacs.008.001.08.subset.xsd` | Sequence order, patterns, code lists. |
| 3 | `payments/iso20022.py` | `settlement_date`, `build_pacs008`, the safe parser, `validate`. |
| 4 | `tests/test_pacs008.py` | The four kinds of XML test, plus XXE. |

## 28. Break it

1. [ ] Swap the order of `<Dbtr>` and `<DbtrAcct>` in `build_pacs008`. Which tests fail, and what does the schema error say?
2. [ ] Change `WEEKEND` to `{4, 5}`. Which settlement-date cases fail?
3. [ ] Change the remarks to an empty string but keep the `RmtInf` element. Why does the schema reject `<Ustrd></Ustrd>`?
4. [ ] Change one character in `tests/golden/pacs008_local.xml`. Read the failure. What process should a team follow before updating a golden file?

## 29. Explain it

1. What is pacs.008, and how is it different from pain.001?
2. What's a UETR, and why does it matter for tracking payments?
3. Why isn't schema validation enough to test a payment message?
4. What's a golden-file test? When is it useful, and what's the risk?
5. What's XXE, and how does this code prevent it?
6. Why does the settlement date depend on the time zone and the weekend?

## 30. Study material

- ⭐ [ISO 20022 message definitions](https://www.iso20022.org/iso-20022-message-definitions) (search "pacs.008")
- ⭐ [OWASP XXE Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html)
- [SWIFT: ISO 20022 programme](https://www.swift.com/standards/iso-20022) and [SWIFT gpi / UETR](https://www.swift.com/our-solutions/swift-gpi)
- [lxml: validation with XML Schema](https://lxml.de/validation.html#xmlschema)

## 31. Quiz (tonight)

**Part A: concepts (1 point each)**

1. What do `pacs`, `008` and `001.08` mean?
2. Which element identifies a payment across every bank it passes through?
3. What does `ChrgBr` `SLEV` mean?
4. Which days are the UAE weekend now, and since when?
5. Which transfers get a pacs.008 message, and which status code do the others get?
6. Why is the schema called a "subset"?

**Part B: read the code (2 points each)**

7. Why does `build_pacs008` format the amount with `:.2f` instead of `str(float(...))`?
8. How does the code identify the creditor's bank without a BIC?
9. In `validate`, what are the three ways a message can fail, and why does it never raise?
10. Why does the golden test fix the UETR and the reference?

**Part C: predict, then run (3 points each)**

11. A transfer is made at 13:59:59 on Friday 27 Nov 2026, Dubai time. Settlement date? And at 14:00:00?
12. A beneficiary is named `Ali & Sons <FZE>`. What appears inside `<Nm>` in the raw XML, and what does a parser read back?
13. Someone sends `validate()` a message with `<!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]>`. What happens, step by step?

<details>
<summary>Answers</summary>

1. `pacs` = payments clearing and settlement (bank-to-bank); `008` = FI to FI customer credit transfer; `001.08` = variant 1, version 8.
2. `PmtId/UETR` (with `EndToEndId` also kept end to end).
3. Charges follow the service level agreed in the clearing system (each side pays its own bank under the scheme's rules).
4. Saturday and Sunday, since January 2022 (previously Friday and Saturday).
5. Only LOCAL transfers (to another UAE bank). OWN and INTERNAL get 409 `not_a_network_payment`.
6. It only contains the elements Ledgerly sends (with the real names, order and rules); the official schema has many more optional elements.
7. Floats can't represent most decimal amounts exactly and `str(float(Decimal("500")))` gives `500.0`; `:.2f` on a Decimal gives exact `500.00`.
8. It takes the 3-digit UAE bank code from characters 5–7 of the creditor's IBAN and sends it in `CdtrAgt/FinInstnId/Othr/Id`.
9. Not well-formed XML (syntax error), a DOCTYPE present, or schema violations (including the validator's own internal error). It returns error strings instead of raising so callers and tests get a clear list and a bad message can never crash the caller.
10. Both are random in real use; fixing them makes the output byte-identical every run, so any difference is a real change in the builder.
11. 13:59:59 Friday → same day, 27 Nov (Friday is a business day). 14:00:00 → next business day, Monday 30 Nov.
12. Raw XML: `Ali &amp; Sons &lt;FZE&gt;`. A parser reads back `Ali & Sons <FZE>`, unchanged.
13. The safe parser parses it without loading the DTD, resolving entities or touching the network, so the file is never read; `validate` sees the DOCTYPE and returns `["DOCTYPE is not allowed in payment messages"]` before schema validation.

</details>

---

# Part 5: Angular front end and login (Forge90 day 14)

This is the screen every UI test in the portfolio (Playwright TS and Python, Cypress) will drive. You don't have to become an Angular developer, but you should be able to read a component, find its `data-testid`s and explain how login and sessions work, because that's what UI tests fight with most.

Budget: two 2-hour sessions (concepts and running it in the first; tests and break-it in the second), plus the quiz.

## 32. Key concepts

**Angular 21, the modern way:**
- **Standalone components:** each component declares its own `imports`, with no NgModules.
- **Signals:** `signal()`, `computed()`. State that the template reads and that updates the view when it changes (`auth.isLoggedIn()`, `submitting()`).
- **Zoneless:** no zone.js. The view updates when signals change, not after every browser event. Tests wait with `await fixture.whenStable()`.
- **New control flow:** `@if`, `@for (... track ...)`, `@switch` in templates.
- **Lazy routes:** `loadComponent` downloads a page only when it's visited (the build shows `login` and `accounts` as separate chunks).

**Why Angular 21 and not 22?** Angular 22 needs Node 22.22+, and this Mac has 22.12. Angular 21 is in long-term support until mid-2027. Same reasoning as Django 5.2 LTS: choose what's supported and runs on the team's machines, and write the reason down.

**How login works, end to end:**

```
Login page --POST /api/auth/login/--> tokens --> stored --> GET /api/auth/me/ --> user signal --> go to returnUrl
Every API call: interceptor adds "Authorization: Bearer <access>"
401? --> POST /api/auth/refresh/ (once, shared) --> retry with the new token
Refresh fails? --> log out --> /login?returnUrl=...&expired=1 --> "Your session has expired"
```

| Piece | File | Job |
|---|---|---|
| `AuthService` | `core/auth.service.ts` | Tokens and user as signals; login, refresh (shared), logout. |
| `authInterceptor` | `core/auth.interceptor.ts` | Adds the token to `/api/` calls only (never to other sites or the public auth endpoints); refresh-and-retry on 401. |
| `authGuard` / `guestGuard` | `core/auth.guard.ts` | Private pages need a login; the login page bounces logged-in users. |
| `Login` | `pages/login/` | Reactive form, field errors, API errors by status, double-submit protection. |
| `Accounts` | `pages/accounts/` | Loading / error + retry / empty / list states. |
| `MoneyPipe` | `shared/money.pipe.ts` | `"32079.82"` → `AED 32,079.82` with string operations, never a float. |

**Where the tokens live, and the trade-off.** Tokens are in `localStorage` so a reload keeps you logged in and Playwright can save a logged-in state per role (P-02). The risk: any script injected into the page (XSS) can read them. A production bank would use **httpOnly, Secure, SameSite cookies** set by the server (unreadable by JavaScript), with CSRF protection. Being able to name this trade-off in an interview matters more than the choice itself.

**Open redirect.** `/login?returnUrl=https://evil.example` must not send a freshly logged-in customer to a phishing site. `safeReturnUrl` only accepts paths starting with a single `/`; `//evil.example` (a protocol-relative URL) is rejected too.

**One refresh for many failures.** When the access token expires, the accounts list and the profile request both get 401 at the same moment. Without sharing, each would call `/refresh/`. With rotation + blacklist (Part 1), the second refresh would use an already-used refresh token and get 401, logging the user out for no reason. `refresh()` keeps one in-flight call (`shareReplay`) for everyone. This was verified against the real API in the browser: two 401s produced exactly one refresh call, and both requests were retried.

**`data-testid` conventions:**
- Unique things: `login-email`, `login-submit`, `accounts-empty`.
- Repeated things: each row has `data-testid="account-<id>"` *and* `data-test-role="account"`, so a test can either find all rows or one specific account. Inside each row, `account-balance`, `account-iban`, `account-frozen`.
- Every state has its own id (`accounts-loading`, `accounts-error`, `accounts-retry`), so tests can wait for a state instead of sleeping.

## 33. How the front end is tested (53 Vitest tests)

- **`HttpTestingController`** replaces the network: tests see each request the app makes (method, URL, body, headers) and decide the response. `http.verify()` after each test fails if anything unexpected was sent, or an expected request never happened.
- The login tests drive the real template through `data-testid`s (type, click, read text), the same way a Playwright test will, just without a browser.
- **Mutation check:** 4 of 4 caught: allowing `//evil.example` as a return URL, sending the token to other sites, removing the shared refresh, refreshing on every error instead of only on 401.
- **Manual end-to-end check** against the real Django API: logged-out redirect with `returnUrl`; login as Sara; a broken access token refreshed silently; broken tokens all round → login page with "session expired".

## 34. Problems hit while building

- **npm 10.9 crashed while resolving the dependency tree** (`Cannot read properties of null (reading 'edgesOut')`), triggered by Vitest's optional peer packages. `--legacy-peer-deps` would hide it by skipping peer checks; instead the lockfile was created once with npm 11 (`npx npm@11.21.2 install`). `npm ci` with the default npm 10 then works from that lockfile, so CI needs nothing special.
- **A test configured TestBed after injecting from it.** In `TestBed.inject(Router).serializeUrl(run(guard))`, JavaScript evaluates `TestBed.inject(...)` *before* `run(...)`, which configures the module. Order of evaluation matters in tests too.

## 35. Run it

```bash
cd backend && python manage.py seed --reset && python manage.py runserver
```

```bash
cd frontend && npm ci && npm start
```

Open http://localhost:4200:
- [ ] Go straight to `/accounts`. Where do you land, and what's in the URL?
- [ ] Log in with a wrong password, then 11 times quickly. What messages appear?
- [ ] Log in as `lina@example.com`. How does the frozen account look?
- [ ] In DevTools → Application → Local Storage, edit `access` to garbage and reload. What happens in the Network tab?
- [ ] Try `/login?returnUrl=https://example.com` and log in. Where do you go?

```bash
cd frontend && npm test
```

## 36. Read it, in this order

| # | File | What to understand |
|---|---|---|
| 1 | `src/app/app.routes.ts`, `app.config.ts` | Routes, guards, lazy loading, the interceptor registration. |
| 2 | `core/auth.service.ts` | Signals; storage and its trade-off; shared refresh. |
| 3 | `core/auth.interceptor.ts` | Which requests get a token; refresh-and-retry. |
| 4 | `pages/login/login.ts` + `.html` | Form validation, error messages, `safeReturnUrl`. |
| 5 | `pages/accounts/*` | The four states and their test ids. |
| 6 | The `*.spec.ts` files | `HttpTestingController`, driving the template by test id. |

## 37. Break it

1. [ ] Remove `shareReplay(1)` from `refresh()`. Which test fails? With the real API, what would the user experience when two requests expire together?
2. [ ] Change `safeReturnUrl` to accept any string. Log in via `/login?returnUrl=https://example.com`. Explain the attack in one sentence.
3. [ ] Remove `[disabled]="submitting()"` from the login button. Which test fails? Why does a double-submitted login matter less than a double-submitted transfer (Part 3)?
4. [ ] Change the accounts list to show `account.balance` without the `money` pipe. Which tests fail, and what does the screen show?

## 38. Explain it

1. What's an HTTP interceptor, and what does this one do?
2. Why share one refresh call between failing requests?
3. Where are tokens stored, what's the risk, and what would production do?
4. What's an open redirect, and how is it prevented here?
5. Why give every UI state its own `data-testid`?
6. Mocked HTTP in unit tests vs the real API in E2E tests: what does each catch?
7. Why Angular 21 rather than 22?

## 39. Study material

- ⭐ [Angular: signals](https://angular.dev/guide/signals) and [HTTP interceptors](https://angular.dev/guide/http/interceptors)
- ⭐ [OWASP: Unvalidated redirects and forwards cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html)
- [Angular: testing HTTP requests](https://angular.dev/guide/http/testing)
- [OWASP: HTML5 security cheat sheet, local storage](https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html#local-storage)
- [Playwright: authentication and storage state](https://playwright.dev/docs/auth) (where P-02 picks up)

## 40. Quiz (tonight)

**Part A: concepts (1 point each)**

1. Name three modern Angular features used here.
2. Which requests does the interceptor add a token to?
3. What URL does a logged-out visitor to `/accounts` land on?
4. What does the login page show for a 401, a 429 and a network failure?
5. Which two `data-testid` attributes does each account row have?
6. Why does the money pipe never call `Number()`?

**Part B: read the code (2 points each)**

7. In `refresh()`, what do `finalize` and `shareReplay(1)` each do?
8. Why does the interceptor check `isPublic` before adding a token?
9. What does `http.verify()` in `afterEach` catch?
10. In the double-click test, how does it prove only one request was sent?

**Part C: predict, then run (3 points each)**

11. Both tokens in localStorage are garbage and the user opens `/accounts`. List the HTTP calls in order and where the user ends up.
12. `returnUrl=//evil.example/login`. Where does the user go after logging in, and why?
13. A Playwright test logs in once, saves storage state, and reuses it for 30 minutes of tests. The access token lasts 15 minutes. What happens at minute 16, and which code makes the tests keep passing?

<details>
<summary>Answers</summary>

1. Any three of: standalone components, signals/computed, zoneless change detection, `@if`/`@for`/`@switch` control flow, lazy `loadComponent` routes, functional interceptors and guards, router input binding.
2. Same-site `/api/` calls, except login, refresh, register and health; never requests to other sites.
3. `/login?returnUrl=%2Faccounts`.
4. 401: "Email or password is incorrect." 429: "Too many attempts. Please wait a minute and try again." Network failure (status 0): "Can't reach Ledgerly Bank. Check your connection and try again."
5. `data-testid="account-<id>"` and `data-test-role="account"`.
6. Converting to a JavaScript number turns the amount into a float, which can't represent every cent exactly; string operations show exactly what the API sent.
7. `shareReplay(1)` makes concurrent subscribers share one HTTP call and its result; `finalize` clears `refreshInFlight` when it completes or fails, so the next expiry starts a fresh refresh.
8. Public endpoints don't need a token, and a 401 from login (wrong password) must not trigger a refresh loop.
9. Requests the app made that no test expected, or expected requests that were never sent.
10. After the button is disabled, a second click is attempted and then `http.expectOne('/api/auth/login/')` passes: `expectOne` fails if there were two matching requests.
11. `GET /api/auth/me/` and `GET /api/accounts/` → both 401 → one `POST /api/auth/refresh/` → 401 → logout → `/login?returnUrl=%2Faccounts&expired=1` with the "session expired" notice.
12. `/accounts`: `safeReturnUrl` rejects anything starting with `//` (a protocol-relative URL that would leave the site).
13. The first API call after minute 15 gets 401; the interceptor refreshes with the stored refresh token (valid for 1 day) and retries, so the test continues. One catch: rotation stores a *new* refresh token in that browser context only, so parallel workers that share the same saved state can invalidate each other's refresh token. That's a real issue P-02 will have to handle, e.g. a fresh login per worker.

</details>

---

# Part 6: Dashboard and statement screens (Forge90 day 15)

The first screens with real data on them: a dashboard with an exact total, and a statement with filters, pagination and a running balance. These are the pages P-02 (Playwright) will test most, and they're full of classic UI-test traps: time zones, stale responses, URLs as input, and labels.

Budget: one 2-hour session plus the quiz.

## 41. Key concepts

**The URL is the source of truth for the filters.** `/accounts/7?direction=DEBIT&search=coffee` can be bookmarked, shared, reloaded, and the browser's Back button undoes a filter. The router binds each query parameter to a component input (`withComponentInputBinding`), and the form only *shows* what the URL says. "Apply" doesn't fetch anything; it changes the URL, and the URL change causes the fetch.

**But the URL is user input.** Anyone can type `?page=-1&direction=SIDEWAYS`. `parseQuery()` keeps only valid values (positive whole page numbers, known directions and categories, `YYYY-MM-DD` dates, search up to 100 characters) and drops the rest before anything reaches the API.

**Stale responses: `switchMap`.** If the user changes filters faster than the API answers, two requests are in flight. Without care, the slower, *older* response can arrive last and overwrite the newer one: the screen says "Salary" but shows card purchases. `switchMap` unsubscribes from the previous request when a new one starts (Angular then cancels it), so only the latest answer can ever be shown. A test proves it: it checks `request.cancelled`.

**Two kinds of 404.** DRF answers 404 both for someone else's account and for a page past the end (`?page=99` → `"Invalid page."`). The page tells them apart: a 404 on the account means "not found or not yours" (no hint whether it exists, Part 2); a 404 on page > 1 means "that page doesn't exist", with a link to page 1.

**Exact totals.** `0.1 + 0.2` in JavaScript is `0.30000000000000004`. The dashboard total converts each balance string to whole cents as a `BigInt`, adds, and converts back (`shared/money.ts`). Totals are per currency: adding AED to USD gives a meaningless number.

**Dubai time, whatever the computer's time zone.** Dates use `date: 'd MMM y, HH:mm' : '+0400'`. A transaction at `23:30Z` on 20 Nov is shown as `21 Nov, 03:30`, because the bank's day is Dubai's day (the daily limit in Part 3 uses the same rule).

**Labels for people and for tests.** A `<label>` wrapped around a `<select>` makes the control's accessible name "Type All": the label text plus the selected option. Separate `<label for="f-direction">` elements give exactly "Type". That's what a screen reader announces, and what Playwright's `getByLabel('Type', { exact: true })` (P-02) will match.

**New test ids:** `total-amount`, `total-AED`; statement: `statement-header`, `statement-balance`, `filter-direction` / `-category` / `-from` / `-to` / `-search`, `filter-apply`, `filter-clear`, `filter-error`, rows with `data-test-role="transaction"` and `data-testid="tx-<reference>"` (each row has `tx-date`, `tx-description`, `tx-category`, `tx-amount`, `tx-balance`), `page-prev`, `page-next`, `page-info`, and one id per state (`statement-loading`, `-error`, `-empty`, `-not-found`, `-no-such-page`, `-bad-filter`).

## 42. How it's tested (94 Vitest tests)

- **`RouterTestingHarness`** opens the page through the real router, with a real URL, so the tests cover the URL → input → request chain and can assert `router.url` after clicking Apply or Next.
- The key tests: filters from the URL reach the API; junk in the URL never does; Apply resets to page 1 and doesn't refetch the account header; reversed dates are refused without a request; a slow old response is cancelled; pagination keeps the filters; both 404s; a 400 shows the API's message; retry after a 500; labels name each control exactly.
- **Tests run in UTC** (`TZ=UTC` in `package.json`), and `tz.spec.ts` fails if they don't.
- **Mutation check, 6 of 6 caught, after two fixes:** `switchMap` → `mergeMap`; dates without `+0400`; `in` instead of `Object.hasOwn`; no From/To check; filters keeping the old page; totals added as floats. The first run **missed two**:
  - *The time zone.* This Mac is set to Dubai (+04), so dates looked right without `'+0400'`. CI (UTC) would have caught it, but only after a push. Fixed by pinning the tests to UTC.
  - *The float total.* `toFixed(2)` rounds normal-sized float errors away, and the one big-number case passed by luck (round-half-to-even landed on the right answer). Added `9007199254740993.01` alone: as a float it becomes `...992.00`.
- **Manual check against the real API** (Sara): total 28,910.53 + 14,632.63 = 43,543.16; running balances consistent row to row; filters from the URL; page 2 of 5; `?page=99` → "That page doesn't exist"; Omar's account → "Account not found"; reversed dates refused; no horizontal scroll at 375 px wide.

## 43. Bugs found while building

1. **`'toString' in CATEGORIES` is `true`.** The `in` operator also looks at inherited properties, so `?category=toString` passed validation and would have been sent to the API. A test written for exactly this case caught it; `Object.hasOwn` fixed it.
2. **Wrapped labels gave the filters the wrong names** ("Type All"). Found while reading the page's accessibility tree in the browser. Fixed with `<label for>`; a test now checks each control's label text is exactly its name.
3. **The browser tool's `form_input` didn't fire Angular's `input` event** on date fields, so the reversed-date error didn't show during the manual check. Dispatching a real `input` event showed it working. This was a tool artifact, not an app bug; checking it rather than assuming took one minute.
4. **The first mutation run missed two sabotages** (time zone, float total). See §42.

## 44. Run it

```bash
cd backend && python manage.py runserver
```

```bash
cd frontend && npm start
```

Log in as `sara@example.com` and:
- [ ] Add up the two account balances yourself. Does the total match to the fils?
- [ ] Open Everyday. Check three rows: does each balance equal the row below plus this row's amount (for money out)?
- [ ] Filter "Money out" + search "coffee". Copy the URL into a new tab. Same result?
- [ ] Press the browser's Back button. What happens to the filters?
- [ ] Try `?page=99`, `?page=-1`, `?category=toString`, and `/accounts/9`. What does each show, and what request does each send (DevTools → Network)?
- [ ] Make the window narrow (DevTools device toolbar). Which column disappears?

## 45. Read it, in this order

| # | File | What to understand |
|---|---|---|
| 1 | `shared/money.ts` + spec | Cents as `BigInt`; why the big-number test is the one that matters. |
| 2 | `pages/accounts/accounts.ts` | `totalsByCurrency`, `computed()`. |
| 3 | `pages/statement/statement.ts`: `parseQuery`, `toParams` | Treating the URL as input. |
| 4 | Same file, the constructor | `toObservable` + `switchMap`; why the header and the list are separate streams. |
| 5 | `statement.html` | States, test ids, `<label for>`, the date pipe's time zone. |
| 6 | `statement.spec.ts` | `RouterTestingHarness`, `request.cancelled`, `router.url`. |

## 46. Break it

1. [ ] Replace `switchMap` with `mergeMap` in the transactions stream. Which test fails, and what would a user see on a slow network?
2. [ ] Remove `: '+0400'` from the date pipe and run `npm test`. Then run `npx ng test --watch=false` (no `TZ=UTC`). Explain the difference.
3. [ ] Put the `<label>` back around the Type `<select>`. Which test fails? What would `page.getByLabel('Type', { exact: true })` find?
4. [ ] In `applyFilters`, keep the current page instead of starting at page 1. Describe the bug a user hits on page 4 who filters down to 3 results.

## 47. Explain it

1. Why is the URL, not the form, the source of truth for filters?
2. What's a stale response, and how does `switchMap` prevent it?
3. Why can't the dashboard add balances with `Number()`?
4. Why are the tests pinned to UTC when the bank is in Dubai?
5. How does the page tell "not your account" from "page past the end", when both are 404?
6. Why does a wrapped label hurt both accessibility and test locators?

## 48. Quiz (tonight)

**Part A: concepts (1 point each)**

1. What does `withComponentInputBinding` do on the statement page?
2. Name four things `parseQuery` refuses.
3. Why does the dashboard show one total per currency?
4. What does `Object.hasOwn(obj, key)` check that `key in obj` doesn't?
5. Which `data-testid` would you wait for to know the statement finished loading with results?

**Part B: read the code (2 points each)**

6. Why are the account header and the transaction list loaded by two separate streams?
7. What does bumping `attempt` do, and why is it part of the `request` computed?
8. In `toParams`, why is page 1 left out of the URL?
9. In the stale-response test, what does `slow.cancelled` prove?

**Part C: predict, then run (3 points each)**

10. The user is on `?direction=DEBIT&page=3` and clicks Apply after choosing "Card purchase". What's the new URL, and how many HTTP requests are sent?
11. On a Mac set to Dubai, someone removes `'+0400'` and runs `npx ng test --watch=false` without `TZ=UTC`. Do the tests pass? What happens in CI?
12. A Playwright test types "coffee" in Search, clicks Apply, then immediately asserts the row count. The API takes 2 seconds. What does the test see, and what should it wait for instead?

<details>
<summary>Answers</summary>

1. The router passes the `:id` path parameter and each query parameter (`page`, `direction`, ...) into the component's inputs, so the component reads them as signals.
2. Any four of: page 0, negative, decimal or non-numeric; unknown direction; unknown or inherited category (`toString`); dates not in `YYYY-MM-DD`; search over 100 characters (cut to 100).
3. Adding amounts in different currencies gives a meaningless number; AED 100 + USD 50 is not 150 of anything.
4. Only the object's own properties; `in` also finds inherited ones like `toString`.
5. `statement-table` (or `statement-count`, or rows with `data-test-role="transaction"`); `statement-empty` if no results.
6. The header depends only on the account id; the list depends on the id and the filters. Separate streams mean changing a filter doesn't refetch the header.
7. It makes the `request` computed produce a new value even though the id and filters are the same, so `toObservable` emits and `switchMap` fetches again ("Try again").
8. Page 1 is the default, so `?page=1` would make two URLs for the same view and add noise to bookmarks.
9. That `switchMap` unsubscribed from the first request when the URL changed, so its response can never reach the screen.
10. `/accounts/7?direction=DEBIT&category=CARD`. One request (transactions with `direction=DEBIT&category=CARD`, no page); the account header isn't refetched.
11. Locally they pass: the machine's zone is +04 already. In CI (UTC) the Dubai-time test fails. With `TZ=UTC` (and `tz.spec.ts`), it fails locally too, before the push.
12. It may still see the old rows (or the loading state) and fail, or pass by luck. It should wait for the result: e.g. `expect(page.getByTestId('statement-count')).toHaveText(/13 transactions/)` or the URL plus `statement-table`, using Playwright's auto-retrying assertions, never a fixed sleep.

</details>
