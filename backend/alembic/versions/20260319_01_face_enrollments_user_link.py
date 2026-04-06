"""Link face enrollments to users and track matched users in logs.

Revision ID: 20260319_01
Revises: 20260314_02
Create Date: 2026-03-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260319_01"
down_revision = "20260314_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reset existing enrollments per product decision before enforcing user linkage.
    op.execute("DELETE FROM face_enrollments")

    op.add_column("face_enrollments", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "face_enrollments_user_id_fkey",
        "face_enrollments",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_face_enrollments_user_id",
        "face_enrollments",
        ["user_id"],
        unique=False,
    )
    op.alter_column("face_enrollments", "user_id", nullable=False)
    op.drop_column("face_enrollments", "name")

    op.add_column(
        "face_recognition_logs",
        sa.Column("matched_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "face_recognition_logs_matched_user_id_fkey",
        "face_recognition_logs",
        "users",
        ["matched_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_face_recognition_logs_matched_user_id",
        "face_recognition_logs",
        ["matched_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_face_recognition_logs_matched_user_id",
        table_name="face_recognition_logs",
    )
    op.drop_constraint(
        "face_recognition_logs_matched_user_id_fkey",
        "face_recognition_logs",
        type_="foreignkey",
    )
    op.drop_column("face_recognition_logs", "matched_user_id")

    op.add_column(
        "face_enrollments",
        sa.Column("name", sa.String(length=255), nullable=False, server_default="unknown"),
    )
    op.alter_column("face_enrollments", "name", server_default=None)
    op.drop_index("ix_face_enrollments_user_id", table_name="face_enrollments")
    op.drop_constraint(
        "face_enrollments_user_id_fkey",
        "face_enrollments",
        type_="foreignkey",
    )
    op.drop_column("face_enrollments", "user_id")
