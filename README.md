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
| Accounts, transactions, seed data | 🔜 |
| Beneficiaries and transfers with real limit rules | 🔜 |
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
python manage.py runserver        # http://localhost:8000/api/docs
```

## Tests

```bash
cd backend && pytest -q
```

CI runs every test on **SQLite and Postgres 17**, fails on missing migrations, and fails if the committed `openapi.yaml` no longer matches the code (an unreviewed API contract change).

## Design choices

- **Secure by default.** Every endpoint needs a login unless it's on a four-item allowlist, and a test walks the OpenAPI schema to prove it: a new endpoint with a forgotten permission fails CI.
- **No user enumeration.** A wrong password and an unknown email get the same 401 response.
- **Refresh tokens rotate and the old one is blacklisted**, so a stolen, already-used refresh token can't be replayed.
- **Django 5.2 LTS**, not the newest 6.x: supported until 2028, and every dependency here is proven on it.

## License

[MIT](LICENSE)
