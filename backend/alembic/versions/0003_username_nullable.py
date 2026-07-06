"""elevation_requests.username nullable

Revision ID: 0003_username_nullable
Revises: 0002_agent_version_nullable
Create Date: 2026-07-06 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003_username_nullable'
down_revision: Union[str, None] = '0002_agent_version_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The .NET agent's ApprovalRequest never sends a Windows username (it was never captured
    # anywhere in the shipped agent) - a request submitted through the agent-compatible
    # POST /api/v1/requests genuinely has no username. Disclosed, not papered over: see
    # docs/API_CONTRACT.md and the dashboard's handling of a null username.
    op.alter_column('elevation_requests', 'username', existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    op.alter_column('elevation_requests', 'username', existing_type=sa.String(length=255), nullable=False)
