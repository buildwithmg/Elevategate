from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_device, get_db
from app.config import get_settings
from app.core.audit import write_audit_log
from app.core.rate_limit import limiter
from app.models.device import Device
from app.models.enums import ActorType
from app.repositories import approval_repository
from app.schemas.approval import ConsumedResponse

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/{approval_id}/consumed", response_model=ConsumedResponse)
@limiter.limit(lambda: get_settings().rate_limit_approval_consumed)
async def mark_approval_consumed(
    request: Request,
    approval_id: int,
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_db),
) -> ConsumedResponse:
    """
    The agent calls this once it has verified the approval's signature locally and executed the
    file. Idempotent: a second call for an already-consumed approval is rejected (409), giving the
    backend its own record-level replay guard independent of the agent's local nonce store.
    """
    approval = await approval_repository.get_by_id(session, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approval not found.")

    if approval.device_uuid != device.device_uuid:
        # Deliberately 404, not 403: existence of another device's approval id is not
        # information this caller is entitled to learn from the response.
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approval not found.")

    updated = await approval_repository.mark_consumed(
        session, approval_id=approval_id, consumed_at=datetime.now(timezone.utc)
    )
    if updated is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Approval was already consumed.")

    await write_audit_log(
        session,
        actor_type=ActorType.DEVICE,
        actor_id=str(device.device_uuid),
        action="approval.consumed",
        target_type="approval",
        target_id=str(approval.id),
        metadata=None,
    )

    await session.commit()
    await session.refresh(updated)
    return ConsumedResponse.model_validate(updated)
