"""Restructure face_enrollments: drop person_id FK, add name+device_id; update face_recognition_logs

Revision ID: 20260309_05
Revises: 20260309_04
Create Date: 2026-03-09 05:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260309_05"
down_revision = "20260309_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop face_recognition_logs.matched_person_id FK + column
    op.drop_constraint("face_recognition_logs_matched_person_id_fkey", "face_recognition_logs", type_="foreignkey")
    op.drop_column("face_recognition_logs", "matched_person_id")

    # 2. Drop face_enrollments (had person_id FK to persons)
    op.drop_table("face_enrollments")

    # 3. Drop persons
    op.drop_table("persons")

    # 4. Re-create face_enrollments without person_id, with name + device_id
    op.create_table(
        "face_enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("feature_vector", sa.JSON(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 5. Add matched_enrollment_id to face_recognition_logs
    op.add_column(
        "face_recognition_logs",
        sa.Column("matched_enrollment_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "face_recognition_logs_matched_enrollment_id_fkey",
        "face_recognition_logs",
        "face_enrollments",
        ["matched_enrollment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Reverse: remove matched_enrollment_id FK + column
    op.drop_constraint(
        "face_recognition_logs_matched_enrollment_id_fkey",
        "face_recognition_logs",
        type_="foreignkey",
    )
    op.drop_column("face_recognition_logs", "matched_enrollment_id")

    # Drop new face_enrollments
    op.drop_table("face_enrollments")

    # Recreate persons
    op.create_table(
        "persons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Recreate old face_enrollments with person_id
    op.create_table(
        "face_enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("feature_vector", sa.JSON(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Restore matched_person_id
    op.add_column(
        "face_recognition_logs",
        sa.Column("matched_person_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "face_recognition_logs_matched_person_id_fkey",
        "face_recognition_logs",
        "persons",
        ["matched_person_id"],
        ["id"],
        ondelete="SET NULL",
    )
