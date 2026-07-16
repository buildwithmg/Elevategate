from app.core.security import create_access_token
from app.models.enums import AdminRole
from tests.factories import create_admin, create_app_allowlist_entry, create_device_group


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def test_create_global_allowlist_entry(client, db_session):
    admin, _ = await create_admin(db_session)
    response = await client.post(
        "/api/v1/app-allowlist",
        headers=_auth_header(admin),
        json={"publisher": "Contoso Ltd.", "filename": "ContosoSetup.exe", "description": "Standard tool"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["group_id"] is None
    assert body["group_name"] is None
    assert body["publisher"] == "Contoso Ltd."


async def test_create_group_scoped_allowlist_entry(client, db_session):
    admin, _ = await create_admin(db_session)
    group = await create_device_group(db_session, name="Finance")

    response = await client.post(
        "/api/v1/app-allowlist",
        headers=_auth_header(admin),
        json={"group_id": group.id, "publisher": "Contoso Ltd.", "filename": "installer.exe"},
    )
    assert response.status_code == 201
    assert response.json()["group_name"] == "Finance"


async def test_create_allowlist_entry_rejects_unknown_group(client, db_session):
    admin, _ = await create_admin(db_session)
    response = await client.post(
        "/api/v1/app-allowlist",
        headers=_auth_header(admin),
        json={"group_id": 99999, "publisher": "Contoso Ltd.", "filename": "installer.exe"},
    )
    assert response.status_code == 404


async def test_create_allowlist_entry_requires_admin_not_reviewer(client, db_session):
    reviewer, _ = await create_admin(db_session, email="reviewer@example.com", role=AdminRole.REVIEWER)
    response = await client.post(
        "/api/v1/app-allowlist",
        headers=_auth_header(reviewer),
        json={"publisher": "Contoso Ltd.", "filename": "installer.exe"},
    )
    assert response.status_code == 403


async def test_list_allowlist_entries_filters_by_group(client, db_session):
    admin, _ = await create_admin(db_session)
    group = await create_device_group(db_session, name="Finance")
    await create_app_allowlist_entry(db_session, group_id=group.id, filename="a.exe")
    await create_app_allowlist_entry(db_session, group_id=None, filename="b.exe")

    response = await client.get(
        "/api/v1/app-allowlist", params={"group_id": group.id}, headers=_auth_header(admin)
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["filename"] == "a.exe"


async def test_delete_allowlist_entry(client, db_session):
    admin, _ = await create_admin(db_session)
    entry = await create_app_allowlist_entry(db_session)

    response = await client.delete(f"/api/v1/app-allowlist/{entry.id}", headers=_auth_header(admin))
    assert response.status_code == 204

    from app.repositories import app_allowlist_repository

    assert await app_allowlist_repository.get_by_id(db_session, entry.id) is None


async def test_delete_unknown_allowlist_entry_returns_404(client, db_session):
    admin, _ = await create_admin(db_session)
    response = await client.delete("/api/v1/app-allowlist/99999", headers=_auth_header(admin))
    assert response.status_code == 404
