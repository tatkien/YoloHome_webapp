import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from app.db.session import Base
from app.models.face_enrollment import VECTOR_DIM


class FaceRecognitionLog(Base):
    __tablename__ = "face_recognition_logs"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    # Camera device that submitted the image
    device_id = sa.Column(
        sa.Integer, sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Path to the saved image file on disk
    image_path = sa.Column(sa.String(512), nullable=True)
    # ArcFace 512-d feature vector extracted from submitted image (null until model runs)
    feature_vector = sa.Column(Vector(VECTOR_DIM), nullable=True)
    # Enrollment record matched by the AI model (null = unknown / pending)
    matched_enrollment_id = sa.Column(
        sa.Integer, sa.ForeignKey("face_enrollments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # User matched by the AI model (denormalized for faster UI/API reads)
    matched_user_id = sa.Column(
        sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Similarity confidence score 0.0 - 1.0 (null until model is integrated)
    confidence = sa.Column(sa.Float, nullable=True)
    # pending: AI not run yet | recognized: match found | unknown: no match
    status = sa.Column(
        sa.String(32), nullable=False, default="pending", server_default="pending"
    )
    created_at = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
