"""Add face recognition tables (persons, face_enrollments, face_recognition_logs).

Revision ID: 20260309_02
Revises: 20260309_01
Create Date: 2026-03-09 01:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260309_02"
down_revision = "20260309_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- persons ---
    op.create_table(
        "persons",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "device_id",
            sa.Integer,
            sa.ForeignKey("devices.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_by_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            default=True,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- face_enrollments ---
    op.create_table(
        "face_enrollments",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "person_id",
            sa.Integer,
            sa.ForeignKey("persons.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("feature_vector", sa.JSON, nullable=False),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- face_recognition_logs ---
    op.create_table(
        "face_recognition_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "device_id",
            sa.Integer,
            sa.ForeignKey("devices.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("image_path", sa.String(512), nullable=True),
        sa.Column("feature_vector", sa.JSON, nullable=True),
        sa.Column(
            "matched_person_id",
            sa.Integer,
            sa.ForeignKey("persons.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            default="pending",
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("face_recognition_logs")
    op.drop_table("face_enrollments")
    op.drop_table("persons")
