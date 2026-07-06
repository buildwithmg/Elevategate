import uuid

from app.config import get_settings
from app.core.security import create_access_token
from tests.factories import create_admin, create_device

ENROLLMENT_KEY = get_settings().enrollment_key


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def test_list_audit_logs_requires_admin(client):
    response = await client.get("/api/v1/audit-logs")
    assert response.status_code == 401


async def test_list_audit_logs_after_enroll(client, db_session):
    admin, _ = await create_admin(db_session)

    await client.post(
        "/api/v1/devices/enroll",
        json={
            "device_uuid": str(uuid.uuid4()),
            "hostname": "WORKSTATION-1",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
        },
        headers={"X-Enrollment-Key": ENROLLMENT_KEY},
    )

    response = await client.get("/api/v1/audit-logs", headers=_auth_header(admin))

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    entry = data["items"][0]
    assert entry["action"] == "device.enroll"
    assert entry["actor_type"] == "device"
    assert entry["metadata"]["hostname"] == "WORKSTATION-1"


async def test_list_audit_logs_filters_by_action(client, db_session):
    admin, _ = await create_admin(db_session)
    await create_device(db_session)

    await client.post(
        "/api/v1/devices/enroll",
        json={
            "device_uuid": str(uuid.uuid4()),
            "hostname": "WORKSTATION-2",
            "operating_system": "Windows 11",
            "agent_version": "1.0.0",
        },
        headers={"X-Enrollment-Key": ENROLLMENT_KEY},
    )

    response = await client.get(
        "/api/v1/audit-logs", params={"action": "device.enroll"}, headers=_auth_header(admin)
    )
    assert response.json()["total"] == 1

    response = await client.get(
        "/api/v1/audit-logs", params={"action": "nonexistent.action"}, headers=_auth_header(admin)
    )
    assert response.json()["total"] == 0


async def test_list_audit_logs_pagination(client, db_session):
    admin, _ = await create_admin(db_session)

    for i in range(3):
        await client.post(
            "/api/v1/devices/enroll",
            json={
                "device_uuid": str(uuid.uuid4()),
                "hostname": f"WORKSTATION-{i}",
                "operating_system": "Windows 11",
                "agent_version": "1.0.0",
            },
            headers={"X-Enrollment-Key": ENROLLMENT_KEY},
        )

    response = await client.get(
        "/api/v1/audit-logs", params={"limit": 2, "offset": 0}, headers=_auth_header(admin)
    )
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
