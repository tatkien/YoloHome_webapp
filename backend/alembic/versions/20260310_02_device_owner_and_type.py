"""Add device_type, rename created_by_id → owner_id (NOT NULL CASCADE), per-owner slug uniqueness

Revision ID: 20260310_02
Revises: 20260310_01
Create Date: 2026-03-10 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260310_02"
down_revision = "20260310_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop the old global unique constraint on slug and its regular index
    op.drop_constraint("devices_slug_key", "devices", type_="unique")
    op.drop_index("ix_devices_slug", table_name="devices")

    # 2. Drop old FK (SET NULL, references created_by_id)
    op.drop_constraint("devices_created_by_id_fkey", "devices", type_="foreignkey")

    # 3. Rename created_by_id → owner_id
    op.alter_column("devices", "created_by_id", new_column_name="owner_id")

    # 4. Ensure no NULL rows before making NOT NULL
    #    (delete orphaned devices whose creator no longer exists)
    op.execute("DELETE FROM devices WHERE owner_id IS NULL")

    # 5. Make owner_id NOT NULL
    op.alter_column("devices", "owner_id", nullable=False, existing_type=sa.Integer())

    # 6. Recreate FK with CASCADE (owner deleted → their devices deleted)
    op.create_foreign_key(
        "devices_owner_id_fkey", "devices", "users", ["owner_id"], ["id"], ondelete="CASCADE"
    )

    # 7. Add device_type column
    op.add_column("devices", sa.Column("device_type", sa.String(length=32), nullable=True))
    # Default existing rows to 'light' so we can make it NOT NULL
    op.execute("UPDATE devices SET device_type = 'light' WHERE device_type IS NULL")
    op.alter_column("devices", "device_type", nullable=False, existing_type=sa.String(length=32))

    # 8. Recreate slug index (non-unique; uniqueness enforced by composite constraint below)
    op.create_index("ix_devices_slug", "devices", ["slug"], unique=False)

    # 9. Composite unique: one slug per owner
    op.create_unique_constraint("uq_device_owner_slug", "devices", ["owner_id", "slug"])


def downgrade() -> None:
    op.drop_constraint("uq_device_owner_slug", "devices", type_="unique")
    op.drop_index("ix_devices_slug", table_name="devices")
    op.drop_column("devices", "device_type")
    op.drop_constraint("devices_owner_id_fkey", "devices", type_="foreignkey")
    op.alter_column("devices", "owner_id", new_column_name="created_by_id")
    op.alter_column("devices", "created_by_id", nullable=True, existing_type=sa.Integer())
    op.create_foreign_key(
        "devices_created_by_id_fkey", "devices", "users",
        ["created_by_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_devices_slug", "devices", ["slug"], unique=False)
    op.create_unique_constraint("devices_slug_key", "devices", ["slug"])
