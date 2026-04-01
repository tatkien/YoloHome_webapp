"""Add device_schedules table

Revision ID: 20260314_02
Revises: 20260314_01
Create Date: 2026-03-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260314_02"
down_revision = "20260314_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_schedules",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("time_of_day", sa.Time(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_triggered_on", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_device_schedules_device_id",
        "device_schedules",
        ["device_id"],
        unique=False,
    )
    op.create_index(
        "ix_device_schedules_time_of_day",
        "device_schedules",
        ["time_of_day"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_device_schedules_time_of_day", table_name="device_schedules")
    op.drop_index("ix_device_schedules_device_id", table_name="device_schedules")
    op.drop_table("device_schedules")
