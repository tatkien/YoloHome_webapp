from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.feed_connections: dict[int, list[WebSocket]] = defaultdict(list)
        self.device_connections: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect_feed(self, feed_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        if websocket not in self.feed_connections[feed_id]:
            self.feed_connections[feed_id].append(websocket)

    async def connect_device(self, device_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        if websocket not in self.device_connections[device_id]:
            self.device_connections[device_id].append(websocket)

    def disconnect_feed(self, feed_id: int, websocket: WebSocket) -> None:
        connections = self.feed_connections.get(feed_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections and feed_id in self.feed_connections:
            del self.feed_connections[feed_id]

    def disconnect_device(self, device_id: int, websocket: WebSocket) -> None:
        connections = self.device_connections.get(device_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections and device_id in self.device_connections:
            del self.device_connections[device_id]

    async def broadcast_feed_value(self, feed_id: int, payload: dict) -> None:
        await self._broadcast(self.feed_connections.get(feed_id, []), payload)

    async def broadcast_device_event(self, device_id: int, payload: dict) -> None:
        await self._broadcast(self.device_connections.get(device_id, []), payload)

    async def _broadcast(self, connections: list[WebSocket], payload: dict) -> None:
        stale_connections: list[WebSocket] = []
        for websocket in list(connections):
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            if websocket in connections:
                connections.remove(websocket)


realtime_manager = ConnectionManager()