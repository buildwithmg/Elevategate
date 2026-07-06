from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.core.rate_limit import limiter
from app.database import get_db
from tests.conftest import _override_get_db


async def test_login_endpoint_enforces_its_configured_rate_limit(monkeypatch):
    """
    Exercises the real login route's real slowapi decorator with a deliberately tight limit
    (rather than the generous blanket override conftest.py sets for the rest of the suite), and
    confirms the Nth request over the limit actually gets HTTP 429 - not just that a Limiter
    object exists somewhere.

    `limiter` is a process-wide singleton whose in-memory counters persist across every other
    test in the suite (all of which share the same synthetic client IP under httpx's
    ASGITransport) - it must be reset here, or this test would trip on request volume left over
    from unrelated tests rather than the tight limit it's actually trying to prove.
    """
    limiter.reset()
    monkeypatch.setenv("RATE_LIMIT_LOGIN", "2/minute")
    get_settings.cache_clear()
    try:
        from app.main import create_app

        app = create_app()
        app.dependency_overrides[get_db] = _override_get_db
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            body = {"email": "nobody@example.com", "password": "irrelevant"}
            responses = [await ac.post("/api/v1/auth/login", json=body) for _ in range(3)]

        statuses = [r.status_code for r in responses]
        # First two consume the limit (both 401 - unknown email - which is fine, we're testing
        # the *rate limiter*, not login success); the third must be rate-limited.
        assert statuses[:2] == [401, 401]
        assert statuses[2] == 429
    finally:
        get_settings.cache_clear()
        limiter.reset()
