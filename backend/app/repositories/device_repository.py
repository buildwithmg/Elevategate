import uuid
from datetime import datetime

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.enums import EnrollmentStatus


async def get_by_uuid(session: AsyncSession, device_uuid: uuid.UUID) -> Device | None:
    result = await session.execute(select(Device).where(Device.device_uuid == device_uuid))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, device_id: int) -> Device | None:
    result = await session.execute(select(Device).where(Device.id == device_id))
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    device_uuid: uuid.UUID,
    hostname: str,
    operating_system: str,
    agent_version: str | None,
    device_secret_hash: str,
) -> Device:
    device = Device(
        device_uuid=device_uuid,
        hostname=hostname,
        operating_system=operating_system,
        agent_version=agent_version,
        device_secret_hash=device_secret_hash,
        enrollment_status=EnrollmentStatus.ACTIVE,
    )
    session.add(device)
    await session.flush()
    return device


async def record_heartbeat(
    session: AsyncSession,
    *,
    device_id: int,
    seen_at: datetime,
    agent_version: str | None,
    disk_total_bytes: int | None = None,
    disk_free_bytes: int | None = None,
    ram_total_bytes: int | None = None,
    ram_used_bytes: int | None = None,
    telemetry_at: datetime | None = None,
) -> Device:
    values: dict[str, object] = {"last_seen": seen_at}
    if agent_version is not None:
        values["agent_version"] = agent_version
    if telemetry_at is not None:
        values["last_telemetry_at"] = telemetry_at
        values["disk_total_bytes"] = disk_total_bytes
        values["disk_free_bytes"] = disk_free_bytes
        values["ram_total_bytes"] = ram_total_bytes
        values["ram_used_bytes"] = ram_used_bytes

    result = await session.execute(
        update(Device).where(Device.id == device_id).values(**values).returning(Device)
    )
    return result.scalar_one()


async def request_update(session: AsyncSession, *, device_id: int, requested_at: datetime) -> Device | None:
    """Admin-initiated "update now" - the device's next heartbeat response carries this back as
    `updateRequested: true` (see app.api.v1.agent_compat.agent_heartbeat). Snapshots the device's
    current agent_version so a later heartbeat can tell the update actually landed (version
    changed) apart from "still checking in on the old build"."""
    device = await get_by_id(session, device_id)
    if device is None:
        return None

    result = await session.execute(
        update(Device)
        .where(Device.id == device_id)
        .values(update_requested_at=requested_at, update_requested_from_version=device.agent_version)
        .returning(Device)
    )
    return result.scalar_one_or_none()


async def clear_update_requested(session: AsyncSession, *, device_id: int) -> None:
    await session.execute(
        update(Device)
        .where(Device.id == device_id)
        .values(update_requested_at=None, update_requested_from_version=None)
    )


async def assign_group(session: AsyncSession, *, device_id: int, group_id: int | None) -> Device | None:
    result = await session.execute(
        update(Device).where(Device.id == device_id).values(group_id=group_id).returning(Device)
    )
    return result.scalar_one_or_none()


async def list_paginated(
    session: AsyncSession,
    *,
    enrollment_status_filter: EnrollmentStatus | None,
    group_id_filter: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Device], int]:
    query = select(Device)
    count_query = select(func.count()).select_from(Device)

    if enrollment_status_filter is not None:
        query = query.where(Device.enrollment_status == enrollment_status_filter)
        count_query = count_query.where(Device.enrollment_status == enrollment_status_filter)
    if group_id_filter is not None:
        query = query.where(Device.group_id == group_id_filter)
        count_query = count_query.where(Device.group_id == group_id_filter)

    query = query.order_by(Device.created_at.desc()).limit(limit).offset(offset)

    total = (await session.execute(count_query)).scalar_one()
    items = list((await session.execute(query)).scalars().all())
    return items, total


async def count_online_offline(session: AsyncSession, *, online_cutoff: datetime) -> tuple[int, int]:
    """
    Returns (active_count, offline_count) among currently-*enrolled* (ACTIVE) devices only -
    revoked devices are excluded from both buckets, matching the dashboard's operational meaning
    of "active"/"offline" rather than enrollment lifecycle state.
    """
    online_case = case((Device.last_seen >= online_cutoff, 1), else_=0)
    result = await session.execute(
        select(func.coalesce(func.sum(online_case), 0), func.count())
        .select_from(Device)
        .where(Device.enrollment_status == EnrollmentStatus.ACTIVE)
    )
    active_count, total_enrolled = result.one()
    return int(active_count), int(total_enrolled) - int(active_count)


async def list_active(session: AsyncSession) -> list[Device]:
    """Every currently-enrolled (ACTIVE) device, unpaginated - used for alert scanning
    (low disk/high RAM/offline), where every device needs to be checked, not just one page."""
    result = await session.execute(select(Device).where(Device.enrollment_status == EnrollmentStatus.ACTIVE))
    return list(result.scalars().all())
