"""Drop feature_vector from face_recognition_logs.

Revision ID: 20260323_01
Revises: 20260319_01
Create Date: 2026-03-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "20260323_01"
down_revision = "20260319_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("face_recognition_logs", "feature_vector")


def downgrade() -> None:
    op.add_column(
        "face_recognition_logs",
        sa.Column("feature_vector", Vector(512), nullable=True),
    )
