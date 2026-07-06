from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.admin_user import AdminUser
from app.models.enums import ActorType
from app.repositories import audit_log_repository
from app.schemas.audit_log import AuditLogList, AuditLogRead

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogList)
async def list_audit_logs(
    actor_type: ActorType | None = Query(default=None),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> AuditLogList:
    items, total = await audit_log_repository.list_paginated(
        session,
        actor_type_filter=actor_type,
        action_filter=action,
        target_type_filter=target_type,
        limit=limit,
        offset=offset,
    )
    return AuditLogList(items=[AuditLogRead.from_model(item) for item in items], total=total)
