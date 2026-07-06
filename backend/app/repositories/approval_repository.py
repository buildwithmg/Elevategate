from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval
from app.models.elevation_request import ElevationRequest
from app.models.enums import ApprovalAction, ElevationRequestStatus


async def create(
    session: AsyncSession,
    *,
    elevation_request_id: int,
    device_uuid: UUID,
    sha256: str,
    nonce: str,
    issued_at: datetime,
    expires_at: datetime,
    signature: bytes,
) -> Approval:
    approval = Approval(
        elevation_request_id=elevation_request_id,
        action=ApprovalAction.EXECUTE,
        device_uuid=device_uuid,
        sha256=sha256,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
        signature=signature,
    )
    session.add(approval)
    await session.flush()
    return approval


async def get_by_id(session: AsyncSession, approval_id: int) -> Approval | None:
    result = await session.execute(select(Approval).where(Approval.id == approval_id))
    return result.scalar_one_or_none()


async def get_by_elevation_request_id(
    session: AsyncSession, elevation_request_id: int
) -> Approval | None:
    result = await session.execute(
        select(Approval).where(Approval.elevation_request_id == elevation_request_id)
    )
    return result.scalar_one_or_none()


async def mark_consumed(
    session: AsyncSession, *, approval_id: int, consumed_at: datetime
) -> Approval | None:
    """
    Atomically sets consumed_at only if it is currently NULL. Returns None if the approval was
    already consumed (or doesn't exist) - the backend's own idempotency guard on the consumed
    callback, independent of (and in addition to) the agent's local nonce store.
    """
    result = await session.execute(
        update(Approval)
        .where(Approval.id == approval_id, Approval.consumed_at.is_(None))
        .values(consumed_at=consumed_at)
        .returning(Approval)
    )
    return result.scalar_one_or_none()


async def list_decisions_for_device_since(
    session: AsyncSession, *, device_id: int, since: datetime
) -> list[tuple[ElevationRequest, Approval | None]]:
    """Every non-pending request for this device decided at/after `since`, with its Approval (if any) attached."""
    query = (
        select(ElevationRequest, Approval)
        .outerjoin(Approval, Approval.elevation_request_id == ElevationRequest.id)
        .where(
            ElevationRequest.device_id == device_id,
            ElevationRequest.status != ElevationRequestStatus.PENDING,
            ElevationRequest.reviewed_at.is_not(None),
            ElevationRequest.reviewed_at >= since,
        )
        .order_by(ElevationRequest.reviewed_at.asc())
    )
    result = await session.execute(query)
    return [(row[0], row[1]) for row in result.all()]
