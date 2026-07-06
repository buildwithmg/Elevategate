from app.models.enums import AdminRole
from tests.factories import create_admin


async def test_login_succeeds_with_correct_credentials(client, db_session):
    admin, password = await create_admin(db_session, email="admin@example.com", password="Correct-Horse-1")

    response = await client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": password}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


async def test_login_rejects_oversized_password_before_hashing(client):
    """
    Regression test: LoginRequest.password previously had no max_length, so an unauthenticated
    caller could submit an arbitrarily large password to inflate the CPU cost of the Argon2id
    verify (or the dummy-hash timing-equalization path) on every request. Pydantic must reject
    this at validation time (422), before any hashing work happens.
    """
    oversized_password = "x" * 10_000

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": oversized_password},
    )

    assert response.status_code == 422


async def test_login_rejects_wrong_password(client, db_session):
    admin, _password = await create_admin(db_session, email="admin@example.com")

    response = await client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": "wrong-password"}
    )
    assert response.status_code == 401


async def test_login_rejects_unknown_email(client):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert response.status_code == 401


async def test_login_rejects_inactive_account(client, db_session):
    admin, password = await create_admin(db_session, email="admin@example.com")
    admin.is_active = False
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": password}
    )
    assert response.status_code == 401


async def test_me_returns_current_admin(client, db_session):
    admin, password = await create_admin(
        db_session, email="admin@example.com", role=AdminRole.REVIEWER
    )

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": password}
    )
    token = login_response.json()["access_token"]

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == admin.email
    assert data["role"] == "reviewer"
    assert "password_hash" not in data


async def test_me_requires_token(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_rejects_invalid_token(client):
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
