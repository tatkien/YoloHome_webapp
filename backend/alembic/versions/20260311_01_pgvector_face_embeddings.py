"""Enable pgvector, migrate feature_vector JSON → vector(512), add HNSW index

Revision ID: 20260311_01
Revises: 20260310_02
Create Date: 2026-03-11 00:00:00.000000
"""

from alembic import op

revision = "20260311_01"
down_revision = "20260310_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable the pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Migrate face_enrollments.feature_vector: JSON → vector(512)
    op.execute("""
        ALTER TABLE face_enrollments
        ALTER COLUMN feature_vector TYPE vector(512)
        USING feature_vector::text::vector
    """)

    # Migrate face_recognition_logs.feature_vector: JSON → vector(512)
    op.execute("""
        ALTER TABLE face_recognition_logs
        ALTER COLUMN feature_vector TYPE vector(512)
        USING feature_vector::text::vector
    """)

    # HNSW index for fast approximate nearest-neighbour cosine similarity search
    op.execute("""
        CREATE INDEX face_enrollments_vector_hnsw
        ON face_enrollments
        USING hnsw (feature_vector vector_cosine_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS face_enrollments_vector_hnsw")

    op.execute("""
        ALTER TABLE face_enrollments
        ALTER COLUMN feature_vector TYPE json
        USING to_json(ARRAY(SELECT unnest(feature_vector::real[])))
    """)

    op.execute("""
        ALTER TABLE face_recognition_logs
        ALTER COLUMN feature_vector TYPE json
        USING to_json(ARRAY(SELECT unnest(feature_vector::real[])))
    """)
