"""Initial IoT platform schema.

Revision ID: 20260309_01
Revises:
Create Date: 2026-03-09 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260309_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_devices_slug", "devices", ["slug"], unique=False)

    op.create_table(
        "feeds",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data_type", sa.String(length=64), nullable=False),
        sa.Column("last_value", sa.Text(), nullable=True),
        sa.Column("last_value_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("device_id", "key", name="uq_feeds_device_key"),
    )
    op.create_index("ix_feeds_device_id", "feeds", ["device_id"], unique=False)
    op.create_index("ix_feeds_key", "feeds", ["key"], unique=False)

    op.create_table(
        "feed_values",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_feed_values_feed_id", "feed_values", ["feed_id"], unique=False)

    op.create_table(
        "commands",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_commands_device_id", "commands", ["device_id"], unique=False)
    op.create_index("ix_commands_status", "commands", ["status"], unique=False)

    op.create_table(
        "dashboards",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_dashboards_owner_id", "dashboards", ["owner_id"], unique=False)

    op.create_table(
        "dashboard_widgets",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("dashboard_id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("widget_type", sa.String(length=64), nullable=False),
        sa.Column("position_x", sa.Integer(), nullable=False),
        sa.Column("position_y", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["dashboard_id"], ["dashboards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_dashboard_widgets_dashboard_id", "dashboard_widgets", ["dashboard_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_dashboard_widgets_dashboard_id", table_name="dashboard_widgets")
    op.drop_table("dashboard_widgets")
    op.drop_index("ix_dashboards_owner_id", table_name="dashboards")
    op.drop_table("dashboards")
    op.drop_index("ix_commands_status", table_name="commands")
    op.drop_index("ix_commands_device_id", table_name="commands")
    op.drop_table("commands")
    op.drop_index("ix_feed_values_feed_id", table_name="feed_values")
    op.drop_table("feed_values")
    op.drop_index("ix_feeds_key", table_name="feeds")
    op.drop_index("ix_feeds_device_id", table_name="feeds")
    op.drop_table("feeds")
    op.drop_index("ix_devices_slug", table_name="devices")
    op.drop_table("devices")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")