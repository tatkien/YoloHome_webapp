import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np
import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.core.config import settings
from app.core.face_service import FaceService, get_face_service
from app.db.db_utils import reset_sequence_to_min_gap
from app.db.session import get_db
from app.models.device import Device, DeviceTypeEnum
from app.models.face_enrollment import FaceEnrollment
from app.models.face_recognition_log import FaceRecognitionLog
from app.models.user import User
from app.schemas.face import (
    FaceEnrollmentRead,
    FaceRecognitionLogRead,
    FaceRecognizeResult,
)

logger = logging.getLogger(__name__)

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


def _user_display_name(full_name: str | None, username: str | None) -> str | None:
    if full_name and full_name.strip():
        return full_name
    return username


def _vector_to_list(vector: list[float] | tuple[float, ...] | np.ndarray | None) -> list[float] | None:
    if vector is None:
        return None
    return [float(v) for v in vector]


def _image_media_type(path: str) -> str:
    guessed_type, _ = mimetypes.guess_type(path)
    return guessed_type or "application/octet-stream"


def _remove_file_if_exists(path: str | None) -> None:
    if path and os.path.isfile(path):
        os.remove(path)


def _save_enrollment_image(contents: bytes, filename: str | None) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = "jpg"
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    saved_filename = f"{uuid.uuid4().hex}.{ext}"
    image_path = os.path.join(UPLOAD_DIR, saved_filename)
    with open(image_path, "wb") as file_handle:
        file_handle.write(contents)
    return image_path


async def _get_user_or_404(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(sa.select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def _get_camera_or_404(db: AsyncSession, device_id: str) -> Device:
    """Validate that device_id is an existing camera device."""
    result = await db.execute(sa.select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    if device.type != DeviceTypeEnum.CAMERA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device is not a camera",
        )
    return device


# ---------------------------------------------------------------------------
# Camera device endpoint (for frontend auto-detection)
# ---------------------------------------------------------------------------

@router.get("/camera", summary="Get currently available camera device")
async def get_camera_device(
    db: AsyncSession = Depends(get_db),
):
    """Returns the first camera device if one exists, or null."""
    result = await db.execute(
        sa.select(Device).where(Device.type == DeviceTypeEnum.CAMERA).limit(1)
    )
    camera = result.scalar_one_or_none()
    if not camera:
        return {"camera": None}
    return {
        "camera": {
            "id": camera.id,
            "name": camera.name,
            "hardware_id": camera.hardware_id,
        }
    }


# ---------------------------------------------------------------------------
# Enrollment  (register a known face → store its feature vector)
# ---------------------------------------------------------------------------

@router.get("/enrollments", response_model=list[FaceEnrollmentRead])
async def list_enrollments(
    device_id: str | None = None,
    user_id: int | None = None,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = sa.select(FaceEnrollment, User.username, User.full_name).join(
        User, FaceEnrollment.user_id == User.id, isouter=True
    )
    if device_id is not None:
        query = query.where(FaceEnrollment.device_id == device_id)
    if user_id is not None:
        query = query.where(FaceEnrollment.user_id == user_id)
    result = await db.execute(query.order_by(FaceEnrollment.created_at.desc()))

    enrollments: list[FaceEnrollmentRead] = []
    for enrollment, username, full_name in result.all():
        enrollments.append(
            FaceEnrollmentRead(
                id=enrollment.id,
                user_id=enrollment.user_id,
                user_name=_user_display_name(full_name, username),
                feature_vector=_vector_to_list(enrollment.feature_vector) or [],
                image_path=enrollment.image_path,
                bbox=_vector_to_list(enrollment.bbox),
                device_id=enrollment.device_id,
                created_at=enrollment.created_at,
            )
        )
    return enrollments


@router.post(
    "/enrollments/image",
    response_model=FaceEnrollmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a face from an uploaded image",
    description=(
        "Upload a JPEG/PNG/WebP photo. The server detects the face with RetinaFace, "
        "aligns it, extracts the 512-d ArcFace embedding, and stores it for the provided user_id."
    ),
)
async def create_enrollment_from_image(
    image: UploadFile = File(..., description="Photo containing the face to enroll"),
    user_id: int = Form(..., description="ID of the registered user"),
    device_id: str = Form(..., description="Camera device ID (required)"),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
):
    user = await _get_user_or_404(db, user_id)
    await _get_camera_or_404(db, device_id)

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
    bbox, embedding, _, _ = results[0]

    # Anti-spoofing gate: embedding is None when face is classified as spoof
    if embedding is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Spoofed face detected — enrollment rejected",
        )

    image_path = _save_enrollment_image(contents, image.filename)

    # Keep sequence aligned with current gaps right before INSERT to avoid duplicates
    # after a previously reused ID.
    await reset_sequence_to_min_gap(db, "face_enrollments", "face_enrollments_id_seq")

    enrollment = FaceEnrollment(
        user_id=user_id,
        feature_vector=embedding.tolist(),
        image_path=image_path,
        bbox=bbox.tolist(),
        device_id=device_id,
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return FaceEnrollmentRead(
        id=enrollment.id,
        user_id=enrollment.user_id,
        user_name=_user_display_name(user.full_name, user.username),
        feature_vector=_vector_to_list(enrollment.feature_vector) or [],
        image_path=enrollment.image_path,
        bbox=_vector_to_list(enrollment.bbox),
        device_id=enrollment.device_id,
        created_at=enrollment.created_at,
    )


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
    _remove_file_if_exists(enrollment.image_path)
    await db.delete(enrollment)
    await db.commit()


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
        "and matches against enrolled faces using cosine similarity (pgvector). "
        "On recognition success, automatically sends an unlock command to the servo/lock device."
    ),
)
async def recognize_face(
    image: UploadFile = File(..., description="JPEG / PNG / WebP image from the camera"),
    device_id: str = Form(..., description="Camera device ID (required)"),
    db: AsyncSession = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
):
    # --- Validate content type ---
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are accepted",
        )

    # --- Validate camera device ---
    camera_device = await _get_camera_or_404(db, device_id)

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
    bbox, embedding, det_score, anti_spoof_score = results[0]

    # Anti-spoofing gate: if embedding is None the face was classified as spoof
    if embedding is None:
        log = FaceRecognitionLog(
            device_id=device_id,
            image_path=image_path,
            status="Spoof detected",
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return FaceRecognizeResult(
            log_id=log.id,
            status="Spoof detected",
            bbox=bbox.tolist(),
            detection_score=round(float(det_score), 4),
            anti_spoof_score=round(float(anti_spoof_score), 4),
        )

    # --- Gate on detection quality ---
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
            anti_spoof_score=round(float(anti_spoof_score), 4),
        )

    embedding_list = embedding.tolist()

    # --- Match against enrolled faces via pgvector cosine distance ---
    matched_enrollment_id = None
    matched_user_id = None
    matched_user_name = None
    confidence = None
    rec_status = "unknown"

    cosine_dist_col = FaceEnrollment.feature_vector.cosine_distance(embedding_list)

    match_query = sa.select(
        FaceEnrollment.id,
        FaceEnrollment.user_id,
        User.username,
        User.full_name,
        cosine_dist_col.label("distance"),
    ).join(User, FaceEnrollment.user_id == User.id, isouter=True)
    # Scope to enrollments for this camera device (or unscoped)
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
            matched_user_id = best_match.user_id
            matched_user_name = _user_display_name(best_match.full_name, best_match.username)
            confidence = round(similarity, 4)
            rec_status = "recognized"
        else:
            confidence = round(similarity, 4)

    # --- Save recognition log ---
    log = FaceRecognitionLog(
        device_id=device_id,
        image_path=image_path,
        matched_enrollment_id=matched_enrollment_id,
        matched_user_id=matched_user_id,
        confidence=confidence,
        status=rec_status,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    # --- Auto-unlock door on recognition ---
    door_unlocked = False
    if rec_status == "recognized" and camera_device.hardware_id:
        try:
            lock_result = await db.execute(
                sa.select(Device).where(
                    Device.hardware_id == camera_device.hardware_id,
                    Device.type == DeviceTypeEnum.LOCK,
                )
            )
            lock_device = lock_result.scalar_one_or_none()
            if lock_device:
                from app.service.mqtt import mqtt_service
                await mqtt_service.publish_command(
                    hardware_id=lock_device.hardware_id,
                    pin=lock_device.pin,
                    is_on=True,
                    value=float(settings.SERVO_OPEN_ANGLE),  # 90
                )
                door_unlocked = True
                logger.info(
                    f"[Face] Auto-unlock: sent servo open command (angle={settings.SERVO_OPEN_ANGLE}) "
                    f"for lock device {lock_device.id} on hardware {lock_device.hardware_id}"
                )
        except Exception:
            logger.exception("[Face] Failed to send auto-unlock command")

    return FaceRecognizeResult(
        log_id=log.id,
        status=rec_status,
        confidence=confidence,
        matched_enrollment_id=matched_enrollment_id,
        matched_user_id=matched_user_id,
        matched_user_name=matched_user_name,
        bbox=bbox.tolist(),
        detection_score=round(float(det_score), 4),
        anti_spoof_score=round(float(anti_spoof_score), 4),
        door_unlocked=door_unlocked,
    )


@router.get("/logs", response_model=list[FaceRecognitionLogRead], summary="List recognition log entries")
async def list_recognition_logs(
    device_id: str | None = None,
    limit: int = 100,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = sa.select(FaceRecognitionLog, User.username, User.full_name).join(
        User, FaceRecognitionLog.matched_user_id == User.id, isouter=True
    )
    if device_id is not None:
        query = query.where(FaceRecognitionLog.device_id == device_id)
    result = await db.execute(
        query.order_by(FaceRecognitionLog.created_at.desc()).limit(limit)
    )

    logs: list[FaceRecognitionLogRead] = []
    for log, username, full_name in result.all():
        logs.append(
            FaceRecognitionLogRead(
                id=log.id,
                device_id=log.device_id,
                image_path=log.image_path,
                matched_enrollment_id=log.matched_enrollment_id,
                matched_user_id=log.matched_user_id,
                matched_user_name=_user_display_name(full_name, username),
                confidence=log.confidence,
                status=log.status,
                created_at=log.created_at,
            )
        )
    return logs


@router.get("/logs/{log_id}/image", summary="Return the stored image for a recognition log")
async def get_recognition_log_image(
    log_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        sa.select(FaceRecognitionLog.image_path).where(FaceRecognitionLog.id == log_id)
    )
    image_path = result.scalar_one_or_none()
    if image_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recognition log not found")
    if not os.path.isfile(image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recognition log image not found")

    return FileResponse(
        path=image_path,
        media_type=_image_media_type(image_path),
        filename=os.path.basename(image_path),
    )
    
@router.get("/enrollments/{enrollment_id}/image", summary="Return the stored image for a face enrollment")
async def get_face_enrollment_image(
    enrollment_id: int,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        sa.select(FaceEnrollment.image_path).where(FaceEnrollment.id == enrollment_id)
    )
    image_path = result.scalar_one_or_none()
    if image_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Face enrollment image not found")
    if not os.path.isfile(image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Face enrollment image not found")

    return FileResponse(
        path=image_path,
        media_type=_image_media_type(image_path),
        filename=os.path.basename(image_path),
    )