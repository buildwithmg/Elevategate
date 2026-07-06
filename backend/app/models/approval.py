import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ApprovalAction


class Approval(Base):
    """
    Created exactly once, at the moment an admin approves an elevation request — never for a
    denial, since a denial authorizes nothing and needs no signature. Denormalizes device_uuid
    and sha256 from the parent ElevationRequest/Device onto the row itself (rather than requiring
    a join) so the exact fields that were signed are directly, permanently visible on this record.
    """

    __tablename__ = "approvals"
    __table_args__ = (UniqueConstraint("nonce", name="uq_approvals_nonce"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    elevation_request_id: Mapped[int] = mapped_column(
        ForeignKey("elevation_requests.id"), unique=True, nullable=False, index=True
    )
    action: Mapped[ApprovalAction] = mapped_column(
        Enum(ApprovalAction, name="approval_action", native_enum=False, validate_strings=True),
        nullable=False,
        default=ApprovalAction.EXECUTE,
    )
    device_uuid: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
