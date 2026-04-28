import json
import asyncio
import aiomqtt
from app.service.device_handle import DeviceHandler
from app.core.config import settings
from app.core.logger import logger

class MQTTService:
    def __init__(self):
        self.reconnect_interval = 5
        # Queue for commands pushed from API endpoints
        self.command_queue: asyncio.Queue = asyncio.Queue()

    async def connect_and_subscribe(self):
        """Keep connection alive, listen to topics, auto-reconnect, and process command queue."""
        while True:
            try:
                async with aiomqtt.Client(hostname=settings.MQTT_BROKER_URL, port=settings.MQTT_PORT) as client:
                    logger.info(f"[MQTT Service] Kết nối thành công đến Broker: {settings.MQTT_BROKER_URL}")
                    
                    await client.subscribe("smart_home/hardware/+/announce")
                    await client.subscribe("smart_home/hardware/+/sensor")
                    await client.subscribe("smart_home/hardware/+/state")
                    
                    # 1. Start background task to publish commands from queue
                    publish_task = asyncio.create_task(self._process_command_queue(client))

                    # 2. Message receive loop
                    async for message in client.messages:
                        logger.debug(f"[MQTT DEBUG] Nhận message mới! Topic: {message.topic}")
                        asyncio.create_task(self.route_message(message))
                
                        
            except aiomqtt.MqttError as e:
                logger.error(f"[MQTT Service] Lỗi mạng/Broker: {e}. Thử lại sau {self.reconnect_interval}s...")
                await asyncio.sleep(self.reconnect_interval)
            except Exception as e:
                logger.error(f"[MQTT Service] Lỗi hệ thống: {e}. Thử lại sau {self.reconnect_interval}s...")
                await asyncio.sleep(self.reconnect_interval)

    async def _process_command_queue(self, client: aiomqtt.Client):
        """Background task: pull commands from queue and publish them."""
        try:
            while True:
                # Pull one command from queue
                task_data = await self.command_queue.get()
                topic = task_data["topic"]
                payload = task_data["payload"]
                
                # Publish command
                await client.publish(topic, payload)
                logger.info(f"[MQTT] Đã gửi lệnh -> Topic: {topic} | Payload: {payload}")
                
                # Mark queue item as processed
                self.command_queue.task_done()
        except Exception as e:
            logger.error(f"[MQTT Queue] Dừng xử lý hàng đợi do lỗi kết nối: {e}")

    async def route_message(self, message):
        """Phân loại và điều phối tin nhắn đến."""
        topic = str(message.topic)
        logger.info(f"[MQTT] Nhận tin nhắn trên topic: {topic}")
        try:
            payload_str = message.payload.decode()
            payload = json.loads(payload_str)
            logger.debug(f"[MQTT] Nội dung: {payload}")
            parts = topic.split('/')
            
            if len(parts) < 4: return
            
            hardware_id = parts[2]
            event_type = parts[3]
            payload = json.loads(payload_str)
            
            if event_type == 'announce':
                await DeviceHandler.process_announce(hardware_id, payload)
            elif event_type == 'sensor':
                await DeviceHandler.process_sensor(hardware_id, payload)
            elif event_type == 'state':
                await DeviceHandler.process_state(hardware_id, payload)
                
        except json.JSONDecodeError:
            logger.warning(f"[MQTT Service] Nhận JSON không hợp lệ từ topic {topic}")
        except Exception as e:
            logger.error(f"[MQTT Service] Lỗi khi xử lý tin nhắn: {e}")

    async def publish_command(self, hardware_id: str, pin: str, payload: dict):
        """Đưa lệnh vào queue để gửi mqtt đi. Payload ở đây đã được xử lý từ command_service"""

        topic = f"smart_home/hardware/{hardware_id}/command"
        command_payload = {
            "pin": pin,
            **payload  # Giải nén dict {'is_on': bool, 'value': int}
        }
        
        # Đưa vào Queue
        await self.command_queue.put({
            "topic": topic,
            "payload": json.dumps(command_payload)
        })

        logger.info(f"[MQTT Queue] Đã đưa lệnh vào hàng đợi cho Pin: {pin}")
        return True

# Service singleton instance
mqtt_service = MQTTService()