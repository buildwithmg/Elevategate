from app.core.security import create_access_token
from app.models.enums import AdminRole
from tests.factories import create_admin, create_device, create_device_group


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def test_assign_device_to_group(client, db_session):
    admin, _ = await create_admin(db_session)
    device, _ = await create_device(db_session)
    group = await create_device_group(db_session, name="Finance")

    response = await client.patch(
        f"/api/v1/devices/{device.id}/group", headers=_auth_header(admin), json={"group_id": group.id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["group_id"] == group.id
    assert body["group_name"] == "Finance"


async def test_unassign_device_group(client, db_session):
    admin, _ = await create_admin(db_session)
    group = await create_device_group(db_session, name="Finance")
    device, _ = await create_device(db_session, group_id=group.id)

    response = await client.patch(
        f"/api/v1/devices/{device.id}/group", headers=_auth_header(admin), json={"group_id": None}
    )
    assert response.status_code == 200
    assert response.json()["group_id"] is None


async def test_assign_device_to_unknown_group_returns_404(client, db_session):
    admin, _ = await create_admin(db_session)
    device, _ = await create_device(db_session)

    response = await client.patch(
        f"/api/v1/devices/{device.id}/group", headers=_auth_header(admin), json={"group_id": 99999}
    )
    assert response.status_code == 404


async def test_assign_group_requires_admin_not_reviewer(client, db_session):
    reviewer, _ = await create_admin(db_session, email="reviewer@example.com", role=AdminRole.REVIEWER)
    device, _ = await create_device(db_session)
    group = await create_device_group(db_session, name="Finance")

    response = await client.patch(
        f"/api/v1/devices/{device.id}/group", headers=_auth_header(reviewer), json={"group_id": group.id}
    )
    assert response.status_code == 403


async def test_request_update_sets_flag(client, db_session):
    admin, _ = await create_admin(db_session)
    device, _ = await create_device(db_session, agent_version="1.0.2")

    response = await client.post(
        f"/api/v1/devices/{device.id}/request-update", headers=_auth_header(admin)
    )
    assert response.status_code == 200
    assert response.json()["update_requested"] is True


async def test_request_update_unknown_device_returns_404(client, db_session):
    admin, _ = await create_admin(db_session)
    response = await client.post("/api/v1/devices/99999/request-update", headers=_auth_header(admin))
    assert response.status_code == 404


async def test_list_devices_filters_by_group(client, db_session):
    admin, _ = await create_admin(db_session)
    group = await create_device_group(db_session, name="Finance")
    in_group, _ = await create_device(db_session, group_id=group.id, hostname="IN-GROUP")
    await create_device(db_session, hostname="NOT-IN-GROUP")

    response = await client.get(
        "/api/v1/devices", params={"group_id": group.id}, headers=_auth_header(admin)
    )
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["hostname"] == "IN-GROUP"
