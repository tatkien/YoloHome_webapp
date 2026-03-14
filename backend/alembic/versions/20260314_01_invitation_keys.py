"""Add invitation_keys table

Revision ID: 20260314_01
Revises: 20260311_01
Create Date: 2026-03-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260314_01"
down_revision = "20260311_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invitation_keys",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("invitation_keys")
