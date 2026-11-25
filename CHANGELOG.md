# Changelog

All notable changes to NovaBank. Dates are when the work was done.

## [1.1.0] - 2026-11-25

### Changed
- **Renamed from Ledgerly Bank to NovaBank** (repo `ledgerly-bank` → `novabank`; the chatbot "Ask Ledgerly" is now NovaAsk). Settings `LEDGERLY_*` → `NOVABANK_*`, demo password `NovaBank-Demo-2026`, browser storage key `novabank.auth`, fictional BIC `NOVAAEADXXX`, emails from `no-reply@novabank.example`, Compose project and database `novabank`. No behaviour changes.

### Fixed
- Stack smoke test: the limit check now uses the richest account and states its precondition, instead of assuming the first account holds more than AED 10,000.01.

## [1.0.0] - 2026-11-24

The first complete version: a fictional bank you can run with one command, built to be the system under test for the rest of the portfolio.

### API (Django 5.2 LTS + DRF)
- Email login with JWTs: rotating refresh tokens, blacklisted after use; rate-limited login; no user enumeration.
- Accounts and statements: owner-only access (another customer's account is a 404), filters, pagination, immutable ledger with running balance, deterministic demo data (UAE IBANs with valid check digits).
- Beneficiaries confirmed with an emailed 6-digit code (hashed at rest, 5-minute expiry, locked after 3 wrong codes).
- Transfers between own accounts, to other NovaBank customers and to other UAE banks, with the bank's published limits (AED 50,000 a day, AED 10,000 to a new beneficiary in the first 24 hours, 100 beneficiaries), idempotency keys and row locking.
- ISO 20022 `pacs.008.001.08` messages for transfers to other banks: schema-validated, golden-file tested, 2 PM cut-off and Saturday-Sunday weekend, DOCTYPE refused (XXE).
- OpenAPI 3 spec committed and checked in CI; secure by default (a test walks the schema).

### Web (Angular 21)
- Login with silent, shared token refresh and safe return URLs; route guards.
- Dashboard with exact totals (whole cents, per currency).
- Statement with filters kept in the URL, pagination, Dubai time.
- Beneficiaries with the emailed code; transfers with a review step and idempotent retries ("we can't tell whether it went through; trying again is safe").
- `data-testid` on everything tests need; every state has its own id.

### Running it
- Docker Compose: Postgres 17, the API under gunicorn (DEBUG off, non-root), nginx with a strict Content Security Policy, Mailpit for emails. Health-checked start order; ports bound to localhost.

### Testing
- 161 API tests (SQLite and Postgres; 3 concurrency tests need Postgres), 134 Angular unit tests (in UTC), a 29-check smoke test against the running containers. CI runs all of them, plus lint, migration and OpenAPI drift checks, on every push.

### Fixed along the way
- A race let two simultaneous transfers exceed the daily limit (caught by the Postgres CI job).
- `seed --reset` failed once demo customers had made transfers.
- The README quick start didn't read `backend/.env`.
- Limit messages showed `AED 10000.00` instead of `AED 10,000.00`.
- Critical-CSS inlining was blocked by the CSP, leaving pages half-styled in production builds.
- A failed code email left an unconfirmable beneficiary behind; server errors weren't logged with DEBUG off.
