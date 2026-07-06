from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.enums import ActorType


async def list_paginated(
    session: AsyncSession,
    *,
    actor_type_filter: ActorType | None,
    action_filter: str | None,
    target_type_filter: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AuditLog], int]:
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    if actor_type_filter is not None:
        query = query.where(AuditLog.actor_type == actor_type_filter)
        count_query = count_query.where(AuditLog.actor_type == actor_type_filter)
    if action_filter is not None:
        query = query.where(AuditLog.action == action_filter)
        count_query = count_query.where(AuditLog.action == action_filter)
    if target_type_filter is not None:
        query = query.where(AuditLog.target_type == target_type_filter)
        count_query = count_query.where(AuditLog.target_type == target_type_filter)

    query = query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)

    total = (await session.execute(count_query)).scalar_one()
    items = list((await session.execute(query)).scalars().all())
    return items, total
