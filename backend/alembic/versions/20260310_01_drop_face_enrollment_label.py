"""Drop label column from face_enrollments

Revision ID: 20260310_01
Revises: 20260309_05
Create Date: 2026-03-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260310_01"
down_revision = "20260309_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("face_enrollments", "label")


def downgrade() -> None:
    op.add_column(
        "face_enrollments",
        sa.Column("label", sa.String(length=128), nullable=True),
    )
