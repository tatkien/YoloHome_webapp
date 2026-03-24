import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.device import Device, HardwareNode
from app.models.user import User
from app.realtime.websocket_manager import realtime_manager

router = APIRouter(tags=["ws"])

async def _resolve_websocket_user(token: str | None, db: AsyncSession) -> User:
    """Xác thực người dùng qua Token trước khi cho phép mở WebSocket"""
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token is required")

    try:
        payload = decode_access_token(token)
        result = await db.execute(sa.select(User).where(User.id == int(payload["sub"])))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
        return user
    except Exception:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")

# ==========================================
# ENDPOINT 1: LẮNG NGHE CẢM BIẾN
# ==========================================
@router.websocket("/ws/hardware/{hardware_id}")
async def hardware_stream(
    websocket: WebSocket,
    hardware_id: str,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    await _resolve_websocket_user(token, db)

    # 1. Kiểm tra mạch có tồn tại không
    result = await db.execute(sa.select(HardwareNode).where(HardwareNode.id == hardware_id))
    if result.scalar_one_or_none() is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Hardware not found")

    # 2. Đăng ký kết nối vào Manager
    await realtime_manager.connect_hardware(hardware_id, websocket)
    await websocket.send_json({"type": "subscription.ready", "hardware_id": hardware_id})

    # 3. Giữ kết nối và phản hồi Ping/Pong để tránh rớt mạng
    try:
        while True:
            message = await websocket.receive_text()
            if message.lower() == "ping":
                await websocket.send_json({"type": "pong", "hardware_id": hardware_id})
    except WebSocketDisconnect:
        realtime_manager.disconnect_hardware(hardware_id, websocket)


# ==========================================
# ENDPOINT 2: LẮNG NGHE PHẢN HỒI TRẠNG THÁI (Theo Từng Thiết Bị)
# ==========================================
@router.websocket("/ws/devices/{device_id}")
async def device_stream(
    websocket: WebSocket,
    device_id: str,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    await _resolve_websocket_user(token, db)

    # 1. Kiểm tra thiết bị có tồn tại không
    result = await db.execute(sa.select(Device).where(Device.id == device_id))
    if result.scalar_one_or_none() is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Device not found")

    # 2. Đăng ký kết nối vào Manager
    await realtime_manager.connect_device(device_id, websocket)
    await websocket.send_json({"type": "subscription.ready", "device_id": device_id})

    # 3. Giữ kết nối
    try:
        while True:
            message = await websocket.receive_text()
            if message.lower() == "ping":
                await websocket.send_json({"type": "pong", "device_id": device_id})
    except WebSocketDisconnect:
        realtime_manager.disconnect_device(device_id, websocket)