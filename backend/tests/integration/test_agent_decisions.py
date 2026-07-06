from app.core.security import create_access_token
from app.models.enums import ElevationRequestStatus
from tests.factories import create_admin, create_device, create_elevation_request


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def test_decisions_empty_for_new_device(client, db_session):
    device, secret = await create_device(db_session)

    response = await client.get(
        "/api/v1/agent/decisions", auth=(str(device.device_uuid), secret)
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_decisions_requires_device_auth(client):
    response = await client.get("/api/v1/agent/decisions")
    assert response.status_code == 401


async def test_decisions_includes_approved_with_token(client, db_session):
    device, secret = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    elevation_request = await create_elevation_request(db_session, device=device)

    await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/approve", headers=_auth_header(admin)
    )

    response = await client.get("/api/v1/agent/decisions", auth=(str(device.device_uuid), secret))

    assert response.status_code == 200
    decisions = response.json()
    assert len(decisions) == 1
    assert decisions[0]["status"] == "approved"
    assert decisions[0]["request_uuid"] == str(elevation_request.request_uuid)
    approval = decisions[0]["approval"]
    assert approval is not None
    assert approval["sha256"] == elevation_request.sha256
    assert approval["nonce"]
    assert approval["signature"]


async def test_decisions_includes_denied_without_token(client, db_session):
    device, secret = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    elevation_request = await create_elevation_request(db_session, device=device)

    await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/deny", headers=_auth_header(admin)
    )

    response = await client.get("/api/v1/agent/decisions", auth=(str(device.device_uuid), secret))

    decisions = response.json()
    assert len(decisions) == 1
    assert decisions[0]["status"] == "denied"
    assert decisions[0]["approval"] is None


async def test_decisions_excludes_still_pending(client, db_session):
    device, secret = await create_device(db_session)
    await create_elevation_request(db_session, device=device)

    response = await client.get("/api/v1/agent/decisions", auth=(str(device.device_uuid), secret))

    assert response.json() == []


async def test_decisions_are_isolated_per_device(client, db_session):
    device_a, secret_a = await create_device(db_session)
    device_b, secret_b = await create_device(db_session)
    admin, _ = await create_admin(db_session)

    request_a = await create_elevation_request(db_session, device=device_a)
    await client.post(
        f"/api/v1/elevation-requests/{request_a.id}/deny", headers=_auth_header(admin)
    )

    response = await client.get(
        "/api/v1/agent/decisions", auth=(str(device_b.device_uuid), secret_b)
    )

    assert response.json() == []


async def test_decisions_since_filter(client, db_session):
    device, secret = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    elevation_request = await create_elevation_request(db_session, device=device)
    await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/deny", headers=_auth_header(admin)
    )

    from datetime import datetime, timedelta, timezone

    far_future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    response = await client.get(
        "/api/v1/agent/decisions",
        params={"since": far_future},
        auth=(str(device.device_uuid), secret),
    )
    assert response.json() == []


async def test_decisions_lazily_expires_stale_pending_requests(client, db_session):
    device, secret = await create_device(db_session)
    await create_elevation_request(db_session, device=device, ttl_seconds=-10)

    response = await client.get("/api/v1/agent/decisions", auth=(str(device.device_uuid), secret))

    decisions = response.json()
    assert len(decisions) == 1
    assert decisions[0]["status"] == "expired"
    assert decisions[0]["approval"] is None
