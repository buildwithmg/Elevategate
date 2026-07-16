from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_device, get_db, require_enrollment_key, require_role
from app.config import get_settings
from app.core.audit import write_audit_log
from app.core.rate_limit import limiter
from app.core.security import generate_device_secret, hash_secret
from app.models.admin_user import AdminUser
from app.models.device import Device
from app.models.enums import ActorType, EnrollmentStatus
from app.repositories import device_group_repository, device_repository
from app.schemas.device import (
    DeviceEnrollRequest,
    DeviceEnrollResponse,
    DeviceHeartbeatRequest,
    DeviceHeartbeatResponse,
    DeviceList,
    DeviceRead,
)
from app.schemas.device_group import DeviceAssignGroupRequest

router = APIRouter(prefix="/devices", tags=["devices"])


def _is_online(device: Device, online_cutoff: datetime) -> bool:
    return (
        device.enrollment_status == EnrollmentStatus.ACTIVE
        and device.last_seen is not None
        and device.last_seen >= online_cutoff
    )


def _online_cutoff() -> datetime:
    settings = get_settings()
    return datetime.now(timezone.utc) - timedelta(seconds=settings.device_online_threshold_seconds)


@router.post(
    "/enroll",
    response_model=DeviceEnrollResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_enrollment_key)],
)
@limiter.limit(lambda: get_settings().rate_limit_enroll)
async def enroll_device(
    request: Request,
    body: DeviceEnrollRequest,
    session: AsyncSession = Depends(get_db),
) -> DeviceEnrollResponse:
    """
    Enrolls a new device. Requires a valid `X-Enrollment-Key` header (a pre-shared secret, not
    tied to any specific device) so this isn't a fully open self-enrollment endpoint. Returns a
    device secret exactly once — only its Argon2id hash is ever persisted.
    """
    existing = await device_repository.get_by_uuid(session, body.device_uuid)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Device is already enrolled.")

    device_secret = generate_device_secret()
    device = await device_repository.create(
        session,
        device_uuid=body.device_uuid,
        hostname=body.hostname,
        operating_system=body.operating_system,
        agent_version=body.agent_version,
        device_secret_hash=hash_secret(device_secret),
    )

    await write_audit_log(
        session,
        actor_type=ActorType.DEVICE,
        actor_id=str(device.device_uuid),
        action="device.enroll",
        target_type="device",
        target_id=str(device.id),
        metadata={"hostname": device.hostname, "operating_system": device.operating_system},
    )

    await session.commit()
    await session.refresh(device)

    return DeviceEnrollResponse(
        id=device.id,
        device_uuid=device.device_uuid,
        device_secret=device_secret,
        enrollment_status=device.enrollment_status,
        created_at=device.created_at,
    )


@router.post("/heartbeat", response_model=DeviceHeartbeatResponse)
@limiter.limit(lambda: get_settings().rate_limit_heartbeat)
async def heartbeat(
    request: Request,
    body: DeviceHeartbeatRequest,
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_db),
) -> DeviceHeartbeatResponse:
    updated = await device_repository.record_heartbeat(
        session,
        device_id=device.id,
        seen_at=datetime.now(timezone.utc),
        agent_version=body.agent_version,
    )
    await session.commit()
    return DeviceHeartbeatResponse.model_validate(updated)


@router.get("", response_model=DeviceList)
async def list_devices(
    enrollment_status: EnrollmentStatus | None = Query(default=None),
    group_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> DeviceList:
    online_cutoff = _online_cutoff()

    items, total = await device_repository.list_paginated(
        session,
        enrollment_status_filter=enrollment_status,
        group_id_filter=group_id,
        limit=limit,
        offset=offset,
    )

    return DeviceList(
        items=[DeviceRead.from_device(device, online=_is_online(device, online_cutoff)) for device in items],
        total=total,
    )


@router.patch("/{device_id}/group", response_model=DeviceRead)
async def assign_device_group(
    device_id: int,
    body: DeviceAssignGroupRequest,
    admin: AdminUser = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db),
) -> DeviceRead:
    if body.group_id is not None:
        group = await device_group_repository.get_by_id(session, body.group_id)
        if group is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device group not found.")

    updated = await device_repository.assign_group(session, device_id=device_id, group_id=body.group_id)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found.")

    await write_audit_log(
        session,
        actor_type=ActorType.ADMIN,
        actor_id=str(admin.id),
        action="device.group_assigned",
        target_type="device",
        target_id=str(device_id),
        metadata={"group_id": body.group_id},
    )

    await session.commit()
    await session.refresh(updated)
    return DeviceRead.from_device(updated, online=_is_online(updated, _online_cutoff()))


@router.post("/{device_id}/request-update", response_model=DeviceRead)
async def request_device_update(
    device_id: int,
    admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> DeviceRead:
    """
    Flags this device to check for and apply an agent update on its next heartbeat, for when
    auto-update didn't already handle it (e.g. AutoUpdateEnabled was off, or the device missed its
    own check window). See app.api.v1.agent_compat.agent_heartbeat for where this is consumed.
    """
    updated = await device_repository.request_update(
        session, device_id=device_id, requested_at=datetime.now(timezone.utc)
    )
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found.")

    await write_audit_log(
        session,
        actor_type=ActorType.ADMIN,
        actor_id=str(admin.id),
        action="device.update_requested",
        target_type="device",
        target_id=str(device_id),
        metadata={},
    )

    await session.commit()
    await session.refresh(updated)
    return DeviceRead.from_device(updated, online=_is_online(updated, _online_cutoff()))
