from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Face enrollment  (register a known face by storing its feature vector)
# ---------------------------------------------------------------------------
class FaceEnrollmentRead(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    feature_vector: list[float]
    device_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Face recognition log  (every recognition attempt with its result)
# ---------------------------------------------------------------------------

class FaceRecognitionLogRead(BaseModel):
    id: int
    device_id: str | None = None
    image_path: str | None = None
    feature_vector: list[float] | None = None
    matched_enrollment_id: int | None = None
    matched_user_id: int | None = None
    matched_user_name: str | None = None
    confidence: float | None = None
    # pending: AI not run yet | recognized: match found | unknown: no match
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FaceRecognizeResult(BaseModel):
    """Response for the /recognize endpoint after AI inference."""
    log_id: int
    status: str                                 # "recognized" | "unknown"
    confidence: float | None = None
    matched_enrollment_id: int | None = None
    matched_user_id: int | None = None
    matched_user_name: str | None = None
    bbox: list[float] | None = None             # [x1, y1, x2, y2]
    detection_score: float | None = None

