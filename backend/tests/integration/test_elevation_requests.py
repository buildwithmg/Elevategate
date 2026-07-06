import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.core.security import create_access_token
from app.models.approval import Approval
from app.models.audit_log import AuditLog
from app.models.elevation_request import ElevationRequest
from app.models.enums import AdminRole, ElevationRequestStatus
from tests.factories import create_admin, create_device, create_elevation_request


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


def _submit_body(**overrides):
    body = {
        "username": "jdoe",
        "filename": "installer.exe",
        "canonical_path": r"C:\Temp\installer.exe",
        "sha256": "a" * 64,
        "publisher": "Contoso Ltd.",
        "signature_status": "trusted",
        "file_size": 1024,
        "file_version": "1.0.0.0",
        "reason": "Need this installed for a printer driver.",
    }
    body.update(overrides)
    return body


async def test_submit_elevation_request(client, db_session):
    device, secret = await create_device(db_session, hostname="WORKSTATION-JOIN-TEST")

    response = await client.post(
        "/api/v1/elevation-requests",
        json=_submit_body(),
        auth=(str(device.device_uuid), secret),
    )

    assert response.status_code == 201
    data = response.json()
    # Joined from Device - the dashboard needs these without a separate per-row lookup.
    assert data["device_uuid"] == str(device.device_uuid)
    assert data["device_hostname"] == "WORKSTATION-JOIN-TEST"
    assert data["status"] == "pending"
    assert data["device_id"] == device.id
    assert data["sha256"] == "a" * 64


async def test_submit_rejects_invalid_sha256(client, db_session):
    device, secret = await create_device(db_session)

    response = await client.post(
        "/api/v1/elevation-requests",
        json=_submit_body(sha256="not-a-valid-hash"),
        auth=(str(device.device_uuid), secret),
    )
    assert response.status_code == 422


async def test_submit_requires_device_auth(client):
    response = await client.post("/api/v1/elevation-requests", json=_submit_body())
    assert response.status_code == 401


async def test_list_elevation_requests_requires_admin(client):
    response = await client.get("/api/v1/elevation-requests")
    assert response.status_code == 401


async def test_list_elevation_requests(client, db_session):
    device, _ = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    await create_elevation_request(db_session, device=device)
    await create_elevation_request(db_session, device=device, status=ElevationRequestStatus.DENIED)

    response = await client.get("/api/v1/elevation-requests", headers=_auth_header(admin))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2

    response = await client.get(
        "/api/v1/elevation-requests", params={"status": "pending"}, headers=_auth_header(admin)
    )
    assert response.json()["total"] == 1


async def test_get_elevation_request_not_found(client, db_session):
    admin, _ = await create_admin(db_session)
    response = await client.get("/api/v1/elevation-requests/99999", headers=_auth_header(admin))
    assert response.status_code == 404


async def test_reviewer_can_approve(client, db_session):
    device, _ = await create_device(db_session)
    reviewer, _ = await create_admin(db_session, email="reviewer@example.com", role=AdminRole.REVIEWER)
    elevation_request = await create_elevation_request(db_session, device=device)

    response = await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/approve",
        headers=_auth_header(reviewer),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["reviewed_by"] == reviewer.id


async def test_approve_creates_signed_approval(client, db_session):
    device, _ = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    elevation_request = await create_elevation_request(db_session, device=device)

    response = await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/approve",
        headers=_auth_header(admin),
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(Approval).where(Approval.elevation_request_id == elevation_request.id)
    )
    approval = result.scalar_one()
    assert approval.device_uuid == device.device_uuid
    assert approval.sha256 == elevation_request.sha256
    assert approval.signature is not None and len(approval.signature) == 64
    assert approval.consumed_at is None
    assert approval.expires_at > approval.issued_at


async def test_approve_writes_audit_log(client, db_session):
    device, _ = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    elevation_request = await create_elevation_request(db_session, device=device)

    await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/approve", headers=_auth_header(admin)
    )

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "elevation_request.approved")
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].actor_id == str(admin.id)


async def test_approve_already_decided_request_is_rejected(client, db_session):
    device, _ = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    elevation_request = await create_elevation_request(
        db_session, device=device, status=ElevationRequestStatus.DENIED
    )

    response = await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/approve", headers=_auth_header(admin)
    )
    assert response.status_code == 409


async def test_approve_expired_request_is_rejected_and_marked_expired(client, db_session):
    device, _ = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    elevation_request = await create_elevation_request(db_session, device=device, ttl_seconds=-10)

    response = await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/approve", headers=_auth_header(admin)
    )
    assert response.status_code == 409

    await db_session.refresh(elevation_request)
    assert elevation_request.status == ElevationRequestStatus.EXPIRED


async def test_deny_elevation_request(client, db_session):
    device, _ = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    elevation_request = await create_elevation_request(db_session, device=device)

    response = await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/deny",
        json={"reason": "Unrecognized publisher."},
        headers=_auth_header(admin),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "denied"

    result = await db_session.execute(
        select(Approval).where(Approval.elevation_request_id == elevation_request.id)
    )
    assert result.scalar_one_or_none() is None


async def test_deny_without_body(client, db_session):
    device, _ = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    elevation_request = await create_elevation_request(db_session, device=device)

    response = await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/deny", headers=_auth_header(admin)
    )
    assert response.status_code == 200


async def test_concurrent_approvals_only_one_wins(client, db_session):
    """
    The exact race the spec calls out: "Prevent two administrators from approving the same
    request simultaneously." Fire two approve calls concurrently at the same pending request and
    assert exactly one succeeds (200) and the other is rejected (409) - never both succeeding,
    never a duplicated Approval row.
    """
    device, _ = await create_device(db_session)
    admin_a, _ = await create_admin(db_session, email="admin-a@example.com")
    admin_b, _ = await create_admin(db_session, email="admin-b@example.com")
    elevation_request = await create_elevation_request(db_session, device=device)

    responses = await asyncio.gather(
        client.post(
            f"/api/v1/elevation-requests/{elevation_request.id}/approve",
            headers=_auth_header(admin_a),
        ),
        client.post(
            f"/api/v1/elevation-requests/{elevation_request.id}/approve",
            headers=_auth_header(admin_b),
        ),
    )

    status_codes = sorted(r.status_code for r in responses)
    assert status_codes == [200, 409]

    result = await db_session.execute(
        select(Approval).where(Approval.elevation_request_id == elevation_request.id)
    )
    approvals = result.scalars().all()
    assert len(approvals) == 1
