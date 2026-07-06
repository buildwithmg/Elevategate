import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import EnrollmentStatus


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_uuid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, index=True, nullable=False
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    operating_system: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nullable: a device enrolled via the agent-compatible /api/v1/enroll route doesn't report a
    # version until its first heartbeat (the .NET agent's EnrollmentRequest has no such field).
    agent_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enrollment_status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus, name="enrollment_status", native_enum=False, validate_strings=True),
        nullable=False,
        default=EnrollmentStatus.ACTIVE,
    )
    # Argon2id hash of the device's enrollment secret - the plaintext is returned exactly once,
    # in the enroll response, and never persisted or logged anywhere.
    device_secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
