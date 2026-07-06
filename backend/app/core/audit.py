from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.enums import ActorType


async def write_audit_log(
    session: AsyncSession,
    *,
    actor_type: ActorType,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict | None = None,
) -> None:
    """
    Stages an AuditLog row on `session` without committing. Callers must write this inside the
    same transaction as the state change it records, and commit them together — an audit entry
    must never exist for an action that didn't commit, or be missing for one that did.
    """
    session.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_=metadata,
        )
    )
