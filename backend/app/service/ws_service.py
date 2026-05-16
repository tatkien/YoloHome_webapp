import asyncio
import logging
import sqlalchemy as sa
from fastapi import WebSocket, WebSocketDisconnect, WebSocketException, status
from collections import defaultdict
from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core.logger import logger
from app.core.config import settings
from app.core.voice_stream import voice_streamer

class WsService:
    """
    WebSocket Service: Quản lý kết nối và gửi tin nhắn thời gian thực lên web.
    """
    def __init__(self):
        # Lưu trữ trạng thái kết nối trực tiếp trong Service
        self.active_connections: dict[int, list[WebSocket]] = defaultdict(list)

    def _add_connection(self, user_id: int, websocket: WebSocket):
        if websocket not in self.active_connections[user_id]:
            self.active_connections[user_id].append(websocket)

    def _remove_connection(self, user_id: int, websocket: WebSocket):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                self.active_connections.pop(user_id, None)

    async def connect_user(self, user_id: int, websocket: WebSocket) -> None:
        """Chấp nhận kết nối và đăng ký vào bộ nhớ."""
        subprotocols = websocket.scope.get("subprotocols", [])
        chosen = "token" if "token" in subprotocols else None
        await websocket.accept(subprotocol=chosen)
        self._add_connection(user_id, websocket)

    def disconnect_user(self, user_id: int, websocket: WebSocket) -> None:
        """Hủy đăng ký kết nối."""
        self._remove_connection(user_id, websocket)

    async def send_to_user(self, user_id: int, payload: dict) -> None:
        """Gửi dữ liệu cho tất cả kết nối của 1 user (kèm dọn dẹp kết nối lỗi)."""
        connections = self.active_connections.get(user_id, [])
        if not connections:
            return

        # Tạo bản sao danh sách để tránh lỗi khi remove phần tử trong lúc lặp
        targets = list(connections)
        tasks = [ws.send_json(payload) for ws in targets]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._remove_connection(user_id, targets[i])
                logger.debug(f"[WsService Cleanup] Removed stale connection for user {user_id}")
    
    async def broadcast(self, payload: dict) -> None:
        """Gửi dữ liệu cho tất cả user đang online."""
        user_ids = list(self.active_connections.keys())
        for user_id in user_ids:
            await self.send_to_user(user_id, payload)

    # ==========================================
    # BUSINESS LOGIC
    # ==========================================
    @staticmethod
    async def authenticate_ws_user(websocket: WebSocket, query_token: str | None = None) -> User:
        # Ưu tiên lấy từ Subprotocol để tránh lộ log URL
        token = query_token
        subprotocols = websocket.scope.get("subprotocols", [])
        if "token" in subprotocols:
            idx = subprotocols.index("token")
            if idx + 1 < len(subprotocols):
                token = subprotocols[idx + 1]

        if not token:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token required")
        
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

    async def handle_connection(self, websocket: WebSocket, token: str | None) -> None:
        # Authenticate and resolve user
        user = await self.authenticate_ws_user(websocket, token)

        # Accept connection and register in manager
        await self.connect_user(user.id, websocket)
        await websocket.send_json({"type": "connection.ready", "user_id": user.id})

        # Keep connection alive with idle timeout
        try:
            while True:
                # receive() nhận cả bytes và text
                message = await asyncio.wait_for(
                    websocket.receive(), timeout=settings.WS_IDLE_TIMEOUT_SECONDS
                )
                
                if message["type"] == "websocket.disconnect":
                    break
                
                if "text" in message:
                    import json
                    data = json.loads(message["text"])
                    if data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif data.get("type") == "voice.source":
                        # Chuyển nguồn trực tiếp ở VoiceStreamer
                        await voice_streamer.set_source(data.get("source"))

                elif "bytes" in message:
                    # Đẩy vào VoiceStreamer
                    voice_streamer.push_chunk(message["bytes"])

        except asyncio.TimeoutError:
            await websocket.close(code=1000, reason="Idle timeout")
        except WebSocketDisconnect:
            pass
        finally:
            self.disconnect_user(user.id, websocket)

# Singleton
realtime_manager = WsService()
