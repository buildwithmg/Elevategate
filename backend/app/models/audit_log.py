from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ActorType


class AuditLog(Base):
    """
    Append-only. Never updated or deleted by the application. Written inside the same
    transaction as the action it records (see app.core.audit.write_audit_log) so the audit trail
    can never observe a state change that didn't actually commit, or vice versa.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type", native_enum=False, validate_strings=True), nullable=False
    )
    # Generic string reference (admin user id, or device_uuid) rather than a polymorphic FK -
    # this table outlives and cross-cuts every other entity, so it deliberately doesn't
    # foreign-key into any of them.
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Mapped to the "metadata" column under a different Python attribute name because
    # `metadata` is a reserved attribute on every SQLAlchemy declarative model (Base.metadata).
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
