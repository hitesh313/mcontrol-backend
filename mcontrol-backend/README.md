# Money Control API

Production-oriented FastAPI backend for a personal money-lending / borrowing
tracker, backed by Supabase PostgreSQL. Tracks multi-level money chains
(Supplier → User → Customer → Customer → ...), ledgers, interest, due dates,
and notifications, with a clean-architecture (api → service → repository)
layout.

## Status

This is the initial production-foundation slice: project skeleton, database
schema, and a fully working **Auth** module (register / login / refresh /
forgot-password via OTP / reset-password) plus **Suppliers** and
**Customers** CRUD. See [Roadmap](#roadmap) for what's next (money-flow
engine, loans, interest engine, notifications, audit logging).

## Architecture

```
app/
├── api/            # FastAPI routers (HTTP layer only — no business logic)
│   ├── deps.py      # shared dependencies: DB session, JWT auth guard
│   └── v1/          # versioned routes
├── core/           # config (env settings) and security (JWT, bcrypt, OTP)
├── database/        # Supabase client singleton
├── schemas/         # Pydantic request/response models (validation layer)
├── repositories/     # data access — all Supabase queries live here
├── services/         # business logic, orchestrates repositories
├── middleware/        # CORS, rate limiting, global error handling
├── notifications/     # (planned) FCM push + SMS/OTP dispatch
└── utils/             # exceptions, shared helpers
sql/
└── schema.sql        # full Postgres schema — run this in Supabase first
```

Each layer only talks to the layer directly below it: **route → service →
repository → Supabase**. Business rules (password strength, chain
integrity, interest math) live in `services/`, never in routes.

## Setup

### 1. Provision the database
Open your Supabase project's SQL editor and run `sql/schema.sql` in full.
It creates all tables, indexes, triggers, and Row-Level-Security policies.

### 2. Configure environment
```bash
cp .env.example .env
```
Fill in:
- `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` — from Supabase Project Settings → API.
  **The service role key must stay server-side only** — never ship it to the Flutter app.
- `JWT_SECRET_KEY` — generate with `openssl rand -hex 32`.

### 3. Install & run
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```
API docs at `http://localhost:8000/docs` (disabled automatically when `APP_ENV=production`).

### 4. Run tests
```bash
pytest
```

## Authentication flow

1. `POST /api/v1/auth/register` — creates the user, hashes password with bcrypt.
2. `POST /api/v1/auth/login` — verifies credentials, returns a short-lived
   JWT **access token** (15 min default) and an opaque **refresh token**.
   Only the refresh token's SHA-256 hash is stored server-side.
3. Protected routes require `Authorization: Bearer <access_token>`.
4. `POST /api/v1/auth/refresh` — rotates the refresh token: the old one is
   revoked and a new pair is issued. This limits the blast radius of a
   leaked refresh token to a single use.
5. `POST /api/v1/auth/forgot-password` → `verify-otp` → `reset-password` —
   OTP is hashed at rest and expires after `OTP_EXPIRE_MINUTES`. Resetting
   the password revokes all existing refresh tokens (forces re-login
   everywhere).

**TODO before production:** wire an SMS provider (Twilio, MSG91, etc.) in
`app/notifications/` to actually deliver the OTP — currently
`request_password_reset` only generates/stores it.

## Security notes

- Passwords hashed with bcrypt (per-password salt).
- JWT access tokens are short-lived; refresh tokens are rotated and stored
  as hashes only, so a stolen DB backup cannot be used to forge sessions.
- Every repository query is explicitly scoped by `user_id` (defense against
  IDOR), *and* Postgres Row-Level-Security policies in `sql/schema.sql`
  provide a second layer in case a query ever forgets to filter.
- Rate limiting via `slowapi` (`RATE_LIMIT_DEFAULT`, tighten
  `RATE_LIMIT_AUTH` further on `/auth/*` routes in production).
- Pydantic validates and rejects malformed input at the edge before it
  reaches business logic or the database (parameterized queries via
  supabase-py — no raw SQL string concatenation anywhere).
- CORS origins are explicit (`ALLOWED_ORIGINS`), not wildcard, in production.

## Roadmap

| Module | Status |
|---|---|
| Auth (register/login/refresh/forgot-password) | ✅ Done |
| Suppliers / Customers CRUD | ✅ Done |
| Loans & money-flow engine (chain tracking) | 🔜 Schema ready (`loans`, `money_flows`), service layer next |
| Interest engine (fixed/percent, daily/monthly) | 🔜 Schema ready (`loan_interest`) |
| Ledger / transactions | 🔜 Schema ready (`transactions`) |
| Dashboard aggregates | 🔜 |
| Notifications (FCM push + reminders) | 🔜 Schema ready (`notifications`) |
| Notes module | 🔜 Schema ready (`notes`) |
| Audit logging | 🔜 Schema ready (`audit_logs`) |
| Scheduled jobs (due-date reminders, interest accrual) | 🔜 (Celery/APScheduler or Supabase Edge Functions + pg_cron) |

## Deployment

Any ASGI-friendly host works (Render, Fly.io, AWS). Minimal setup:
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Set all `.env` values as platform environment variables/secrets — never
  commit `.env`.
- Set `APP_ENV=production` to disable `/docs` and `/redoc`.
