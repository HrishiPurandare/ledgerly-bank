# Ledgerly Bank

![CI](https://github.com/HrishiPurandare/ledgerly-bank/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Django](https://img.shields.io/badge/Django-5.2%20LTS-0C4B33)

A small, realistic banking app built **to be tested**. It's the shared system under test for my test-automation portfolio: Playwright, API, Cypress and Kubernetes projects all run against it, and the [Ask Ledgerly chatbot](https://github.com/HrishiPurandare/ai-quality-engineering-lab) answers questions about the same bank's policies.

Ledgerly Bank is fictional. All customers, accounts and money are invented test data.

## What's in it

| Area | Status |
|---|---|
| REST API: Django 5.2 LTS + Django REST Framework | ✅ |
| JWT login with rotating, blacklisted refresh tokens; rate-limited auth | ✅ |
| OpenAPI 3 spec (committed, checked in CI) + Swagger UI | ✅ |
| Accounts and statements (filters, pagination), owner-only access, deterministic seed data | ✅ |
| Beneficiaries (OTP by email) and transfers with the bank's real limit rules, idempotency and row locking | ✅ |
| ISO 20022 `pacs.008` payment messages | 🔜 |
| Angular front end with `data-testid` everywhere | 🔜 |
| Docker Compose (Postgres + API + UI) | 🔜 |

## Quick start (API)

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py seed             # demo customers: sara@ / omar@ / lina@example.com, password Ledgerly-Demo-2026
python manage.py runserver        # http://localhost:8000/api/docs
```

## Tests

```bash
cd backend && pytest -q
```

CI runs every test on **SQLite and Postgres 17**, fails on missing migrations, and fails if the committed `openapi.yaml` no longer matches the code (an unreviewed API contract change).

## Design choices

- **Secure by default.** Every endpoint needs a login unless it's on a four-item allowlist, and a test walks the OpenAPI schema to prove it: a new endpoint with a forgotten permission fails CI.
- **A customer only ever sees their own money.** Someone else's account is a 404 with the same body as an account that doesn't exist, so probing ids reveals nothing (OWASP API #1, broken object-level authorization).
- **Transfer rules come from the bank's published policy**, the same text the Ask Ledgerly chatbot answers from: AED 50,000 a day per customer across all accounts, AED 10,000 in the first 24 hours to a new beneficiary, up to 100 beneficiaries, OTP to add one. Each rule is tested at its exact boundary (AED 50,000.00 passes, 0.01 more is refused).
- **Money moves inside one database transaction with row locks**: the customer first (so two accounts can't both slip under the daily limit), then the accounts in id order (no deadlocks). Concurrency tests fire 10 transfers at the same instant on Postgres.
- **Idempotency keys**: a retried or double-clicked transfer replays the first response (`Idempotent-Replayed: true`) and never pays twice; reusing a key for a different transfer is a 409.
- **Money is `Decimal`, sent as a string** (`"1000.00"`), never a float.
- **Deterministic demo data.** The same seed always gives the same customers, IBANs (valid mod-97 check digits) and statements, and a test proves every balance equals the sum of its transactions. The seed command refuses to run with DEBUG off, because its passwords are public.
- **No user enumeration.** A wrong password and an unknown email get the same 401 response.
- **Refresh tokens rotate and the old one is blacklisted**, so a stolen, already-used refresh token can't be replayed.
- **Django 5.2 LTS**, not the newest 6.x: supported until 2028, and every dependency here is proven on it.

## License

[MIT](LICENSE)
