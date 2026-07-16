from app.core.security import create_access_token
from tests.factories import (
    create_admin,
    create_app_allowlist_entry,
    create_device,
    create_device_group,
)


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def test_create_device_group(client, db_session):
    admin, _ = await create_admin(db_session)
    response = await client.post(
        "/api/v1/device-groups",
        headers=_auth_header(admin),
        json={"name": "Finance", "description": "Finance team laptops"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Finance"
    assert body["device_count"] == 0


async def test_create_device_group_rejects_duplicate_name(client, db_session):
    admin, _ = await create_admin(db_session)
    await create_device_group(db_session, name="Finance")

    response = await client.post(
        "/api/v1/device-groups", headers=_auth_header(admin), json={"name": "Finance"}
    )
    assert response.status_code == 409


async def test_create_device_group_requires_admin_not_reviewer(client, db_session):
    from app.models.enums import AdminRole

    reviewer, _ = await create_admin(db_session, email="reviewer@example.com", role=AdminRole.REVIEWER)
    response = await client.post(
        "/api/v1/device-groups", headers=_auth_header(reviewer), json={"name": "Finance"}
    )
    assert response.status_code == 403


async def test_list_device_groups_includes_device_count(client, db_session):
    admin, _ = await create_admin(db_session)
    group = await create_device_group(db_session, name="Finance")
    await create_device(db_session, group_id=group.id)
    await create_device(db_session, group_id=group.id)
    await create_device_group(db_session, name="Engineering")

    response = await client.get("/api/v1/device-groups", headers=_auth_header(admin))
    assert response.status_code == 200
    items = {item["name"]: item for item in response.json()["items"]}
    assert items["Finance"]["device_count"] == 2
    assert items["Engineering"]["device_count"] == 0


async def test_delete_device_group_unassigns_devices(client, db_session):
    admin, _ = await create_admin(db_session)
    group = await create_device_group(db_session, name="Finance")
    device, _ = await create_device(db_session, group_id=group.id)

    response = await client.delete(f"/api/v1/device-groups/{group.id}", headers=_auth_header(admin))
    assert response.status_code == 204

    from app.repositories import device_repository

    await db_session.refresh(device)
    reloaded = await device_repository.get_by_id(db_session, device.id)
    assert reloaded.group_id is None


async def test_delete_device_group_cascades_allowlist_entries(client, db_session):
    admin, _ = await create_admin(db_session)
    group = await create_device_group(db_session, name="Finance")
    entry = await create_app_allowlist_entry(db_session, group_id=group.id)

    response = await client.delete(f"/api/v1/device-groups/{group.id}", headers=_auth_header(admin))
    assert response.status_code == 204

    from app.repositories import app_allowlist_repository

    assert await app_allowlist_repository.get_by_id(db_session, entry.id) is None


async def test_delete_unknown_device_group_returns_404(client, db_session):
    admin, _ = await create_admin(db_session)
    response = await client.delete("/api/v1/device-groups/99999", headers=_auth_header(admin))
    assert response.status_code == 404
