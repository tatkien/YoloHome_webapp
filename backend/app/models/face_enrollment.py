import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

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
    bbox = sa.Column(sa.JSON, nullable=True)
    # Optionally scope to a specific door-camera device
    device_id = sa.Column(
        sa.Integer, sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
