import json
import asyncio
import aiomqtt
from app.core.devide_handle import DevideHandler
from app.core.config import settings

class MQTTService:
    def __init__(self):
        self.client = None

    async def connect_and_subscribe(self):
        """Duy trì kết nối và lắng nghe Topic"""
        async with aiomqtt.Client(settings.MQTT_BROKER_URL, port=settings.MQTT_PORT) as client:
            self.client = client
            print(f"[Service] MQTT Connected to {settings.MQTT_BROKER_URL}")
            
            # Đăng ký lắng nghe các sự kiện từ phần cứng
            await client.subscribe("smart_home/hardware/+/announce")
            await client.subscribe("smart_home/hardware/+/sensor")
            await client.subscribe("smart_home/hardware/+/state")
            
            async for message in client.messages:
                await self.route_message(message)

    async def route_message(self, message):
        """Phân loại và điều hướng tin nhắn"""
        topic = str(message.topic)
        payload_str = message.payload.decode()
        parts = topic.split('/')
        
        if len(parts) < 4: return
        
        hardware_id = parts[2]
        event_type = parts[3]
        
        try:
            payload = json.loads(payload_str)
            
            # GỬI ĐẾN HANDLER TƯƠNG ỨNG
            if event_type == 'announce':
                await MQTTHandler.process_announce(hardware_id, payload)
            elif event_type == 'sensor':
                await MQTTHandler.process_sensor(hardware_id, payload)
            elif event_type == 'state':
                await MQTTHandler.process_state(hardware_id, payload)
                
        except Exception as e:
            print(f"[Service] Lỗi xử lý gói tin: {e}")

    
    async def publish_command(self, device_id: str, command_data: dict):
        """
        Đây chính là PHẦN ĐIỀU KHIỂN:
        Gửi lệnh từ Backend xuống thiết bị phần cứng.
        """
        async with AsyncSessionLocal() as session:
            # 1. Tìm thiết bị trong DB để biết nó thuộc mạch nào, chân (pin) nào
            stmt = select(Device).where(Device.id == device_id)
            res = await session.execute(stmt)
            device = res.scalar_one_of_none()

            if not device or not device.hardwareId:
                print(f"Không tìm thấy thiết bị {device_id} để điều khiển")
                return

            # 2. Xây dựng Topic và Nội dung lệnh
            # Topic: smart_home/hardware/ID_CHIP/command
            topic = f"smart_home/hardware/{device.hardwareId}/command"
            
            # Đảm bảo trong lệnh có tên chân (pin) để mạch YoloBit biết chỗ điều khiển
            command_payload = {
                "pin": device.pin,
                "isOn": command_data.get("isOn", True),
                "value": command_data.get("value", 0)
            }

            # 3. Gửi (Publish) qua MQTT Broker
            if self.client:
                await self.client.publish(topic, json.dumps(command_payload))
                print(f"[MQTT Gửi] Topic: {topic} | Lệnh: {command_payload}")