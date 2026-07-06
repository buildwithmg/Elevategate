from app.core.security import create_access_token
from tests.factories import create_admin, create_device, create_elevation_request


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _create_approved_approval(client, db_session):
    device, secret = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    elevation_request = await create_elevation_request(db_session, device=device)

    response = await client.post(
        f"/api/v1/elevation-requests/{elevation_request.id}/approve", headers=_auth_header(admin)
    )
    assert response.status_code == 200

    from sqlalchemy import select

    from app.models.approval import Approval

    result = await db_session.execute(
        select(Approval).where(Approval.elevation_request_id == elevation_request.id)
    )
    approval = result.scalar_one()
    return device, secret, approval


async def test_mark_consumed_succeeds(client, db_session):
    device, secret, approval = await _create_approved_approval(client, db_session)

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/consumed", auth=(str(device.device_uuid), secret)
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == approval.id
    assert data["consumed_at"] is not None


async def test_mark_consumed_twice_is_conflict(client, db_session):
    device, secret, approval = await _create_approved_approval(client, db_session)

    first = await client.post(
        f"/api/v1/approvals/{approval.id}/consumed", auth=(str(device.device_uuid), secret)
    )
    second = await client.post(
        f"/api/v1/approvals/{approval.id}/consumed", auth=(str(device.device_uuid), secret)
    )

    assert first.status_code == 200
    assert second.status_code == 409


async def test_mark_consumed_wrong_device_is_not_found(client, db_session):
    _device, _secret, approval = await _create_approved_approval(client, db_session)
    other_device, other_secret = await create_device(db_session)

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/consumed",
        auth=(str(other_device.device_uuid), other_secret),
    )
    assert response.status_code == 404


async def test_mark_consumed_unknown_approval_is_not_found(client, db_session):
    device, secret = await create_device(db_session)

    response = await client.post(
        "/api/v1/approvals/99999/consumed", auth=(str(device.device_uuid), secret)
    )
    assert response.status_code == 404


async def test_mark_consumed_requires_device_auth(client, db_session):
    _device, _secret, approval = await _create_approved_approval(client, db_session)

    response = await client.post(f"/api/v1/approvals/{approval.id}/consumed")
    assert response.status_code == 401
