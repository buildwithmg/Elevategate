"""devices.agent_version nullable

Revision ID: 0002_agent_version_nullable
Revises: 0001_initial_schema
Create Date: 2026-07-06 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_agent_version_nullable'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The .NET agent's enrollment request has no agent-version concept (it's only ever supplied
    # later, via heartbeat) - so a device enrolled through the agent-compatible /api/v1/enroll
    # route genuinely doesn't have one yet at creation time.
    op.alter_column('devices', 'agent_version', existing_type=sa.String(length=50), nullable=True)


def downgrade() -> None:
    op.alter_column('devices', 'agent_version', existing_type=sa.String(length=50), nullable=False)
