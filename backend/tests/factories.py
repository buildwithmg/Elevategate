import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_secret
from app.models.admin_user import AdminUser
from app.models.device import Device
from app.models.elevation_request import ElevationRequest
from app.models.enums import AdminRole, ElevationRequestStatus, EnrollmentStatus, SignatureStatus


async def create_device(
    session: AsyncSession,
    *,
    device_uuid: uuid.UUID | None = None,
    hostname: str = "TEST-WORKSTATION",
    operating_system: str = "Windows 11 23H2",
    agent_version: str = "1.0.0",
    secret: str = "test-device-secret",
    enrollment_status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
) -> tuple[Device, str]:
    device = Device(
        device_uuid=device_uuid or uuid.uuid4(),
        hostname=hostname,
        operating_system=operating_system,
        agent_version=agent_version,
        device_secret_hash=hash_secret(secret),
        enrollment_status=enrollment_status,
    )
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return device, secret


async def create_admin(
    session: AsyncSession,
    *,
    email: str = "admin@example.com",
    name: str = "Test Admin",
    password: str = "Str0ng!Password",
    role: AdminRole = AdminRole.ADMIN,
) -> tuple[AdminUser, str]:
    admin = AdminUser(
        email=email, name=name, password_hash=hash_secret(password), role=role, is_active=True
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin, password


async def create_elevation_request(
    session: AsyncSession,
    *,
    device: Device,
    username: str = "jdoe",
    filename: str = "installer.exe",
    canonical_path: str = r"C:\Temp\installer.exe",
    sha256: str = "a" * 64,
    publisher: str | None = "Contoso Ltd.",
    signature_status: SignatureStatus = SignatureStatus.TRUSTED,
    file_size: int = 1024,
    file_version: str | None = "1.0.0.0",
    reason: str = "Need this installed for a printer driver.",
    status: ElevationRequestStatus = ElevationRequestStatus.PENDING,
    ttl_seconds: int = 3600,
) -> ElevationRequest:
    elevation_request = ElevationRequest(
        request_uuid=uuid.uuid4(),
        device_id=device.id,
        username=username,
        filename=filename,
        canonical_path=canonical_path,
        sha256=sha256,
        publisher=publisher,
        signature_status=signature_status,
        file_size=file_size,
        file_version=file_version,
        reason=reason,
        status=status,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
    )
    session.add(elevation_request)
    await session.commit()
    await session.refresh(elevation_request)
    return elevation_request
