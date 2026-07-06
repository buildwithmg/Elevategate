import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ElevationRequestStatus, SignatureStatus

if TYPE_CHECKING:
    from app.models.device import Device


class ElevationRequest(Base):
    __tablename__ = "elevation_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_uuid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, index=True, nullable=False, default=uuid.uuid4
    )
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    # Eagerly (joined) loaded - the dashboard shows device_uuid/hostname alongside every
    # elevation request (table + detail view), so this is effectively always needed.
    device: Mapped["Device"] = relationship(lazy="joined")
    # Nullable: the .NET agent's ApprovalRequest never captures the local Windows username (see
    # docs/API_CONTRACT.md) - a request submitted via the agent-compatible route genuinely has none.
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    publisher: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signature_status: Mapped[SignatureStatus] = mapped_column(
        Enum(SignatureStatus, name="signature_status", native_enum=False, validate_strings=True),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ElevationRequestStatus] = mapped_column(
        Enum(ElevationRequestStatus, name="elevation_request_status", native_enum=False, validate_strings=True),
        nullable=False,
        default=ElevationRequestStatus.PENDING,
        index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    # When the *request itself* stops being reviewable if left pending (distinct from an issued
    # Approval's own, shorter, expiry).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def device_uuid(self) -> uuid.UUID:
        return self.device.device_uuid

    @property
    def device_hostname(self) -> str:
        return self.device.hostname
