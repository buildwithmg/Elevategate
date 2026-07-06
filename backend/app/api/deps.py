import uuid

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import TokenError, decode_access_token, verify_secret
from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.device import Device
from app.models.enums import EnrollmentStatus
from app.repositories import admin_user_repository, device_repository

_bearer_scheme = HTTPBearer(auto_error=False)
_basic_scheme = HTTPBasic(auto_error=False)
_device_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials=Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> AdminUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    try:
        admin_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")

    admin = await admin_user_repository.get_by_id(session, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Account is not active.")

    return admin


def require_role(*roles: str):
    async def dependency(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if admin.role.value not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient role.")
        return admin

    return dependency


async def get_current_device(
    credentials: HTTPBasicCredentials | None = Depends(_basic_scheme),
    session: AsyncSession = Depends(get_db),
) -> Device:
    """
    Device-specific authentication: HTTP Basic where the username is the device's own
    device_uuid and the password is the enrollment-issued device_secret, verified against the
    Argon2id hash on file - never a JWT, never a shared bearer token, and never anything that
    could be replayed to authenticate as a *different* device.
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing device credentials.")

    try:
        device_uuid = uuid.UUID(credentials.username)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid device credentials.")

    device = await device_repository.get_by_uuid(session, device_uuid)
    if device is None or not verify_secret(credentials.password, device.device_secret_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid device credentials.")

    if device.enrollment_status != EnrollmentStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Device is not active.")

    return device


async def require_enrollment_key(x_enrollment_key: str = Header(...)) -> None:
    settings = get_settings()
    if x_enrollment_key != settings.enrollment_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid enrollment key.")


async def get_current_device_bearer(
    credentials=Depends(_device_bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> Device:
    """
    Device authentication for the .NET agent's actual wire contract: a single opaque
    `Authorization: Bearer <token>` (ElevateGate.Core.Models.EnrollmentResult.BearerToken),
    issued once at enrollment - the agent has no concept of HTTP Basic device credentials.

    The token is `"<device_uuid>.<secret>"`: a self-contained but still O(1)-lookupable opaque
    string. The device_uuid prefix is not itself a secret (it's already public - the agent
    presents it as its own identity elsewhere), so exposing it lets the backend look the device
    up directly instead of scanning every enrolled device's Argon2id hash on every request. The
    secret half is generated the same way as the HTTP-Basic device_secret and verified the same
    way (Argon2id, constant-time) - it is the only part that authenticates anything.
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing device bearer token.")

    device_uuid_str, _, secret = credentials.credentials.partition(".")
    if not secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Malformed device bearer token.")

    try:
        device_uuid = uuid.UUID(device_uuid_str)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Malformed device bearer token.")

    device = await device_repository.get_by_uuid(session, device_uuid)
    if device is None or not verify_secret(secret, device.device_secret_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid device bearer token.")

    if device.enrollment_status != EnrollmentStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Device is not active.")

    return device
