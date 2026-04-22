import sqlalchemy as sa
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.realtime.websocket_manager import realtime_manager

router = APIRouter(tags=["ws"])

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

    except asyncio.TimeoutError:
        # Client didn't send anything for 60 seconds
        await websocket.close(code=1000, reason="Idle timeout")
    except WebSocketDisconnect:
        pass
    finally:
        realtime_manager.disconnect_user(user.id, websocket)

@router.get("/docs-websocket-info")
async def websocket_documentation_only():
    """
    ### NOTE: THIS IS A DOCUMENTATION-ONLY ENDPOINT
    **Do not click "Execute"; this endpoint does not return live data.**

    The system uses one shared stream per user. Connection guide:

    ---
    ### 1. Open connection
    Device/sensor events are delivered through this single URL.
    * **URL:** `ws://{{host}}/api/v1/ws?token={{your_jwt_token}}`

    ---
    ### 2. Message protocol (JSON)
    * **Server -> Client (Handshake successful):** `{"type": "connection.ready", "user_id": 1}`
    * **Client -> Server (Keepalive):** Send `{"type": "ping"}` every 30s to receive `{"type": "pong"}`.
    * **Idle timeout:** 60 seconds without any message will close the connection.

    ---
    ### 3. Incoming payload shape
    Frontend uses the `"event"` field to render updates.

    **Sensor update event:**
    ```json
    {
      "event": "sensor_update",
      "hardware_id": "MOCK_BOARD",
      "data": { "temp": 28, "humi": 70 }
    }
    ```
    **State update event (ON/OFF):**
    ```json
    {
      "event": "device_update",
      "hardware_id": "MOCK_BOARD",
      "device_id": "uuid-cua-thiet-bi",
      "data": { "is_on": true, "value": 1023 }
    }
    ```
    """
    return {"detail": "This is a documentation page, not a live endpoint."}