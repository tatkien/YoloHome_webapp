import json
import asyncio
from app.service.device_service import DeviceService
from app.service.voice_intent import voice_intent_service
from app.db.session import AsyncSessionLocal
from app.core.logger import logger
from app.core.mqtt_infra import mqtt_infra

class MQTTService:
    """
    Xử lý logic và phân luồng dữ liệu các topic MQTT.
    """
    def __init__(self):
        self.infra = mqtt_infra
        self.topics = [
            "smart_home/hardware/+/announce",
            "smart_home/hardware/+/sensor",
            "smart_home/hardware/+/state"
        ]

    async def connect_and_subscribe(self):
        """Kích hoạt kết nối và đăng ký các topic."""
        logger.info("[MQTT Service] Khởi động trình điều phối MQTT...")
        await self.infra.connect_and_listen(
            topics=self.topics,
            message_handler=self.route_message
        )

    async def route_message(self, message):
        """Phân tích tin nhắn topic MQTT đến và gọi các Service tương ứng."""
        topic = str(message.topic)
        try:
            payload_str = message.payload.decode()
            payload = json.loads(payload_str)
            parts = topic.split('/')
            
            if len(parts) < 4: return
            
            hardware_id = parts[2]
            event_type = parts[3]
            
            if event_type == 'announce':
                await DeviceService.process_announce(hardware_id, payload)
                # Reload voice intent cache
                async with AsyncSessionLocal() as session:
                    await voice_intent_service.reload_cache(session)
                    
            elif event_type == 'sensor':
                await DeviceService.process_sensor(hardware_id, payload)
            elif event_type == 'state':
                await DeviceService.process_state(hardware_id, payload)
                
        except Exception as e:
            logger.error(f"[MQTT Service] Lỗi khi xử lý tin nhắn trên {topic}: {e}")

    async def publish_command(self, hardware_id: str, pin: str, payload: dict):
        """Gửi lệnh điều khiển thiết bị xuống phần cứng."""
        topic = f"smart_home/hardware/{hardware_id}/command"
        full_payload = {"pin": pin, **payload}
        return await self.infra.publish(topic, json.dumps(full_payload))

# Service singleton instance
mqtt_service = MQTTService()