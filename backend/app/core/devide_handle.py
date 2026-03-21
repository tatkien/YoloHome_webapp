import json
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.device import Device, HardwareNode
from app.schemas.mqtt import MqttAnnounceSchema, MqttStateSchema
from app.services.history import add_history_record

class DeviveHandler:
    @staticmethod
    async def process_announce(hardware_id: str, payload: dict):
        """Xử lý khi mạch báo danh"""
        data = MqttAnnounceSchema(**payload)
        async with AsyncSessionLocal() as session:
            # Tìm xem node đã tồn tại chưa
            stmt = select(HardwareNode).where(HardwareNode.id == hardware_id)
            res = await session.execute(stmt)
            node = res.scalar_one_of_none()
            
            if node:
                node.name = data.name
                node.pins = data.pins
            else:
                new_node = HardwareNode(id=hardware_id, name=data.name, pins=data.pins)
                session.add(new_node)
            await session.commit()
            print(f"[Handler] Đã cập nhật bo mạch: {hardware_id}")

    @staticmethod
    async def process_state(hardware_id: str, payload: dict):
        """Xử lý phản hồi trạng thái (Dành cho Servo, Đèn, Quạt)"""
        # 1. Validate dữ liệu qua Schema
        data = MqttStateSchema(**payload)
        
        async with AsyncSessionLocal() as session:
            # 2. Tìm thiết bị tương ứng trong DB bằng hardwareId và pin
            stmt = select(Device).where(Device.hardwareId == hardware_id, Device.pin == data.pin)
            res = await session.execute(stmt)
            device = res.scalar_one_of_none()
            
            if device:
                # 3. Chỉ cập nhật nếu có thay đổi
                if device.isOn != data.isOn or device.value != data.value:
                    device.isOn = data.isOn
                    device.value = data.value
                    await session.commit()
                    
                    # 4. Ghi lịch sử hoạt động
                    msg = f"Cập nhật: {'Bật' if data.isOn else 'Tắt'}, Giá trị: {data.value}"
                    await add_history_record(device.id, device.name, f"[Phản hồi] {msg}", "system", "Hardware")
                    print(f"[Handler] Đã đồng bộ thiết bị {data.pin} của mạch {hardware_id}")

    @staticmethod
    async def process_sensor(hardware_id: str, payload: dict):
        """Xử lý dữ liệu cảm biến (Nhiệt độ, Độ ẩm)"""
        async with AsyncSessionLocal() as session:
            for pin_name, val in payload.items():
                stmt = select(Device).where(Device.hardwareId == hardware_id, Device.pin == pin_name)
                res = await session.execute(stmt)
                device = res.scalar_one_of_none()
                
                if device and device.value != val:
                    device.value = val
                    await session.commit()
                    print(f"[Handler] Cập nhật cảm biến {pin_name}: {val}")