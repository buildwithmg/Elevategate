from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token
from tests.factories import create_admin, create_device


def _auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _set_telemetry(db_session, device, **values):
    from sqlalchemy import update

    from app.models.device import Device

    await db_session.execute(update(Device).where(Device.id == device.id).values(**values))
    await db_session.commit()


async def test_low_disk_space_produces_critical_alert(client, db_session):
    admin, _ = await create_admin(db_session)
    device, _ = await create_device(db_session, hostname="LOW-DISK-PC")
    await _set_telemetry(
        db_session, device, disk_total_bytes=100_000_000_000, disk_free_bytes=1_000_000_000
    )

    response = await client.get("/api/v1/dashboard/alerts", headers=_auth_header(admin))
    assert response.status_code == 200
    alerts = response.json()["items"]
    matching = [a for a in alerts if a["type"] == "low_disk_space" and a["hostname"] == "LOW-DISK-PC"]
    assert len(matching) == 1
    assert matching[0]["severity"] == "critical"


async def test_high_ram_usage_produces_warning_alert(client, db_session):
    admin, _ = await create_admin(db_session)
    device, _ = await create_device(db_session, hostname="HIGH-RAM-PC")
    await _set_telemetry(
        db_session, device, ram_total_bytes=16_000_000_000, ram_used_bytes=15_500_000_000
    )

    response = await client.get("/api/v1/dashboard/alerts", headers=_auth_header(admin))
    alerts = response.json()["items"]
    matching = [a for a in alerts if a["type"] == "high_ram_usage" and a["hostname"] == "HIGH-RAM-PC"]
    assert len(matching) == 1
    assert matching[0]["severity"] == "warning"


async def test_offline_device_with_prior_heartbeat_produces_critical_alert(client, db_session):
    admin, _ = await create_admin(db_session)
    device, _ = await create_device(db_session, hostname="OFFLINE-PC")
    stale = datetime.now(timezone.utc) - timedelta(days=2)
    await _set_telemetry(db_session, device, last_seen=stale)

    response = await client.get("/api/v1/dashboard/alerts", headers=_auth_header(admin))
    alerts = response.json()["items"]
    matching = [a for a in alerts if a["type"] == "device_offline" and a["hostname"] == "OFFLINE-PC"]
    assert len(matching) == 1
    assert matching[0]["severity"] == "critical"


async def test_device_never_seen_produces_no_offline_alert(client, db_session):
    admin, _ = await create_admin(db_session)
    await create_device(db_session, hostname="NEVER-SEEN-PC")

    response = await client.get("/api/v1/dashboard/alerts", headers=_auth_header(admin))
    alerts = response.json()["items"]
    assert not [a for a in alerts if a["hostname"] == "NEVER-SEEN-PC"]


async def test_healthy_device_produces_no_alerts(client, db_session):
    admin, _ = await create_admin(db_session)
    device, _ = await create_device(db_session, hostname="HEALTHY-PC")
    await _set_telemetry(
        db_session,
        device,
        disk_total_bytes=500_000_000_000,
        disk_free_bytes=400_000_000_000,
        ram_total_bytes=16_000_000_000,
        ram_used_bytes=4_000_000_000,
        last_seen=datetime.now(timezone.utc),
    )

    response = await client.get("/api/v1/dashboard/alerts", headers=_auth_header(admin))
    alerts = response.json()["items"]
    assert not [a for a in alerts if a["hostname"] == "HEALTHY-PC"]


async def test_reviewer_can_view_alerts(client, db_session):
    from app.models.enums import AdminRole

    reviewer, _ = await create_admin(db_session, email="reviewer@example.com", role=AdminRole.REVIEWER)
    response = await client.get("/api/v1/dashboard/alerts", headers=_auth_header(reviewer))
    assert response.status_code == 200
