import asyncio
from collections import defaultdict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = defaultdict(list)

    # ==========================================
    # QUẢN LÝ KẾT NỐI
    # ==========================================
    async def connect_user(self, user_id: int, websocket: WebSocket) -> None:
        """Đăng ký kết nối chung cho một User"""
        await websocket.accept()
        if websocket not in self.active_connections[user_id]:
            self.active_connections[user_id].append(websocket)

    def disconnect_user(self, user_id: int, websocket: WebSocket) -> None:
        """Ngắt kết nối và dọn dẹp bộ nhớ"""
        connections = self.active_connections.get(user_id)
        if connections and websocket in connections:
            connections.remove(websocket) 
        
        # Nếu user đóng hết các tab/app, xóa luôn key khỏi dict
        if connections is not None and not connections:
            self.active_connections.pop(user_id, None)

    # ==========================================
    # GỬI DỮ LIỆU
    # ==========================================
    async def send_to_user(self, user_id: int, payload: dict) -> None:
        """
        Gửi dữ liệu tới toàn bộ thiết bị đang online của User này.
        """
        connections = self.active_connections.get(user_id, [])
        if not connections:
            return

        # 1. Tạo danh sách các tác vụ gửi tin
        targets = list(connections)
        tasks = [ws.send_json(payload) for ws in targets]
        
        # 2. Chạy tất cả cùng lúc
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 3. Kiểm tra kết quả và tự động dọn dẹp các kết nối bị sập 
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                ws_failed = targets[i]
                if ws_failed in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(ws_failed)
                print(f"DEBUG: Removed stale WS for user {user_id} due to: {result}")
        
        # Check lại
        if not self.active_connections[user_id]:
            self.active_connections.pop(user_id, None)

# Khởi tạo instance dùng chung cho toàn bộ web
realtime_manager = ConnectionManager()