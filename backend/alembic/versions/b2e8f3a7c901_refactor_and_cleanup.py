"""refactor_and_cleanup

Revision ID: b2e8f3a7c901
Revises: a1d9401a5669
Create Date: 2026-04-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e8f3a7c901'
down_revision: Union[str, Sequence[str]] = 'a1d9401a5669'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ---------------------------------------------------------------
    # 1. devices table: rename camelCase columns to snake_case
    # ---------------------------------------------------------------
    op.alter_column('devices', 'isOn', new_column_name='is_on')
    op.alter_column('devices', 'createdBy', new_column_name='created_by')
    op.alter_column('devices', 'createdAt', new_column_name='created_at')
    op.alter_column('devices', 'hardwareId', new_column_name='hardware_id')

    # Drop removed columns
    op.drop_index(op.f('ix_devices_search_keywords'), table_name='devices')
    op.drop_column('devices', 'search_keywords')
    op.drop_column('devices', 'scheduledOnTime')
    op.drop_column('devices', 'scheduledOffTime')

    # Change value column from INTEGER to FLOAT
    op.alter_column(
        'devices', 'value',
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using='value::double precision',
    )

    # ---------------------------------------------------------------
    # 2. hardware_nodes table: rename createdAt -> created_at
    # ---------------------------------------------------------------
    op.alter_column('hardware_nodes', 'createdAt', new_column_name='created_at')

    # ---------------------------------------------------------------
    # 3. Drop device_shares table entirely
    # ---------------------------------------------------------------
    op.drop_table('device_shares')


    # Create the schedule_action_enum type
    schedule_action_enum = sa.Enum('on', 'off', name='schedule_action_enum')
    schedule_action_enum.create(op.get_bind(), checkfirst=True)

    # Change action column from varchar to enum
    op.alter_column(
        'device_schedules', 'action',
        existing_type=sa.String(16),
        type_=sa.Enum('on', 'off', name='schedule_action_enum'),
        existing_nullable=False,
        postgresql_using="action::schedule_action_enum",
    )

    # ---------------------------------------------------------------
    # 5. Alter device_type_enum: remove 'unknown' value
    # ---------------------------------------------------------------
    # PostgreSQL does not support DROP VALUE from enum directly.
    # We: rename old -> _old, create new, migrate column, drop _old.
    op.execute("ALTER TYPE device_type_enum RENAME TO device_type_enum_old")
    op.execute(
        "CREATE TYPE device_type_enum AS ENUM "
        "('fan', 'light', 'camera', 'lock', 'temp_sensor', 'humidity_sensor')"
    )
    # Migrate any 'unknown' rows to 'light' before casting
    op.execute("UPDATE devices SET type = 'light' WHERE type = 'unknown'")
    op.execute(
        "ALTER TABLE devices ALTER COLUMN type TYPE device_type_enum "
        "USING type::text::device_type_enum"
    )
    op.execute("DROP TYPE device_type_enum_old")

    # ---------------------------------------------------------------
    # 6. device_schedules: drop created_by_id column
    # ---------------------------------------------------------------
    op.drop_column('device_schedules', 'created_by_id')

    # ---------------------------------------------------------------
    # 7. face_enrollments: make device_id NOT NULL + CASCADE
    # ---------------------------------------------------------------
    op.drop_constraint(
        'face_enrollments_device_id_fkey', 'face_enrollments', type_='foreignkey'
    )
    op.alter_column(
        'face_enrollments', 'device_id',
        existing_type=sa.String(64),
        nullable=False,
    )
    op.create_foreign_key(
        'face_enrollments_device_id_fkey',
        'face_enrollments', 'devices',
        ['device_id'], ['id'],
        ondelete='CASCADE',
    )

    # ---------------------------------------------------------------
    # 8. face_recognition_logs: make device_id NOT NULL + CASCADE
    # ---------------------------------------------------------------
    op.drop_constraint(
        'face_recognition_logs_device_id_fkey', 'face_recognition_logs', type_='foreignkey'
    )
    op.alter_column(
        'face_recognition_logs', 'device_id',
        existing_type=sa.String(64),
        nullable=False,
    )
    op.create_foreign_key(
        'face_recognition_logs_device_id_fkey',
        'face_recognition_logs', 'devices',
        ['device_id'], ['id'],
        ondelete='CASCADE',
    )

    # ---------------------------------------------------------------
    # 9. Create sensor_data table
    # ---------------------------------------------------------------
    op.create_table(
        'sensor_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.String(length=64), nullable=True),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column(
            'sensor_type',
            sa.Enum('fan', 'light', 'camera', 'lock', 'temp_sensor', 'humidity_sensor', name='sensor_type_enum'),
            nullable=False
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sensor_data_device_id'), 'sensor_data', ['device_id'], unique=False)
    op.create_index(op.f('ix_sensor_data_created_at'), 'sensor_data', ['created_at'], unique=False)
    op.create_index(op.f('ix_sensor_data_id'), 'sensor_data', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""

    # 9. Drop sensor_data table
    op.drop_index(op.f('ix_sensor_data_id'), table_name='sensor_data')
    op.drop_index(op.f('ix_sensor_data_created_at'), table_name='sensor_data')
    op.drop_index(op.f('ix_sensor_data_device_id'), table_name='sensor_data')
    op.drop_table('sensor_data')
    op.execute("DROP TYPE IF EXISTS sensor_type_enum")

    # 8. Revert face_recognition_logs.device_id to nullable + SET NULL
    op.drop_constraint(
        'face_recognition_logs_device_id_fkey', 'face_recognition_logs', type_='foreignkey'
    )
    op.alter_column(
        'face_recognition_logs', 'device_id',
        existing_type=sa.String(64),
        nullable=True,
    )
    op.create_foreign_key(
        'face_recognition_logs_device_id_fkey',
        'face_recognition_logs', 'devices',
        ['device_id'], ['id'],
        ondelete='SET NULL',
    )

    # 7. Revert face_enrollments.device_id to nullable + SET NULL
    op.drop_constraint(
        'face_enrollments_device_id_fkey', 'face_enrollments', type_='foreignkey'
    )
    op.alter_column(
        'face_enrollments', 'device_id',
        existing_type=sa.String(64),
        nullable=True,
    )
    op.create_foreign_key(
        'face_enrollments_device_id_fkey',
        'face_enrollments', 'devices',
        ['device_id'], ['id'],
        ondelete='SET NULL',
    )

    # 6. Restore created_by_id on device_schedules
    op.add_column(
        'device_schedules',
        sa.Column('created_by_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'device_schedules_created_by_id_fkey',
        'device_schedules', 'users',
        ['created_by_id'], ['id'],
        ondelete='SET NULL',
    )

    # 5. Restore device_type_enum with 'unknown'
    op.execute("ALTER TYPE device_type_enum RENAME TO device_type_enum_old")
    op.execute(
        "CREATE TYPE device_type_enum AS ENUM "
        "('fan', 'light', 'camera', 'lock', 'temp_sensor', 'humidity_sensor', 'unknown')"
    )
    op.execute(
        "ALTER TABLE devices ALTER COLUMN type TYPE device_type_enum "
        "USING type::text::device_type_enum"
    )
    op.execute("DROP TYPE device_type_enum_old")

    # 4. Revert device_schedules
    op.alter_column(
        'device_schedules', 'action',
        existing_type=sa.Enum('on', 'off', name='schedule_action_enum'),
        type_=sa.String(16),
        existing_nullable=False,
    )
    op.execute("DROP TYPE IF EXISTS schedule_action_enum")
    op.drop_column('device_schedules', 'times_of_day')
    op.add_column(
        'device_schedules',
        sa.Column('time_of_day', sa.Time(), nullable=False),
    )

    # 3. Recreate device_shares table
    op.create_table(
        'device_shares',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.String(length=64), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 2. hardware_nodes: revert created_at -> createdAt
    op.alter_column('hardware_nodes', 'created_at', new_column_name='createdAt')

    # 1. devices: revert snake_case -> camelCase
    op.alter_column(
        'devices', 'value',
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using='value::integer',
    )
    op.add_column('devices', sa.Column('scheduledOffTime', sa.String(length=32), nullable=True))
    op.add_column('devices', sa.Column('scheduledOnTime', sa.String(length=32), nullable=True))
    op.add_column('devices', sa.Column('search_keywords', sa.Text(), nullable=True))
    op.create_index(op.f('ix_devices_search_keywords'), 'devices', ['search_keywords'], unique=False)

    op.alter_column('devices', 'hardware_id', new_column_name='hardwareId')
    op.alter_column('devices', 'created_at', new_column_name='createdAt')
    op.alter_column('devices', 'created_by', new_column_name='createdBy')
    op.alter_column('devices', 'is_on', new_column_name='isOn')
