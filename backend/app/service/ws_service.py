import asyncio
from collections import defaultdict
import sqlalchemy as sa
from fastapi import WebSocket, WebSocketDisconnect, WebSocketException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core.logger import logger

WS_IDLE_TIMEOUT_SECONDS = 60

class WsService:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = defaultdict(list)

    # ==========================================
    # CONNECTION MANAGEMENT
    # ==========================================
    async def connect_user(self, user_id: int, websocket: WebSocket) -> None:
        """Register a shared websocket connection for a user."""
        await websocket.accept()
        if websocket not in self.active_connections[user_id]:
            self.active_connections[user_id].append(websocket)

    def disconnect_user(self, user_id: int, websocket: WebSocket) -> None:
        """Disconnect a websocket and clean up in-memory state."""
        connections = self.active_connections.get(user_id)
        if connections and websocket in connections:
            connections.remove(websocket) 
        
        # If user closed all tabs/apps, remove the key from the dict
        if connections is not None and not connections:
            self.active_connections.pop(user_id, None)

    # ==========================================
    # DATA DELIVERY
    # ==========================================
    async def send_to_user(self, user_id: int, payload: dict) -> None:
        """
        Send data to all online client connections of this user.
        """
        connections = self.active_connections.get(user_id, [])
        if not connections:
            return

        # 1. Build send tasks
        targets = list(connections)
        tasks = [ws.send_json(payload) for ws in targets]
        
        # 2. Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 3. Inspect results and remove dead connections automatically
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                ws_failed = targets[i]
                if ws_failed in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(ws_failed)
                logger.debug(f"[WS Cleanup] Removed stale connection for user {user_id} due to: {result}")
        
        # Final cleanup check
        if not self.active_connections[user_id]:
            self.active_connections.pop(user_id, None)

    # ==========================================
    # BUSINESS LOGIC
    # ==========================================
    @staticmethod
    async def authenticate_ws_user(token: str) -> User:
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
        # 1. Authenticate and resolve user
        user = await self.authenticate_ws_user(token)

        # 2. Accept connection and register in manager
        await self.connect_user(user.id, websocket)
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
            self.disconnect_user(user.id, websocket)

# Shared singleton instance
realtime_manager = WsService()
