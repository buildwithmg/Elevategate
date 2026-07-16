import os

# Must happen before anything under `app` is imported, since Settings() reads the environment
# eagerly and app.database module-level engine binds to it at import time.
os.environ["DATABASE_URL"] = "postgresql+psycopg://localhost/elevategate_test"
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-not-for-production-use")
os.environ.setdefault("ENROLLMENT_KEY", "test-enrollment-key-not-for-production-use")
os.environ.setdefault("ED25519_PRIVATE_KEY_B64", "OB79CTrGXPQ2LIY3ntr1bbCGe16PeO9EQpn6GpSazIY=")
# Generous rate limits by default so ordinary test traffic never trips slowapi; a dedicated test
# exercises the rate limiter itself with its own tight, explicit override.
for _var in (
    "RATE_LIMIT_ENROLL",
    "RATE_LIMIT_HEARTBEAT",
    "RATE_LIMIT_ELEVATION_REQUEST_SUBMIT",
    "RATE_LIMIT_AGENT_DECISIONS",
    "RATE_LIMIT_APPROVAL_CONSUMED",
    "RATE_LIMIT_LOGIN",
):
    os.environ.setdefault(_var, "100000/minute")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import create_app  # noqa: E402

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

test_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

_TABLES = (
    "approvals, elevation_requests, app_allowlist_entries, devices, device_groups, "
    "admin_users, audit_logs"
)


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    async with test_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {_TABLES} RESTART IDENTITY CASCADE"))
    yield


async def _override_get_db():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session
