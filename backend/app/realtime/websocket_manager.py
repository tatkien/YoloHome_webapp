import asyncio
from collections import defaultdict
from fastapi import WebSocket

class ConnectionManager:
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
                print(f"DEBUG: Removed stale WS for user {user_id} due to: {result}")
        
        # Final cleanup check
        if not self.active_connections[user_id]:
            self.active_connections.pop(user_id, None)

# Shared singleton instance for the whole web app
realtime_manager = ConnectionManager()