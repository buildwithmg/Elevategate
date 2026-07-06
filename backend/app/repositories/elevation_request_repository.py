import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elevation_request import ElevationRequest
from app.models.enums import ElevationRequestStatus, SignatureStatus


async def create(
    session: AsyncSession,
    *,
    device_id: int,
    username: str,
    filename: str,
    canonical_path: str,
    sha256: str,
    publisher: str | None,
    signature_status: SignatureStatus,
    file_size: int,
    file_version: str | None,
    reason: str,
    expires_at: datetime,
) -> ElevationRequest:
    elevation_request = ElevationRequest(
        request_uuid=uuid.uuid4(),
        device_id=device_id,
        username=username,
        filename=filename,
        canonical_path=canonical_path,
        sha256=sha256,
        publisher=publisher,
        signature_status=signature_status,
        file_size=file_size,
        file_version=file_version,
        reason=reason,
        status=ElevationRequestStatus.PENDING,
        expires_at=expires_at,
    )
    session.add(elevation_request)
    await session.flush()
    return elevation_request


async def get_by_id(session: AsyncSession, elevation_request_id: int) -> ElevationRequest | None:
    result = await session.execute(
        select(ElevationRequest).where(ElevationRequest.id == elevation_request_id)
    )
    return result.scalar_one_or_none()


async def get_by_uuid(session: AsyncSession, request_uuid: uuid.UUID) -> ElevationRequest | None:
    result = await session.execute(
        select(ElevationRequest).where(ElevationRequest.request_uuid == request_uuid)
    )
    return result.scalar_one_or_none()


async def list_paginated(
    session: AsyncSession,
    *,
    status_filter: ElevationRequestStatus | None,
    device_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[ElevationRequest], int]:
    query = select(ElevationRequest)
    count_query = select(func.count()).select_from(ElevationRequest)

    if status_filter is not None:
        query = query.where(ElevationRequest.status == status_filter)
        count_query = count_query.where(ElevationRequest.status == status_filter)
    if device_id is not None:
        query = query.where(ElevationRequest.device_id == device_id)
        count_query = count_query.where(ElevationRequest.device_id == device_id)

    query = query.order_by(ElevationRequest.requested_at.desc()).limit(limit).offset(offset)

    total = (await session.execute(count_query)).scalar_one()
    items = list((await session.execute(query)).scalars().all())
    return items, total


async def count_pending(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(ElevationRequest)
        .where(ElevationRequest.status == ElevationRequestStatus.PENDING)
    )
    return result.scalar_one()


async def count_reviewed_since(
    session: AsyncSession, *, status_filter: ElevationRequestStatus, since: datetime
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(ElevationRequest)
        .where(
            ElevationRequest.status == status_filter,
            ElevationRequest.reviewed_at >= since,
        )
    )
    return result.scalar_one()


async def expire_stale_pending_requests_for_device(
    session: AsyncSession, *, device_id: int, now: datetime
) -> None:
    """
    Bulk-transitions any of this device's PENDING requests whose review window has already
    passed to EXPIRED, with no reviewer attached. Called at the top of the agent's decisions
    poll so a request that nobody ever acted on still eventually surfaces as "expired" to the
    agent, not just requests an admin happened to click on after the fact.
    """
    await session.execute(
        update(ElevationRequest)
        .where(
            ElevationRequest.device_id == device_id,
            ElevationRequest.status == ElevationRequestStatus.PENDING,
            ElevationRequest.expires_at <= now,
        )
        .values(status=ElevationRequestStatus.EXPIRED, reviewed_at=now)
    )


async def transition_status(
    session: AsyncSession,
    *,
    elevation_request_id: int,
    expected_current_status: ElevationRequestStatus,
    new_status: ElevationRequestStatus,
    reviewed_by: int | None,
    reviewed_at: datetime,
) -> ElevationRequest | None:
    """
    Atomically moves the request from `expected_current_status` to `new_status` in a single
    UPDATE...WHERE...RETURNING statement. Returns None if the row was not in
    `expected_current_status` (e.g. a concurrent admin already decided it, or it already expired)
    - callers must treat None as "no longer actionable," never retry-and-overwrite. This is what
    prevents two administrators from approving the same request simultaneously: Postgres
    serializes concurrent UPDATEs to the same row, and the loser's WHERE clause re-evaluates
    against the winner's already-committed new status and matches zero rows.
    """
    result = await session.execute(
        update(ElevationRequest)
        .where(
            ElevationRequest.id == elevation_request_id,
            ElevationRequest.status == expected_current_status,
        )
        .values(status=new_status, reviewed_by=reviewed_by, reviewed_at=reviewed_at)
        .returning(ElevationRequest)
    )
    return result.scalar_one_or_none()
