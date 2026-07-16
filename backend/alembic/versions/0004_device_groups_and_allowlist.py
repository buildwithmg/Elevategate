"""device groups, app allowlist, device telemetry

Revision ID: 0004_device_groups_and_allowlist
Revises: 0003_username_nullable
Create Date: 2026-07-17 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004_device_groups_and_allowlist'
down_revision: Union[str, None] = '0003_username_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'device_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_device_groups_name'), 'device_groups', ['name'], unique=True)

    op.create_table(
        'app_allowlist_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=True),
        sa.Column('publisher', sa.String(length=500), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        # CASCADE (not SET NULL, unlike devices.group_id): an entry scoped to a group that no
        # longer exists should not silently become a global "any device" allow rule.
        sa.ForeignKeyConstraint(['group_id'], ['device_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['admin_users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_app_allowlist_entries_group_id'), 'app_allowlist_entries', ['group_id'], unique=False)

    op.add_column('devices', sa.Column('group_id', sa.Integer(), nullable=True))
    op.add_column('devices', sa.Column('disk_total_bytes', sa.BigInteger(), nullable=True))
    op.add_column('devices', sa.Column('disk_free_bytes', sa.BigInteger(), nullable=True))
    op.add_column('devices', sa.Column('ram_total_bytes', sa.BigInteger(), nullable=True))
    op.add_column('devices', sa.Column('ram_used_bytes', sa.BigInteger(), nullable=True))
    op.add_column('devices', sa.Column('last_telemetry_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('devices', sa.Column('update_requested_at', sa.DateTime(timezone=True), nullable=True))
    # Snapshot of agent_version at the moment an update was requested, so a later heartbeat can
    # tell "the update actually landed" (version changed) apart from "still on the old build."
    op.add_column('devices', sa.Column('update_requested_from_version', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_devices_group_id'), 'devices', ['group_id'], unique=False)
    op.create_foreign_key(
        'fk_devices_group_id_device_groups', 'devices', 'device_groups', ['group_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_devices_group_id_device_groups', 'devices', type_='foreignkey')
    op.drop_index(op.f('ix_devices_group_id'), table_name='devices')
    op.drop_column('devices', 'update_requested_from_version')
    op.drop_column('devices', 'update_requested_at')
    op.drop_column('devices', 'last_telemetry_at')
    op.drop_column('devices', 'ram_used_bytes')
    op.drop_column('devices', 'ram_total_bytes')
    op.drop_column('devices', 'disk_free_bytes')
    op.drop_column('devices', 'disk_total_bytes')
    op.drop_column('devices', 'group_id')

    op.drop_index(op.f('ix_app_allowlist_entries_group_id'), table_name='app_allowlist_entries')
    op.drop_table('app_allowlist_entries')

    op.drop_index(op.f('ix_device_groups_name'), table_name='device_groups')
    op.drop_table('device_groups')
