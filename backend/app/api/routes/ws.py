import sqlalchemy as sa
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import logging

from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.realtime.websocket_manager import realtime_manager
from app.service.voice_listener import get_voice_ws_processor

router = APIRouter(tags=["ws"])
logger = logging.getLogger(__name__)

WS_IDLE_TIMEOUT_SECONDS = 60


async def authenticate_ws_user(token: str) -> User:
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token required")
    
    # Open/close DB context locally in this helper
    async with AsyncSessionLocal() as db:
        try:
            payload = decode_access_token(token)
            result = await db.execute(sa.select(User).where(User.id == int(payload["sub"])))
            user = result.scalar_one_or_none()
            
            if user is None or not user.is_active:
                raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return user
        except Exception:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")

# ==========================================
# USER WEBSOCKET ENDPOINT
# ==========================================
@router.websocket("/ws")
async def user_global_stream(
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    # 1. Authenticate and resolve user
    user = await authenticate_ws_user(token)

    # 2. Accept connection and register in manager
    await realtime_manager.connect_user(user.id, websocket)
    await websocket.send_json({"type": "connection.ready", "user_id": user.id})

    # 3. Keep connection alive with idle timeout
    try:
        while True:
            # Wait for message with 60s timeout — client must ping every 30s
            data = await asyncio.wait_for(
                websocket.receive_json(), timeout=WS_IDLE_TIMEOUT_SECONDS
            )

            # Handle ping/pong
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if data.get("type") == "voice_start":
                logger.info("[VOICE][user:%s] WS voice_start", user.id)
                try:
                    await get_voice_ws_processor().start_session(user.id)
                except RuntimeError as exc:
                    await realtime_manager.send_to_user(user.id, {
                        "event": "voice_error",
                        "data": {"message": str(exc)},
                    })
                continue

            if data.get("type") == "voice_stop":
                logger.info("[VOICE][user:%s] WS voice_stop", user.id)
                try:
                    await get_voice_ws_processor().stop_session(user.id)
                except RuntimeError:
                    pass
                continue

            if data.get("type") == "voice_chunk":
                logger.info("[VOICE][user:%s] WS voice_chunk", user.id)
                audio_base64 = data.get("audio_base64")
                mime_type = data.get("mime_type")
                if not audio_base64:
                    await realtime_manager.send_to_user(user.id, {
                        "event": "voice_error",
                        "data": {"message": "Missing audio chunk data."},
                    })
                    continue
                try:
                    await get_voice_ws_processor().process_chunk(user.id, audio_base64, mime_type)
                except RuntimeError as exc:
                    await realtime_manager.send_to_user(user.id, {
                        "event": "voice_error",
                        "data": {"message": str(exc)},
                    })
                continue

    except asyncio.TimeoutError:
        # Client didn't send anything for 60 seconds
        await websocket.close(code=1000, reason="Idle timeout")
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await get_voice_ws_processor().stop_session(user.id)
        except RuntimeError:
            pass
        realtime_manager.disconnect_user(user.id, websocket)