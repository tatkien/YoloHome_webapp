"""Re-add persons and face_enrollments tables, restore matched_person_id in face_recognition_logs.

Revision ID: 20260309_04
Revises: 20260309_03
Create Date: 2026-03-10 01:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260309_04"
down_revision = "20260309_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- persons ---
    op.create_table(
        "persons",
        sa.Column("id", sa.Integer, primary_key=True),
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
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
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
        sa.Column("id", sa.Integer, primary_key=True),
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

    # --- restore matched_person_id column ---
    op.add_column(
        "face_recognition_logs",
        sa.Column(
            "matched_person_id",
            sa.Integer,
            sa.ForeignKey("persons.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("face_recognition_logs", "matched_person_id")
    op.drop_table("face_enrollments")
    op.drop_table("persons")
