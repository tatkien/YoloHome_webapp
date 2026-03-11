import os
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.core.security import verify_secret
from app.db.session import get_db
from app.models.device import Device
from app.models.face_enrollment import FaceEnrollment
from app.models.face_recognition_log import FaceRecognitionLog
from app.models.user import User
from app.schemas.face import FaceEnrollmentCreate, FaceEnrollmentRead, FaceRecognitionLogRead

UPLOAD_DIR = "/app/uploads/face_recognition"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

router = APIRouter(prefix="/face", tags=["face"])


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
    summary="Register a face by storing its feature vector",
    description=(
        "The AI model extracts the feature vector from the face image on the client side "
        "and submits it here. The backend stores it so future recognitions can be matched."
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


# ---------------------------------------------------------------------------
# Recognition  (camera submits image → save + create log)
# ---------------------------------------------------------------------------

@router.post(
    "/recognize",
    response_model=FaceRecognitionLogRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a camera image for face recognition",
    description=(
        "Saves the image to disk and creates a recognition log entry with status 'pending'. "
        "Once the AI model is integrated it will populate feature_vector, matched_enrollment_id, "
        "confidence, and update the status to 'recognized' or 'unknown'."
    ),
)
async def recognize_face(
    image: UploadFile = File(..., description="JPEG / PNG / WebP image from the camera"),
    device_id: int | None = Form(default=None, description="ID of the submitting device"),
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    db: AsyncSession = Depends(get_db),
):
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are accepted",
        )

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

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = "jpg"
    if image.filename and "." in image.filename:
        ext = image.filename.rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    image_path = os.path.join(UPLOAD_DIR, filename)

    contents = await image.read()
    with open(image_path, "wb") as f:
        f.write(contents)

    log = FaceRecognitionLog(
        device_id=device_id,
        image_path=image_path,
        status="pending",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


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
