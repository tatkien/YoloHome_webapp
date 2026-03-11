from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Face enrollment  (register a known face by storing its feature vector)
# ---------------------------------------------------------------------------

class FaceEnrollmentCreate(BaseModel):
    name: str                       # whose face this is, e.g. "Alice"
    feature_vector: list[float]     # extracted by the AI model before sending
    device_id: int | None = None    # optional: scope to one door-camera device


class FaceEnrollmentRead(BaseModel):
    id: int
    name: str
    feature_vector: list[float]
    device_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Face recognition log  (every recognition attempt with its result)
# ---------------------------------------------------------------------------

class FaceRecognitionLogRead(BaseModel):
    id: int
    device_id: int | None = None
    image_path: str | None = None
    feature_vector: list[float] | None = None
    matched_enrollment_id: int | None = None
    confidence: float | None = None
    # pending: AI not run yet | recognized: match found | unknown: no match
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
