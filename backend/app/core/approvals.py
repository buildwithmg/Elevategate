import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.signing import build_canonical_payload, sign_payload
from app.models.approval import Approval
from app.models.device import Device
from app.models.elevation_request import ElevationRequest
from app.repositories import approval_repository


async def issue_approval(
    session: AsyncSession, *, elevation_request: ElevationRequest, device: Device
) -> Approval:
    """
    Generates the nonce, builds and Ed25519-signs the canonical payload, and persists the
    resulting Approval row. Callers must have *already* atomically transitioned the request to
    APPROVED (see elevation_request_repository.transition_status) before calling this - it does
    not check or change the request's status itself. Shared by the admin manual-approve endpoint
    (app.api.v1.elevation_requests) and the allowlist auto-approve path
    (app.api.v1.agent_compat.agent_submit_request) so there is exactly one place that builds a
    signed approval.
    """
    settings = get_settings()
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=settings.approval_ttl_seconds)
    nonce = secrets.token_urlsafe(24)

    payload = build_canonical_payload(
        device_uuid=str(device.device_uuid),
        request_uuid=str(elevation_request.request_uuid),
        sha256=elevation_request.sha256,
        expires_at=expires_at,
        nonce=nonce,
    )
    signature = sign_payload(payload)

    return await approval_repository.create(
        session,
        elevation_request_id=elevation_request.id,
        device_uuid=device.device_uuid,
        sha256=elevation_request.sha256,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
        signature=signature,
    )
