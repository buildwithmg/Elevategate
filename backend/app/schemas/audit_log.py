from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ActorType


class AuditLogRead(BaseModel):
    id: int
    actor_type: ActorType
    actor_id: str
    action: str
    target_type: str
    target_id: str
    metadata: dict | None
    timestamp: datetime

    @classmethod
    def from_model(cls, audit_log) -> "AuditLogRead":
        # Built explicitly (not via from_attributes) because the ORM's Python attribute is
        # `metadata_` - `metadata` is reserved on every SQLAlchemy declarative model
        # (Base.metadata) - but the public API field is the plain, correct `metadata`.
        return cls(
            id=audit_log.id,
            actor_type=audit_log.actor_type,
            actor_id=audit_log.actor_id,
            action=audit_log.action,
            target_type=audit_log.target_type,
            target_id=audit_log.target_id,
            metadata=audit_log.metadata_,
            timestamp=audit_log.timestamp,
        )


class AuditLogList(BaseModel):
    items: list[AuditLogRead]
    total: int
