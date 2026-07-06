from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token
from app.models.enums import EnrollmentStatus
from tests.factories import create_admin, create_device


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def test_list_devices_requires_admin(client):
    response = await client.get("/api/v1/devices")
    assert response.status_code == 401


async def test_list_devices(client, db_session):
    admin, _ = await create_admin(db_session)
    await create_device(db_session, hostname="PC-ONE")
    await create_device(db_session, hostname="PC-TWO")

    response = await client.get("/api/v1/devices", headers=_auth_header(admin))

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    hostnames = {item["hostname"] for item in data["items"]}
    assert hostnames == {"PC-ONE", "PC-TWO"}


async def test_list_devices_filters_by_enrollment_status(client, db_session):
    admin, _ = await create_admin(db_session)
    await create_device(db_session, hostname="ACTIVE-PC", enrollment_status=EnrollmentStatus.ACTIVE)
    await create_device(db_session, hostname="REVOKED-PC", enrollment_status=EnrollmentStatus.REVOKED)

    response = await client.get(
        "/api/v1/devices", params={"enrollment_status": "revoked"}, headers=_auth_header(admin)
    )

    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["hostname"] == "REVOKED-PC"


async def test_device_online_true_for_recent_heartbeat(client, db_session):
    admin, _ = await create_admin(db_session)
    device, secret = await create_device(db_session, hostname="FRESH-PC")

    await client.post(
        "/api/v1/devices/heartbeat", json={}, auth=(str(device.device_uuid), secret)
    )

    response = await client.get("/api/v1/devices", headers=_auth_header(admin))
    item = next(i for i in response.json()["items"] if i["hostname"] == "FRESH-PC")
    assert item["online"] is True


async def test_device_online_false_for_stale_last_seen(client, db_session):
    admin, _ = await create_admin(db_session)
    device, _secret = await create_device(db_session, hostname="STALE-PC")

    from sqlalchemy import update

    from app.models.device import Device

    stale_time = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.execute(update(Device).where(Device.id == device.id).values(last_seen=stale_time))
    await db_session.commit()

    response = await client.get("/api/v1/devices", headers=_auth_header(admin))
    item = next(i for i in response.json()["items"] if i["hostname"] == "STALE-PC")
    assert item["online"] is False


async def test_device_online_false_with_no_heartbeat_ever(client, db_session):
    admin, _ = await create_admin(db_session)
    await create_device(db_session, hostname="NEVER-SEEN-PC")

    response = await client.get("/api/v1/devices", headers=_auth_header(admin))
    item = next(i for i in response.json()["items"] if i["hostname"] == "NEVER-SEEN-PC")
    assert item["online"] is False


async def test_device_online_false_when_revoked_even_with_recent_heartbeat(client, db_session):
    admin, _ = await create_admin(db_session)
    device, secret = await create_device(db_session, hostname="REVOKED-BUT-FRESH")

    await client.post(
        "/api/v1/devices/heartbeat", json={}, auth=(str(device.device_uuid), secret)
    )

    from sqlalchemy import update

    from app.models.device import Device

    await db_session.execute(
        update(Device).where(Device.id == device.id).values(enrollment_status=EnrollmentStatus.REVOKED)
    )
    await db_session.commit()

    response = await client.get("/api/v1/devices", headers=_auth_header(admin))
    item = next(i for i in response.json()["items"] if i["hostname"] == "REVOKED-BUT-FRESH")
    assert item["online"] is False
