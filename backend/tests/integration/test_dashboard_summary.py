from app.core.security import create_access_token
from app.models.enums import EnrollmentStatus
from tests.factories import create_admin, create_device, create_elevation_request


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def test_summary_requires_admin(client):
    response = await client.get("/api/v1/dashboard/summary")
    assert response.status_code == 401


async def test_summary_counts(client, db_session):
    admin, _ = await create_admin(db_session)
    device, secret = await create_device(db_session)
    await create_device(db_session, enrollment_status=EnrollmentStatus.REVOKED)

    # One pending, one approved, one denied.
    pending_request = await create_elevation_request(db_session, device=device, sha256="a" * 64)
    approved_request = await create_elevation_request(db_session, device=device, sha256="b" * 64)
    denied_request = await create_elevation_request(db_session, device=device, sha256="c" * 64)

    await client.post(
        f"/api/v1/elevation-requests/{approved_request.id}/approve", headers=_auth_header(admin)
    )
    await client.post(
        f"/api/v1/elevation-requests/{denied_request.id}/deny", headers=_auth_header(admin)
    )

    # Device heartbeat makes it "active"; the revoked device is excluded from both buckets.
    await client.post("/api/v1/devices/heartbeat", json={}, auth=(str(device.device_uuid), secret))

    response = await client.get("/api/v1/dashboard/summary", headers=_auth_header(admin))

    assert response.status_code == 200
    data = response.json()
    assert data["pending_requests"] == 1
    assert data["approved_today"] == 1
    assert data["denied_today"] == 1
    assert data["active_devices"] == 1
    assert data["offline_devices"] == 0
