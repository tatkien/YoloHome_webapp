import re
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.core.security import verify_secret
from app.db.session import get_db
from app.models.device import Device
from app.models.feed import Feed
from app.models.feed_value import FeedValue
from app.models.user import User
from app.realtime.manager import realtime_manager
from app.schemas.feed import FeedCreate, FeedRead, FeedValueCreate, FeedValueRead

router = APIRouter(prefix="/feeds", tags=["feeds"])


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


async def _get_feed_or_404(db: AsyncSession, feed_id: int) -> Feed:
    result = await db.execute(sa.select(Feed).where(Feed.id == feed_id))
    feed = result.scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    return feed


async def _get_device_or_404(db: AsyncSession, device_id: int) -> Device:
    result = await db.execute(sa.select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


async def _get_owned_feed(db: AsyncSession, feed_id: int, user: User) -> Feed:
    """Fetch a feed and verify the requesting user owns its parent device."""
    feed = await _get_feed_or_404(db, feed_id)
    device = await _get_device_or_404(db, feed.device_id)
    if device.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return feed


async def _create_feed_value(
    db: AsyncSession,
    feed: Feed,
    value: str,
    source: str,
) -> FeedValue:
    created_at = datetime.now(timezone.utc)
    feed_value = FeedValue(feed_id=feed.id, value=value, source=source, created_at=created_at)
    feed.last_value = value
    feed.last_value_at = created_at
    db.add(feed_value)
    await db.commit()
    await db.refresh(feed_value)

    message = FeedValueRead.model_validate(feed_value).model_dump(mode="json")
    await realtime_manager.broadcast_feed_value(
        feed.id,
        {"type": "feed.value.created", "feed_id": feed.id, "value": message},
    )
    await realtime_manager.broadcast_device_event(
        feed.device_id,
        {
            "type": "device.telemetry.received",
            "device_id": feed.device_id,
            "feed_id": feed.id,
            "value": message,
        },
    )
    return feed_value


@router.get("/", response_model=list[FeedRead])
async def list_feeds(
    device_id: int | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all feeds, optionally filtered by device."""
    query = sa.select(Feed)
    if device_id is not None:
        query = query.where(Feed.device_id == device_id)
    result = await db.execute(query.order_by(Feed.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=FeedRead, status_code=status.HTTP_201_CREATED)
async def create_feed(
    payload: FeedCreate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    device = await _get_device_or_404(db, payload.device_id)
    feed_key = _slugify(payload.key or payload.name)
    if not feed_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feed key cannot be empty",
        )

    existing_feed = await db.execute(
        sa.select(Feed).where(Feed.device_id == payload.device_id, Feed.key == feed_key)
    )
    if existing_feed.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feed key is already in use for this device",
        )

    feed = Feed(
        device_id=payload.device_id,
        name=payload.name,
        key=feed_key,
        description=payload.description,
        data_type=payload.data_type,
    )
    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    return feed


@router.get("/{feed_id}", response_model=FeedRead)
async def read_feed(
    feed_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_feed_or_404(db, feed_id)


@router.get("/{feed_id}/values", response_model=list[FeedValueRead])
async def list_feed_values(
    feed_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    since: datetime | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_feed_or_404(db, feed_id)
    query = sa.select(FeedValue).where(FeedValue.feed_id == feed_id)
    if since is not None:
        query = query.where(FeedValue.created_at >= since)
    result = await db.execute(query.order_by(FeedValue.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.post("/{feed_id}/values", response_model=FeedValueRead, status_code=status.HTTP_201_CREATED)
async def publish_feed_value(
    feed_id: int,
    payload: FeedValueCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    feed = await _get_feed_or_404(db, feed_id)
    if feed.data_type == "number":
        try:
            float(payload.value)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Feed expects a numeric value")
    return await _create_feed_value(db, feed, payload.value, source="user")


@router.post("/{feed_id}/ingest", response_model=FeedValueRead, status_code=status.HTTP_201_CREATED)
async def ingest_feed_value(
    feed_id: int,
    payload: FeedValueCreate,
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    db: AsyncSession = Depends(get_db),
):
    if not x_device_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Device-Key header is required",
        )

    feed = await _get_feed_or_404(db, feed_id)
    device = await _get_device_or_404(db, feed.device_id)
    if not device.is_active or not verify_secret(x_device_key, device.key_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credentials",
        )

    device.last_seen_at = datetime.now(timezone.utc)
    if feed.data_type == "number":
        try:
            float(payload.value)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Feed expects a numeric value")
    return await _create_feed_value(db, feed, payload.value, source="device")