from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_device, get_db
from app.config import get_settings
from app.core.rate_limit import limiter
from app.models.device import Device
from app.repositories import approval_repository, elevation_request_repository
from app.schemas.agent import DecisionRead
from app.schemas.approval import ApprovalRead

router = APIRouter(prefix="/agent", tags=["agent"])

_EPOCH = datetime.fromtimestamp(0, tz=timezone.utc)


@router.get("/decisions", response_model=list[DecisionRead])
@limiter.limit(lambda: get_settings().rate_limit_agent_decisions)
async def get_decisions(
    request: Request,
    since: datetime | None = Query(default=None),
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_db),
) -> list[DecisionRead]:
    """
    Polled periodically by the agent. Device identity comes exclusively from the authenticated
    caller (HTTP Basic device credentials) - there is no device-id path/query parameter to spoof,
    so a device can never enumerate another device's decisions.
    """
    now = datetime.now(timezone.utc)

    await elevation_request_repository.expire_stale_pending_requests_for_device(
        session, device_id=device.id, now=now
    )
    await session.commit()

    rows = await approval_repository.list_decisions_for_device_since(
        session, device_id=device.id, since=since or _EPOCH
    )

    return [
        DecisionRead(
            request_uuid=elevation_request.request_uuid,
            status=elevation_request.status,
            approval=ApprovalRead.model_validate(approval) if approval else None,
        )
        for elevation_request, approval in rows
    ]
