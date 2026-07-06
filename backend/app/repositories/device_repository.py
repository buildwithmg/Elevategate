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
    session: AsyncSession, *, device_id: int, seen_at: datetime, agent_version: str | None
) -> Device:
    values: dict[str, object] = {"last_seen": seen_at}
    if agent_version is not None:
        values["agent_version"] = agent_version

    result = await session.execute(
        update(Device).where(Device.id == device_id).values(**values).returning(Device)
    )
    return result.scalar_one()


async def list_paginated(
    session: AsyncSession,
    *,
    enrollment_status_filter: EnrollmentStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Device], int]:
    query = select(Device)
    count_query = select(func.count()).select_from(Device)

    if enrollment_status_filter is not None:
        query = query.where(Device.enrollment_status == enrollment_status_filter)
        count_query = count_query.where(Device.enrollment_status == enrollment_status_filter)

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
