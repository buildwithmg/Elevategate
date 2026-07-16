import os

from app.core.security import create_access_token
from app.models.enums import AdminRole
from tests.factories import create_admin


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def test_admin_can_view_enrollment_info(client, db_session):
    admin, _ = await create_admin(db_session)
    response = await client.get("/api/v1/dashboard/enrollment-info", headers=_auth_header(admin))
    assert response.status_code == 200
    body = response.json()
    assert body["enrollment_key"] == os.environ["ENROLLMENT_KEY"]
    assert "irm " in body["install_command"] and "install.ps1" in body["install_command"]


async def test_reviewer_cannot_view_enrollment_info(client, db_session):
    reviewer, _ = await create_admin(db_session, email="reviewer@example.com", role=AdminRole.REVIEWER)
    response = await client.get("/api/v1/dashboard/enrollment-info", headers=_auth_header(reviewer))
    assert response.status_code == 403


async def test_enrollment_info_requires_auth(client):
    response = await client.get("/api/v1/dashboard/enrollment-info")
    assert response.status_code == 401
