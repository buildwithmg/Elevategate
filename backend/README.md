# ElevateGate Backend

FastAPI + PostgreSQL backend for the ElevateGate endpoint privilege-approval system. Windows
agents submit elevation requests; IT administrators review and approve/deny them in a dashboard
(not included here — this is the API it would call); approved requests get a signed, single-use,
short-lived Ed25519 token the agent verifies before executing anything.

See also: [docs/API_CONTRACT.md](../docs/API_CONTRACT.md) (the full HTTP contract and the exact
signed-payload byte layout) and [docs/BACKEND_THREAT_MODEL.md](../docs/BACKEND_THREAT_MODEL.md).

## Stack

Python 3.12, FastAPI, SQLAlchemy 2 (async, via `psycopg` v3), Alembic, Pydantic v2, PyJWT,
Argon2id (`argon2-cffi`), Ed25519 (`cryptography`), `slowapi` rate limiting.

## Local development (without Docker)

Prerequisites: Python 3.12, a running PostgreSQL 16 instance.

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

createdb elevategate
createdb elevategate_test   # used by the test suite

cp .env.example .env
# Fill in JWT_SECRET_KEY, ENROLLMENT_KEY, ED25519_PRIVATE_KEY_B64 (see secrets/README.md for how
# to generate an Ed25519 keypair), and point DATABASE_URL at the `elevategate` database above.

alembic upgrade head
uvicorn app.main:app --reload
```

Interactive API docs: http://localhost:8000/docs (Swagger UI) or http://localhost:8000/redoc.
Raw OpenAPI schema: http://localhost:8000/openapi.json.

Seed the first administrator:

```bash
ADMIN_EMAIL=admin@example.com ADMIN_NAME="IT Admin" ADMIN_PASSWORD='a-strong-password' \
    python -m scripts.seed_admin
```

(Omit the env vars to be prompted interactively, with the password entered via `getpass` — never
echoed or logged. Safe to re-run: it's a no-op if that email already has an account.)

## Running the tests

```bash
source .venv/bin/activate
python -m pytest
```

Tests run against a **real** local PostgreSQL database (`elevategate_test`), not mocks or SQLite —
including the concurrency test that fires two simultaneous approve calls at the same request and
asserts exactly one wins. Each test truncates all tables first (see `tests/conftest.py`), so tests
are isolated but not sandboxed inside a rolled-back transaction — don't point `DATABASE_URL` at a
database you care about when running the suite.

## Running with Docker Compose

```bash
cd backend
cp .env.example .env   # fill in POSTGRES_PASSWORD, JWT_SECRET_KEY, ENROLLMENT_KEY
mkdir -p secrets
# generate an Ed25519 keypair and save the private key - see secrets/README.md
echo "<base64-private-key>" > secrets/ed25519_private_key.b64

docker compose up --build
```

This builds the backend image, starts PostgreSQL, runs `alembic upgrade head` automatically on
container start (see `docker-entrypoint.sh` — fine for a single backend replica; a multi-replica
deployment should run migrations as one separate release step instead), and serves the API on
`http://localhost:8000`.

**Note on this deliverable**: the Dockerfile and docker-compose.yml were written and carefully
reviewed, but there was no Docker available in the environment this backend was built in, so they
were not actually built/run to confirm they boot end-to-end — unlike the rest of this backend,
which was verified against a real local PostgreSQL instance and a real `pytest` run. Please do a
`docker compose up --build` smoke test before relying on this in production.

Then seed the first admin inside the running container:

```bash
docker compose exec backend python -m scripts.seed_admin
```

## Project layout

```
app/
  main.py               FastAPI app factory, routers, rate-limit wiring
  config.py              Settings (env vars / .env)
  database.py             Async SQLAlchemy engine/session
  models/                  SQLAlchemy ORM: admin_user, device, elevation_request, approval, audit_log
  schemas/                  Pydantic request/response models
  repositories/              DB access per entity (including the atomic race-safe update patterns)
  core/
    security.py               Argon2id hashing, JWT
    signing.py                 Ed25519 canonical payload + signing
    audit.py                    write_audit_log()
    rate_limit.py                 slowapi Limiter
  api/
    deps.py                        get_db, get_current_admin, require_role, get_current_device
    v1/                              one router module per endpoint group
alembic/                            migrations
tests/
  unit/                              no DB required
  integration/                        real Postgres + real HTTP requests via httpx.AsyncClient
scripts/seed_admin.py                bootstrap the first administrator
```
