"""
The three endpoints the real .NET agent actually calls, at the exact paths and wire shapes its
already-compiled HttpApprovalApiClient expects (see docs/API_CONTRACT.md and
app/schemas/agent_wire.py). Deliberately separate from app/api/v1/devices.py and
app/api/v1/elevation_requests.py, which serve the admin dashboard and use this backend's own
snake_case/HTTP-Basic conventions - the two families of endpoints share the same underlying
tables and repositories, just different wire contracts for different callers.
"""

import base64
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_device_bearer, get_db, require_enrollment_key
from app.config import get_settings
from app.core.approvals import issue_approval
from app.core.audit import write_audit_log
from app.core.rate_limit import limiter
from app.core.security import generate_device_secret, hash_secret
from app.models.device import Device
from app.models.enums import ActorType, ElevationRequestStatus, SignatureStatus
from app.repositories import (
    app_allowlist_repository,
    approval_repository,
    device_repository,
    elevation_request_repository,
)
from app.schemas.agent_wire import (
    AgentApprovalDecision,
    AgentApprovalRequest,
    AgentApprovalToken,
    AgentEnrollRequest,
    AgentEnrollResponse,
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    to_internal_signature_status,
)

router = APIRouter(tags=["agent-compat"])

_EPOCH = datetime.fromtimestamp(0, tz=timezone.utc)


@router.post(
    "/enroll",
    response_model=AgentEnrollResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_enrollment_key)],
)
@limiter.limit(lambda: get_settings().rate_limit_enroll)
async def agent_enroll(
    request: Request,
    body: AgentEnrollRequest,
    session: AsyncSession = Depends(get_db),
) -> AgentEnrollResponse:
    """POST /api/v1/enroll - HttpApprovalApiClient.EnrollAsync. Same X-Enrollment-Key gate and
    device row as the dashboard-facing POST /api/v1/devices/enroll, just returning a bearer
    token instead of an HTTP-Basic device secret, and without an agent_version (the agent's
    EnrollmentRequest has no such field - see Device.agent_version, now nullable)."""
    existing = await device_repository.get_by_uuid(session, body.device_id)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Device is already enrolled.")

    secret = generate_device_secret()
    device = await device_repository.create(
        session,
        device_uuid=body.device_id,
        hostname=body.machine_name,
        operating_system=body.operating_system_version,
        agent_version=None,
        device_secret_hash=hash_secret(secret),
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

    return AgentEnrollResponse(
        bearer_token=f"{device.device_uuid}.{secret}",
        enrolled_at_utc=device.created_at,
    )


@router.post("/requests", status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().rate_limit_elevation_request_submit)
async def agent_submit_request(
    request: Request,
    body: AgentApprovalRequest,
    device: Device = Depends(get_current_device_bearer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """POST /api/v1/requests - HttpApprovalApiClient.SubmitRequestAsync. The agent only checks
    EnsureSuccessStatusCode() on the response and never parses its body, so the response shape
    here is not part of the contract - it exists for API hygiene, not because anything reads it."""
    if body.device_id != device.device_uuid:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Request body deviceId does not match the authenticated device.",
        )

    settings = get_settings()
    now = datetime.now(timezone.utc)

    elevation_request = await elevation_request_repository.create(
        session,
        request_uuid=body.request_id,
        device_id=device.id,
        username=None,
        filename=body.file.file_name,
        canonical_path=body.file.full_path,
        sha256=body.file.sha256_hex,
        publisher=body.signature.publisher_common_name,
        signature_status=to_internal_signature_status(body.signature.trust_status),
        file_size=body.file.size_bytes,
        file_version=body.file.file_version,
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

    await _try_auto_approve(session, elevation_request=elevation_request, device=device)

    await session.commit()
    return {"requestId": str(elevation_request.request_uuid)}


async def _try_auto_approve(session: AsyncSession, *, elevation_request, device: Device) -> None:
    """
    Auto-approves a just-submitted request if it matches an app-allowlist entry scoped to this
    device's group (or a global entry) - see AppAllowlistEntry and docs/API_CONTRACT.md. Matches
    on (publisher, filename) rather than the exact sha256 the manual-approval flow implicitly
    binds to, so an entry keeps working across the app's own updates; to keep that looser match
    safe, it only ever applies when this specific submission's signature was independently
    verified Trusted by the agent - an untrusted/unsigned/hash-mismatched file with the same
    publisher/filename text always falls through to the ordinary human-review queue instead.
    """
    if elevation_request.signature_status != SignatureStatus.TRUSTED:
        return
    if elevation_request.publisher is None:
        return

    match = await app_allowlist_repository.find_match(
        session,
        device_group_id=device.group_id,
        publisher=elevation_request.publisher,
        filename=elevation_request.filename,
    )
    if match is None:
        return

    updated = await elevation_request_repository.transition_status(
        session,
        elevation_request_id=elevation_request.id,
        expected_current_status=ElevationRequestStatus.PENDING,
        new_status=ElevationRequestStatus.APPROVED,
        reviewed_by=None,
        reviewed_at=datetime.now(timezone.utc),
    )
    if updated is None:
        return  # lost a race (implausible immediately after creation) - leave it pending

    approval = await issue_approval(session, elevation_request=updated, device=device)

    await write_audit_log(
        session,
        actor_type=ActorType.SYSTEM,
        actor_id=f"app_allowlist_entry:{match.id}",
        action="elevation_request.auto_approved",
        target_type="elevation_request",
        target_id=str(updated.id),
        metadata={
            "nonce": approval.nonce,
            "matched_allowlist_entry_id": match.id,
            "publisher": elevation_request.publisher,
            "filename": elevation_request.filename,
        },
    )


@router.post("/heartbeat", response_model=AgentHeartbeatResponse)
@limiter.limit(lambda: get_settings().rate_limit_heartbeat)
async def agent_heartbeat(
    request: Request,
    body: AgentHeartbeatRequest,
    device: Device = Depends(get_current_device_bearer),
    session: AsyncSession = Depends(get_db),
) -> AgentHeartbeatResponse:
    """
    POST /api/v1/heartbeat - not part of the agent's originally-shipped contract (added alongside
    HttpApprovalApiClient.SendHeartbeatAsync so the dashboard can show live disk/RAM telemetry and
    the agent's own running version per device, and so an admin's "update now" request actually
    reaches the device). Bearer device auth, same as /requests and /devices/{id}/decisions.
    """
    now = datetime.now(timezone.utc)
    updated = await device_repository.record_heartbeat(
        session,
        device_id=device.id,
        seen_at=now,
        agent_version=body.agent_version,
        disk_total_bytes=body.disk_total_bytes,
        disk_free_bytes=body.disk_free_bytes,
        ram_total_bytes=body.ram_total_bytes,
        ram_used_bytes=body.ram_used_bytes,
        telemetry_at=now,
    )

    update_requested = updated.update_requested_at is not None
    if (
        update_requested
        and body.agent_version is not None
        and body.agent_version != updated.update_requested_from_version
    ):
        # The requested update actually landed - this heartbeat is running a different version
        # than the one recorded when the admin asked for an update.
        await device_repository.clear_update_requested(session, device_id=device.id)
        update_requested = False

    await session.commit()
    return AgentHeartbeatResponse(update_requested=update_requested)


@router.get("/devices/{device_id}/decisions", response_model=list[AgentApprovalDecision])
@limiter.limit(lambda: get_settings().rate_limit_agent_decisions)
async def agent_poll_decisions(
    request: Request,
    device_id: str = Path(...),
    since: datetime | None = Query(default=None),
    device: Device = Depends(get_current_device_bearer),
    session: AsyncSession = Depends(get_db),
) -> list[AgentApprovalDecision]:
    """GET /api/v1/devices/{deviceId}/decisions?since=... - HttpApprovalApiClient
    .PollDecisionsAsync. `device_id` is a path segment purely because that's the shape the
    already-built agent requests - identity for the actual query still comes exclusively from
    the authenticated bearer token, and a mismatch is rejected rather than silently ignored, so
    a device can never even probe whether some other deviceId path resolves to a real device."""
    if device_id != str(device.device_uuid):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Cannot poll decisions for a different device."
        )

    now = datetime.now(timezone.utc)

    await elevation_request_repository.expire_stale_pending_requests_for_device(
        session, device_id=device.id, now=now
    )
    await session.commit()

    rows = await approval_repository.list_decisions_for_device_since(
        session, device_id=device.id, since=since or _EPOCH
    )

    decisions: list[AgentApprovalDecision] = []
    for elevation_request, approval in rows:
        token = None
        if approval is not None:
            token = AgentApprovalToken(
                device_id=approval.device_uuid,
                request_id=elevation_request.request_uuid,
                sha256_hex=approval.sha256,
                expires_at_utc=approval.expires_at,
                nonce=approval.nonce,
                signature=base64.b64encode(approval.signature).decode("ascii"),
            )
        decisions.append(
            AgentApprovalDecision(
                request_id=elevation_request.request_uuid,
                status=elevation_request.status,
                token=token,
            )
        )
    return decisions
