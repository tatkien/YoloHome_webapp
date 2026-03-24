import asyncio
from collections import defaultdict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.hardware_connections: dict[str, list[WebSocket]] = defaultdict(list)
        self.device_connections: dict[str, list[WebSocket]] = defaultdict(list)

    # ==========================================
    # QUẢN LÝ KẾT NỐI (Lúc Web/App mở lên)
    # ==========================================
    async def connect_hardware(self, hardware_id: str, websocket: WebSocket) -> None:
        """Đăng ký nghe toàn bộ cảm biến của 1 bo mạch YoloBit cụ thể"""
        await websocket.accept()
        if websocket not in self.hardware_connections[hardware_id]:
            self.hardware_connections[hardware_id].append(websocket)

    async def connect_device(self, device_id: str, websocket: WebSocket) -> None:
        """Đăng ký nghe trạng thái (Bật/Tắt/Success) của riêng 1 con Quạt/Servo/Đèn"""
        await websocket.accept()
        if websocket not in self.device_connections[device_id]:
            self.device_connections[device_id].append(websocket)

    def disconnect_hardware(self, hardware_id: str, websocket: WebSocket) -> None:
        connections = self.hardware_connections.get(hardware_id)
        if connections and websocket in connections:
            connections.remove(websocket) 
    
        if connections is not None and not connections:
            self.hardware_connections.pop(hardware_id, None)

    def disconnect_device(self, device_id: str, websocket: WebSocket) -> None:
        connections = self.device_connections.get(device_id)
        if connections and websocket in connections:
            connections.remove(websocket)       

        if connections is not None and not connections:
            self.device_connections.pop(device_id, None)

    # ==========================================
    # GỬI DỮ LIỆU LÊN WEB (BROADCAST)
    # ==========================================

    async def broadcast_sensor_data(self, hardware_id: str, payload: dict) -> None:
        """
        Dùng khi mạch gửi: {"temp": 30, "humi": 70}
        """
        message = {
            "event": "sensor_update",
            "hardware_id": hardware_id,
            "data": payload
        }
        await self._broadcast(self.hardware_connections.get(hardware_id, []), message)

    async def broadcast_device_state(self, device_id: str, payload: dict) -> None:
        """
        Dùng khi mạch phản hồi: {"pin": "servo", "isOn": True, "value": 90, "status": "success"}
        """
        message = {
            "event": "device_state_update",
            "device_id": device_id,
            "data": payload
        }
        await self._broadcast(self.device_connections.get(device_id, []), message)


    async def _broadcast(self, connections: list[WebSocket], payload: dict) -> None:
        """Dùng chung"""
        if not connections:
            return

        # 1. Tạo danh sách các tác vụ gửi tin
        targets = list(connections)
        tasks = [ws.send_json(payload) for ws in targets]
        
        # 2. Chạy tất cả cùng lúc. return_exceptions=True nếu có một vài kết nối bị sập.
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 3. Kiểm tra kết quả và dọn dẹp kết nối lỗi
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Nếu kết quả là một Exception, nghĩa là WebSocket đó đã chết
                ws_failed = targets[i]
                if ws_failed in connections:
                    connections.remove(ws_failed)
                    print(f"DEBUG: Removed stale connection due to: {result}")


realtime_manager = ConnectionManager()