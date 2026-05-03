import json
import asyncio
import aiomqtt
from app.core.config import settings
from app.core.logger import logger

class MQTTInfra:
    """
    Hạ tầng MQTT: Quản lý kết nối, vòng đời và hàng đợi gửi tin nhắn.
    """
    def __init__(self):
        self.reconnect_interval = 5
        self.command_queue: asyncio.Queue = asyncio.Queue()

    async def connect_and_listen(self, topics: list[str], message_handler):
        """Duy trì kết nối, đăng ký topic và điều phối nhận/gửi tin nhắn."""
        while True:
            try:
                async with aiomqtt.Client(hostname=settings.MQTT_BROKER_URL, port=settings.MQTT_PORT) as client:
                    logger.info(f"[MQTT Infra] Kết nối thành công đến {settings.MQTT_BROKER_URL}")
                    
                    for topic in topics:
                        await client.subscribe(topic)
                    
                    publish_task = asyncio.create_task(self._process_command_queue(client))
                    
                    async for message in client.messages:
                        await message_handler(message)
                        
            except aiomqtt.MqttError as e:
                logger.error(f"[MQTT Infra] Lỗi kết nối: {e}. Thử lại sau {self.reconnect_interval}s...")
                await asyncio.sleep(self.reconnect_interval)
            except Exception as e:
                logger.error(f"[MQTT Infra] Lỗi không xác định: {e}")
                await asyncio.sleep(self.reconnect_interval)

    async def _process_command_queue(self, client: aiomqtt.Client):
        """Lấy lệnh từ queue và gửi ra MQTT Broker theo thứ tự."""
        try:
            while True:
                task_data = await self.command_queue.get()
                topic = task_data.get("topic")
                payload = task_data.get("payload")
                
                if topic and payload is not None:
                    await client.publish(topic, payload)
                    logger.debug(f"[MQTT Infra Out] Topic: {topic} | Payload: {payload}")
                
                self.command_queue.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[MQTT Infra Queue] Error: {e}")

    async def publish(self, topic: str, payload: str):
        """Đưa yêu cầu gửi lệnh vào hàng đợi để xử lý ngầm."""
        await self.command_queue.put({
            "topic": topic,
            "payload": payload
        })

# Instance duy nhất cho toàn bộ hệ thống
mqtt_infra = MQTTInfra()
