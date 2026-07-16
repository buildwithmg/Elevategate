from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_device, get_db, require_role
from app.config import get_settings
from app.core.approvals import issue_approval
from app.core.audit import write_audit_log
from app.core.rate_limit import limiter
from app.models.admin_user import AdminUser
from app.models.device import Device
from app.models.enums import ActorType, ElevationRequestStatus
from app.repositories import device_repository, elevation_request_repository
from app.schemas.elevation_request import (
    DenyRequest,
    ElevationRequestCreate,
    ElevationRequestList,
    ElevationRequestRead,
)

router = APIRouter(prefix="/elevation-requests", tags=["elevation-requests"])


@router.post("", response_model=ElevationRequestRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().rate_limit_elevation_request_submit)
async def submit_elevation_request(
    request: Request,
    body: ElevationRequestCreate,
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_db),
) -> ElevationRequestRead:
    settings = get_settings()
    now = datetime.now(timezone.utc)

    elevation_request = await elevation_request_repository.create(
        session,
        device_id=device.id,
        username=body.username,
        filename=body.filename,
        canonical_path=body.canonical_path,
        sha256=body.sha256,
        publisher=body.publisher,
        signature_status=body.signature_status,
        file_size=body.file_size,
        file_version=body.file_version,
        reason=body.reason,
        expires_at=now + timedelta(seconds=settings.elevation_request_ttl_seconds),
    )

    await write_audit_log(
        session,
        actor_type=ActorType.DEVICE,
        actor_id=str(device.device_uuid),
        action="elevation_request.submitted",
        target_type="elevation_request",
        target_id=str(elevation_request.id),
        metadata={"filename": elevation_request.filename, "sha256": elevation_request.sha256},
    )

    await session.commit()
    await session.refresh(elevation_request)
    return ElevationRequestRead.model_validate(elevation_request)


@router.get("", response_model=ElevationRequestList)
async def list_elevation_requests(
    status_filter: ElevationRequestStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> ElevationRequestList:
    items, total = await elevation_request_repository.list_paginated(
        session, status_filter=status_filter, device_id=None, limit=limit, offset=offset
    )
    return ElevationRequestList(
        items=[ElevationRequestRead.model_validate(item) for item in items], total=total
    )


@router.get("/{elevation_request_id}", response_model=ElevationRequestRead)
async def get_elevation_request(
    elevation_request_id: int,
    _admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> ElevationRequestRead:
    elevation_request = await elevation_request_repository.get_by_id(session, elevation_request_id)
    if elevation_request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Elevation request not found.")
    return ElevationRequestRead.model_validate(elevation_request)


async def _reject_if_expired(session: AsyncSession, elevation_request) -> None:
    """If a still-'pending' request's review window has passed, flip it to EXPIRED and raise 409.
    Called at the top of both approve and deny so neither action can be taken on a stale request."""
    now = datetime.now(timezone.utc)
    if elevation_request.expires_at <= now:
        await elevation_request_repository.transition_status(
            session,
            elevation_request_id=elevation_request.id,
            expected_current_status=ElevationRequestStatus.PENDING,
            new_status=ElevationRequestStatus.EXPIRED,
            reviewed_by=None,
            reviewed_at=now,
        )
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Elevation request has expired.")


@router.post("/{elevation_request_id}/approve", response_model=ElevationRequestRead)
async def approve_elevation_request(
    elevation_request_id: int,
    admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> ElevationRequestRead:
    elevation_request = await elevation_request_repository.get_by_id(session, elevation_request_id)
    if elevation_request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Elevation request not found.")

    if elevation_request.status != ElevationRequestStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Elevation request is no longer pending.")

    await _reject_if_expired(session, elevation_request)

    now = datetime.now(timezone.utc)
    updated = await elevation_request_repository.transition_status(
        session,
        elevation_request_id=elevation_request.id,
        expected_current_status=ElevationRequestStatus.PENDING,
        new_status=ElevationRequestStatus.APPROVED,
        reviewed_by=admin.id,
        reviewed_at=now,
    )
    if updated is None:
        # Lost a race with a concurrent approve/deny on the same request - see
        # elevation_request_repository.transition_status for why this is safe to treat as final.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Elevation request was already decided by another reviewer.",
        )

    device = await device_repository.get_by_id(session, updated.device_id)
    approval = await issue_approval(session, elevation_request=updated, device=device)

    await write_audit_log(
        session,
        actor_type=ActorType.ADMIN,
        actor_id=str(admin.id),
        action="elevation_request.approved",
        target_type="elevation_request",
        target_id=str(updated.id),
        metadata={"nonce": approval.nonce},
    )

    await session.commit()
    await session.refresh(updated)
    return ElevationRequestRead.model_validate(updated)


@router.post("/{elevation_request_id}/deny", response_model=ElevationRequestRead)
async def deny_elevation_request(
    elevation_request_id: int,
    body: DenyRequest | None = None,
    admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> ElevationRequestRead:
    elevation_request = await elevation_request_repository.get_by_id(session, elevation_request_id)
    if elevation_request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Elevation request not found.")

    if elevation_request.status != ElevationRequestStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Elevation request is no longer pending.")

    await _reject_if_expired(session, elevation_request)

    now = datetime.now(timezone.utc)
    updated = await elevation_request_repository.transition_status(
        session,
        elevation_request_id=elevation_request.id,
        expected_current_status=ElevationRequestStatus.PENDING,
        new_status=ElevationRequestStatus.DENIED,
        reviewed_by=admin.id,
        reviewed_at=now,
    )
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Elevation request was already decided by another reviewer.",
        )

    await write_audit_log(
        session,
        actor_type=ActorType.ADMIN,
        actor_id=str(admin.id),
        action="elevation_request.denied",
        target_type="elevation_request",
        target_id=str(updated.id),
        metadata={"reason": body.reason if body else None},
    )

    await session.commit()
    await session.refresh(updated)
    return ElevationRequestRead.model_validate(updated)
