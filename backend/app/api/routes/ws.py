import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.realtime.websocket_manager import realtime_manager

router = APIRouter(tags=["ws"])

async def authenticate_ws_user(token: str) -> User:
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token required")
    
    # Tự mở đóng DB context
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
# ENDPOINT CHO USER
# ==========================================
@router.websocket("/ws")
async def user_global_stream(
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    # 1. Xác thực và lấy User
    user = await authenticate_ws_user(token)

    # 2. Chấp nhận kết nối và đưa vào Manager
    await realtime_manager.connect_user(user.id, websocket)
    await websocket.send_json({"type": "connection.ready", "user_id": user.id})

    # 3. Vòng lặp giữ kết nối
    try:
        while True:
            # Nhận tin nhắn từ Client
            data = await websocket.receive_json()
            
            # Xử lý Ping/Pong
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                
            # Gửi lệnh xuống (nếu có)
            elif data.get("action") == "toggle_device":
                device_id = data.get("device_id")
                
    except WebSocketDisconnect:
        realtime_manager.disconnect_user(user.id, websocket)