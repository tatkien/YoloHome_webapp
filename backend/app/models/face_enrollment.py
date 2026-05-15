import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Index
from app.db.session import Base

VECTOR_DIM = 512  # ArcFace 512-dimensional embedding


class FaceEnrollment(Base):
    __tablename__ = "face_enrollments"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    # Registered user that this face embedding belongs to
    user_id = sa.Column(
        sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ArcFace 512-d feature vector — stored as pgvector for cosine similarity search
    feature_vector = sa.Column(Vector(VECTOR_DIM), nullable=False)
    # Saved source image for the enrollment
    image_path = sa.Column(sa.String(512), nullable=True)
    # Face bbox used when the enrollment image was processed: [x1, y1, x2, y2]
    bbox = sa.Column(ARRAY(sa.Float), nullable=True)
    # Must be linked to a camera device (NOT NULL)
    device_id = sa.Column(
        sa.String(64), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    
    __table_args__ = (
        Index(
            'ix_face_enrollments_feature_vector_hnsw',
            feature_vector,
            postgresql_using='hnsw',
            postgresql_with={"ef_construction": 64, "m": 16},
            postgresql_ops={'feature_vector': 'vector_cosine_ops'}
        ),
    )