import os
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np
import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.core.config import settings
from app.core.face_service import FaceService, get_face_service
from app.core.security import verify_secret
from app.db.db_utils import reset_sequence_to_min_gap
from app.db.session import get_db
from app.models.device import Device
from app.models.face_enrollment import FaceEnrollment
from app.models.face_recognition_log import FaceRecognitionLog
from app.models.user import User
from app.schemas.face import (
    FaceEnrollmentCreate,
    FaceEnrollmentRead,
    FaceRecognitionLogRead,
    FaceRecognizeResult,
)

UPLOAD_DIR = "/app/uploads/face_recognition"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

router = APIRouter(prefix="/face", tags=["face"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_upload(contents: bytes | bytearray) -> np.ndarray:
    """Decode raw image bytes into a BGR OpenCV image."""
    arr = np.frombuffer(contents, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not decode image",
        )
    return image


# ---------------------------------------------------------------------------
# Enrollment  (register a known face → store its feature vector)
# ---------------------------------------------------------------------------

@router.get("/enrollments", response_model=list[FaceEnrollmentRead])
async def list_enrollments(
    device_id: int | None = None,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = sa.select(FaceEnrollment)
    if device_id is not None:
        query = query.where(FaceEnrollment.device_id == device_id)
    result = await db.execute(query.order_by(FaceEnrollment.created_at.desc()))
    return result.scalars().all()


@router.post(
    "/enrollments",
    response_model=FaceEnrollmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a face by storing its feature vector (JSON)",
    description=(
        "Accepts a pre-extracted 512-d feature vector. "
        "Use POST /enrollments/image to let the server extract the vector from an image."
    ),
)
async def create_enrollment(
    payload: FaceEnrollmentCreate,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    enrollment = FaceEnrollment(
        name=payload.name,
        feature_vector=payload.feature_vector,
        device_id=payload.device_id,
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


@router.post(
    "/enrollments/image",
    response_model=FaceEnrollmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a face from an uploaded image",
    description=(
        "Upload a JPEG/PNG/WebP photo. The server detects the face with RetinaFace, "
        "aligns it, extracts the 512-d ArcFace embedding, and stores the enrollment."
    ),
)
async def create_enrollment_from_image(
    image: UploadFile = File(..., description="Photo containing the face to enroll"),
    name: str = Form(..., description="Name of the person"),
    device_id: int | None = Form(default=None, description="Optional device scope"),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
):
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are accepted",
        )

    contents = await image.read()
    img_bgr = _decode_upload(contents)

    results = face_service.detect_and_embed(img_bgr)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No face detected in the image",
        )

    # Use the highest-confidence face
    bbox, embedding, score = results[0]

    enrollment = FaceEnrollment(
        name=name,
        feature_vector=embedding.tolist(),
        device_id=device_id,
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


@router.delete("/enrollments/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_enrollment(
    enrollment_id: int,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        sa.select(FaceEnrollment).where(FaceEnrollment.id == enrollment_id)
    )
    enrollment = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    await db.delete(enrollment)
    await db.commit()
    await reset_sequence_to_min_gap(db, "face_enrollments", "face_enrollments_id_seq")


# ---------------------------------------------------------------------------
# Recognition  (camera submits image → detect → embed → match → log)
# ---------------------------------------------------------------------------

@router.post(
    "/recognize",
    response_model=FaceRecognizeResult,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a camera image for face recognition",
    description=(
        "Runs RetinaFace detection, aligns the face, extracts the ArcFace embedding, "
        "and matches against enrolled faces using cosine similarity (pgvector)."
    ),
)
async def recognize_face(
    image: UploadFile = File(..., description="JPEG / PNG / WebP image from the camera"),
    device_id: int | None = Form(default=None, description="ID of the submitting device"),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    db: AsyncSession = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
):
    # --- Validate content type ---
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are accepted",
        )

    # --- Authenticate device (if provided) ---
    if device_id is not None:
        if not x_device_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-Device-Key header is required when device_id is provided",
            )
        result = await db.execute(sa.select(Device).where(Device.id == device_id))
        device = result.scalar_one_or_none()
        if device is None or not device.is_active or not verify_secret(x_device_key, device.key_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid device credentials",
            )
        device.last_seen_at = datetime.now(timezone.utc)

    # --- Save image to disk ---
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = "jpg"
    if image.filename and "." in image.filename:
        ext = image.filename.rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    image_path = os.path.join(UPLOAD_DIR, filename)

    contents = await image.read()
    raw_bytes = bytes(contents)
    with open(image_path, "wb") as f:
        f.write(raw_bytes)

    # --- Detect + embed ---
    img_bgr = _decode_upload(raw_bytes)
    results = face_service.detect_and_embed(img_bgr)

    if not results:
        # No face found — save log as unknown
        log = FaceRecognitionLog(
            device_id=device_id,
            image_path=image_path,
            status="unknown",
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return FaceRecognizeResult(
            log_id=log.id,
            status="unknown",
        )

    # Use the highest-confidence detection
    bbox, embedding, det_score = results[0]

    # --- Gate on detection quality ---
    # Low detection scores produce unreliable embeddings; skip matching.
    if det_score < settings.FACE_DETECTION_THRESHOLD:
        log = FaceRecognitionLog(
            device_id=device_id,
            image_path=image_path,
            confidence=None,
            status="unknown",
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return FaceRecognizeResult(
            log_id=log.id,
            status="unknown",
            bbox=bbox.tolist(),
            detection_score=round(float(det_score), 4),
        )

    embedding_list = embedding.tolist()

    # --- Match against enrolled faces via pgvector cosine distance ---
    matched_enrollment_id = None
    matched_name = None
    confidence = None
    rec_status = "unknown"

    # pgvector cosine distance: 1 - cosine_similarity
    # So cosine_similarity = 1 - cosine_distance
    cosine_dist_col = FaceEnrollment.feature_vector.cosine_distance(embedding_list)

    match_query = sa.select(
        FaceEnrollment.id,
        FaceEnrollment.name,
        cosine_dist_col.label("distance"),
    )
    if device_id is not None:
        match_query = match_query.where(
            sa.or_(
                FaceEnrollment.device_id == device_id,
                FaceEnrollment.device_id.is_(None),
            )
        )
    match_query = match_query.order_by(cosine_dist_col).limit(1)

    match_result = await db.execute(match_query)
    best_match = match_result.first()

    if best_match is not None:
        similarity = float(1.0 - best_match.distance)
        if similarity >= settings.FACE_MATCH_THRESHOLD:
            matched_enrollment_id = best_match.id
            matched_name = best_match.name
            confidence = round(similarity, 4)
            rec_status = "recognized"
        else:
            confidence = round(similarity, 4)

    # --- Save recognition log ---
    log = FaceRecognitionLog(
        device_id=device_id,
        image_path=image_path,
        feature_vector=embedding_list,
        matched_enrollment_id=matched_enrollment_id,
        confidence=confidence,
        status=rec_status,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    return FaceRecognizeResult(
        log_id=log.id,
        status=rec_status,
        confidence=confidence,
        matched_enrollment_id=matched_enrollment_id,
        matched_name=matched_name,
        bbox=bbox.tolist(),
        detection_score=round(float(det_score), 4),
    )


@router.get("/logs", response_model=list[FaceRecognitionLogRead], summary="List recognition log entries")
async def list_recognition_logs(
    device_id: int | None = None,
    limit: int = 100,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = sa.select(FaceRecognitionLog)
    if device_id is not None:
        query = query.where(FaceRecognitionLog.device_id == device_id)
    result = await db.execute(
        query.order_by(FaceRecognitionLog.created_at.desc()).limit(limit)
    )
    return result.scalars().all()
