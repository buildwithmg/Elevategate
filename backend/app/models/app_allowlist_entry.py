from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppAllowlistEntry(Base):
    """
    An app that's allowed to run without a human approving each request. Matched against an
    incoming elevation request by (publisher, filename) - deliberately not by sha256, unlike the
    manual-approval flow's "bind to one exact file" model - so an entry keeps working across the
    app's own updates without needing a new entry per build. To keep that looser match safe, a
    match only auto-approves when the submitted request's signature_status is TRUSTED (see
    app.api.v1.agent_compat.agent_submit_request) - an untrusted/unsigned/hash-mismatched file
    with the same publisher/filename text never auto-approves, only ever falls through to the
    ordinary human-review queue.
    """

    __tablename__ = "app_allowlist_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Null means the entry applies to every device, regardless of group.
    group_id: Mapped[int | None] = mapped_column(ForeignKey("device_groups.id"), nullable=True, index=True)
    publisher: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
