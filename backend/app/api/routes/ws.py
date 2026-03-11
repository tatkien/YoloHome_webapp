import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.device import Device
from app.models.feed import Feed
from app.models.user import User
from app.realtime.manager import realtime_manager

router = APIRouter(tags=["ws"])


async def _resolve_websocket_user(token: str | None, db: AsyncSession) -> User:
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token is required")

    payload = decode_access_token(token)
    result = await db.execute(sa.select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid authentication token",
        )
    return user


@router.websocket("/ws/feeds/{feed_id}")
async def feed_stream(
    websocket: WebSocket,
    feed_id: int,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    await _resolve_websocket_user(token, db)
    feed_result = await db.execute(sa.select(Feed).where(Feed.id == feed_id))
    if feed_result.scalar_one_or_none() is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Feed not found")

    await realtime_manager.connect_feed(feed_id, websocket)
    await websocket.send_json({"type": "subscription.ready", "feed_id": feed_id})
    try:
        while True:
            message = await websocket.receive_text()
            if message.lower() == "ping":
                await websocket.send_json({"type": "pong", "feed_id": feed_id})
    except WebSocketDisconnect:
        realtime_manager.disconnect_feed(feed_id, websocket)


@router.websocket("/ws/devices/{device_id}")
async def device_stream(
    websocket: WebSocket,
    device_id: int,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    await _resolve_websocket_user(token, db)
    device_result = await db.execute(sa.select(Device).where(Device.id == device_id))
    if device_result.scalar_one_or_none() is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Device not found")

    await realtime_manager.connect_device(device_id, websocket)
    await websocket.send_json({"type": "subscription.ready", "device_id": device_id})
    try:
        while True:
            message = await websocket.receive_text()
            if message.lower() == "ping":
                await websocket.send_json({"type": "pong", "device_id": device_id})
    except WebSocketDisconnect:
        realtime_manager.disconnect_device(device_id, websocket)