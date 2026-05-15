"""Add HNSW vector index and upgrade Array type for face enrollment table

Revision ID: e1553abf9d21
Revises: b2e8f3a7c901
Create Date: 2026-04-26 00:47:51.169900

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1553abf9d21'
down_revision: Union[str, Sequence[str], None] = 'b2e8f3a7c901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Convert face_enrollments.bbox from JSON to double precision[].
    op.execute("ALTER TABLE face_enrollments ADD COLUMN bbox_tmp double precision[]")
    op.execute(
        """
        UPDATE face_enrollments
        SET bbox_tmp = ARRAY(
            SELECT json_array_elements_text(bbox)::double precision
        )
        WHERE bbox IS NOT NULL
        """
    )
    op.execute("ALTER TABLE face_enrollments DROP COLUMN bbox")
    op.execute("ALTER TABLE face_enrollments RENAME COLUMN bbox_tmp TO bbox")

    op.create_index(
        'ix_face_enrollments_feature_vector_hnsw',
        'face_enrollments',
        ['feature_vector'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_with={'ef_construction': 64, 'm': 16},
        postgresql_ops={'feature_vector': 'vector_cosine_ops'},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'ix_face_enrollments_feature_vector_hnsw',
        table_name='face_enrollments',
        postgresql_using='hnsw',
        postgresql_with={'ef_construction': 64, 'm': 16},
        postgresql_ops={'feature_vector': 'vector_cosine_ops'},
    )

    # Convert face_enrollments.bbox from double precision[] back to json via a temporary column.
    op.execute("ALTER TABLE face_enrollments ADD COLUMN bbox_tmp json")
    op.execute(
        """
        UPDATE face_enrollments
        SET bbox_tmp = array_to_json(bbox)
        WHERE bbox IS NOT NULL
        """
    )
    op.execute("ALTER TABLE face_enrollments DROP COLUMN bbox")
    op.execute("ALTER TABLE face_enrollments RENAME COLUMN bbox_tmp TO bbox")
