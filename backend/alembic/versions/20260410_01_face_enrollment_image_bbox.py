"""Add image_path and bbox to face_enrollments.

Revision ID: 20260410_01
Revises: 20260323_01
Create Date: 2026-04-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260410_01"
down_revision = "20260323_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("face_enrollments", sa.Column("image_path", sa.String(length=512), nullable=True))
    op.add_column("face_enrollments", sa.Column("bbox", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("face_enrollments", "bbox")
    op.drop_column("face_enrollments", "image_path")
