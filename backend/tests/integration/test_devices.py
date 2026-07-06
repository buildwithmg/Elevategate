import uuid

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models.audit_log import AuditLog
from app.models.enums import EnrollmentStatus
from tests.factories import create_device

ENROLLMENT_KEY = get_settings().enrollment_key


def _enroll_body(**overrides):
    body = {
        "device_uuid": str(uuid.uuid4()),
        "hostname": "WORKSTATION-042",
        "operating_system": "Windows 11 23H2",
        "agent_version": "1.0.0",
    }
    body.update(overrides)
    return body


async def test_enroll_succeeds_with_valid_key(client):
    response = await client.post(
        "/api/v1/devices/enroll",
        json=_enroll_body(),
        headers={"X-Enrollment-Key": ENROLLMENT_KEY},
    )

    assert response.status_code == 201
    data = response.json()
    assert "device_secret" in data and len(data["device_secret"]) >= 32
    assert data["enrollment_status"] == "active"


async def test_enroll_rejects_missing_key(client):
    response = await client.post("/api/v1/devices/enroll", json=_enroll_body())
    assert response.status_code in (401, 422)


async def test_enroll_rejects_wrong_key(client):
    response = await client.post(
        "/api/v1/devices/enroll",
        json=_enroll_body(),
        headers={"X-Enrollment-Key": "wrong-key"},
    )
    assert response.status_code == 401


async def test_enroll_rejects_duplicate_device_uuid(client):
    body = _enroll_body()
    headers = {"X-Enrollment-Key": ENROLLMENT_KEY}

    first = await client.post("/api/v1/devices/enroll", json=body, headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/v1/devices/enroll", json=body, headers=headers)
    assert second.status_code == 409


async def test_enroll_rejects_missing_fields(client):
    response = await client.post(
        "/api/v1/devices/enroll",
        json={"device_uuid": str(uuid.uuid4())},
        headers={"X-Enrollment-Key": ENROLLMENT_KEY},
    )
    assert response.status_code == 422


async def test_enroll_writes_audit_log(client, db_session):
    await client.post(
        "/api/v1/devices/enroll",
        json=_enroll_body(),
        headers={"X-Enrollment-Key": ENROLLMENT_KEY},
    )

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "device.enroll"))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].actor_type.value == "device"


async def test_heartbeat_succeeds_with_valid_credentials(client, db_session):
    device, secret = await create_device(db_session)

    response = await client.post(
        "/api/v1/devices/heartbeat",
        json={"agent_version": "1.1.0"},
        auth=(str(device.device_uuid), secret),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["device_uuid"] == str(device.device_uuid)
    assert data["last_seen"] is not None


async def test_heartbeat_rejects_wrong_secret(client, db_session):
    device, _secret = await create_device(db_session)

    response = await client.post(
        "/api/v1/devices/heartbeat",
        json={},
        auth=(str(device.device_uuid), "wrong-secret"),
    )
    assert response.status_code == 401


async def test_heartbeat_rejects_unknown_device(client):
    response = await client.post(
        "/api/v1/devices/heartbeat",
        json={},
        auth=(str(uuid.uuid4()), "some-secret"),
    )
    assert response.status_code == 401


async def test_heartbeat_rejects_revoked_device(client, db_session):
    device, secret = await create_device(db_session, enrollment_status=EnrollmentStatus.REVOKED)

    response = await client.post(
        "/api/v1/devices/heartbeat",
        json={},
        auth=(str(device.device_uuid), secret),
    )
    assert response.status_code == 403


async def test_heartbeat_missing_credentials(client):
    response = await client.post("/api/v1/devices/heartbeat", json={})
    assert response.status_code == 401
