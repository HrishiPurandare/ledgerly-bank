# Ledgerly Bank

![CI](https://github.com/HrishiPurandare/ledgerly-bank/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Django](https://img.shields.io/badge/Django-5.2%20LTS-0C4B33)
![Angular](https://img.shields.io/badge/Angular-21-DD0031)

A small, realistic banking app built **to be tested**. It's the shared system under test for my test-automation portfolio: Playwright, API, Cypress and Kubernetes projects all run against it, and the [Ask Ledgerly chatbot](https://github.com/HrishiPurandare/ai-quality-engineering-lab) answers questions about the same bank's policies.

Ledgerly Bank is fictional. All customers, accounts and money are invented test data.

![Statement screen: filters, running balance, Dubai time](docs/statement.jpg)

## What's in it

| Area | Status |
|---|---|
| REST API: Django 5.2 LTS + Django REST Framework | ✅ |
| JWT login with rotating, blacklisted refresh tokens; rate-limited auth | ✅ |
| OpenAPI 3 spec (committed, checked in CI) + Swagger UI | ✅ |
| Accounts and statements (filters, pagination), owner-only access, deterministic seed data | ✅ |
| Beneficiaries (OTP by email) and transfers with the bank's real limit rules, idempotency and row locking | ✅ |
| ISO 20022 `pacs.008` messages for transfers to other banks (schema-validated, golden-file tested) | ✅ |
| Angular 21 front end: login, session refresh, route guards, `data-testid` everywhere | ✅ |
| Dashboard (exact totals) and statements (filters in the URL, pagination, Dubai time) | ✅ |
| Beneficiaries (add, emailed code, lock after 3 wrong codes) and transfers (review step, idempotent retries, plain-language limit errors) | ✅ |
| Docker Compose: Postgres, API (gunicorn, DEBUG off), web (nginx, CSP), Mailpit for OTP emails | ✅ |

## Run with Docker (the whole bank, one command)

```bash
echo "DJANGO_SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n/+=')" > .env   # once
docker compose up --build --wait
```

| Open | What |
|---|---|
| http://localhost:8080 | The bank. Log in as `sara@example.com` / `Ledgerly-Demo-2026` (also `omar@`, `lina@`) |
| http://localhost:8025 | Mailpit: the inbox that catches OTP emails |
| http://localhost:8080/api/docs/ | API documentation (Swagger UI) |

Production-like on purpose: DEBUG off, gunicorn, Postgres 17, real SMTP, non-root containers, strict security headers, ports bound to localhost only. Demo data is created on the first start. `docker compose down -v` removes everything, including the database.

## Quick start (without Docker)

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py seed             # demo customers: sara@ / omar@ / lina@example.com, password Ledgerly-Demo-2026
python manage.py runserver        # http://localhost:8000/api/docs
```

```bash
cd frontend                       # second terminal; Node 22
npm ci && npm start               # http://localhost:4200 (proxies /api to :8000)
```

## Tests

```bash
cd backend && pytest -q           # 159 API tests (+3 concurrency tests on Postgres)
cd frontend && npm test           # 132 Angular unit tests (Vitest, run in UTC)
```

CI runs every API test on **SQLite and Postgres 17**, fails on missing migrations, and fails if the committed `openapi.yaml` no longer matches the code (an unreviewed API contract change).

## Design choices

- **Secure by default.** Every endpoint needs a login unless it's on a four-item allowlist, and a test walks the OpenAPI schema to prove it: a new endpoint with a forgotten permission fails CI.
- **A customer only ever sees their own money.** Someone else's account is a 404 with the same body as an account that doesn't exist, so probing ids reveals nothing (OWASP API #1, broken object-level authorization).
- **Transfer rules come from the bank's published policy**, the same text the Ask Ledgerly chatbot answers from: AED 50,000 a day per customer across all accounts, AED 10,000 in the first 24 hours to a new beneficiary, up to 100 beneficiaries, OTP to add one. Each rule is tested at its exact boundary (AED 50,000.00 passes, 0.01 more is refused).
- **Money moves inside one database transaction with row locks**: the customer first (so two accounts can't both slip under the daily limit), then the accounts in id order (no deadlocks). Concurrency tests fire 10 transfers at the same instant on Postgres.
- **Idempotency keys**: a retried or double-clicked transfer replays the first response (`Idempotent-Replayed: true`) and never pays twice; reusing a key for a different transfer is a 409.
- **ISO 20022 pacs.008 for every transfer to another bank** (`GET /api/transfers/{id}/pacs008/`): built with lxml, validated against a subset XSD written from the published pacs.008.001.08 definition (real element names, order and data rules; not the official file), settlement date from the bank's 2 PM cut-off and the UAE Saturday–Sunday weekend, names escaped, and any DOCTYPE refused (XXE).
- **Money is `Decimal`, sent as a string** (`"1000.00"`), never a float.
- **Deterministic demo data.** The same seed always gives the same customers, IBANs (valid mod-97 check digits) and statements, and a test proves every balance equals the sum of its transactions. The seed command refuses to run with DEBUG off, because its passwords are public.
- **No user enumeration.** A wrong password and an unknown email get the same 401 response.
- **Refresh tokens rotate and the old one is blacklisted**, so a stolen, already-used refresh token can't be replayed.
- **The web app treats the session carefully**: an expired access token is refreshed silently, and requests that fail together share **one** refresh call (verified against the real API). If the refresh fails, the user lands on the login page with a "session expired" message and is sent back to where they were afterwards. `returnUrl` only accepts same-site paths, so the login page can't be used as an open redirect.
- **The statement's filters live in the URL**, so a filtered statement can be bookmarked, shared and undone with Back. The URL is treated as user input (junk like `?page=-1` or `?category=toString` never reaches the API), and `switchMap` cancels an older request when filters change, so a slow stale response can never overwrite a newer one.
- **The transfer screen never pays twice.** One `Idempotency-Key` per reviewed transfer, reused on every retry. A timeout or 5xx is shown as *"we can't tell whether it went through; trying again is safe"*, never as "failed" (which pushes people to start a second payment). Verified by stopping the API mid-transfer, restarting it and retrying: exactly one payment. Business errors carry a stable code (`data-error-code` on the page), so tests assert the rule, not the wording.
- **Money on screen is exact**: totals are added in whole cents (`BigInt`), never floats, and per currency. Dates are shown in Dubai time whatever the browser's time zone, and the unit tests run in UTC so a missing time zone fails on every machine, not only in CI.
- **Django 5.2 LTS**, not the newest 6.x: supported until 2028, and every dependency here is proven on it. Likewise **Angular 21 (LTS until mid-2027)**, because Angular 22 needs Node 22.22+.

## License

[MIT](LICENSE)
