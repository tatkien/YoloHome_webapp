import json
import asyncio
import aiomqtt
from typing import Dict, Any
from app.core.device_handle import DeviceHandler
from app.core.config import settings

class MQTTService:
    def __init__(self):
        self.reconnect_interval = 5
        # Queue để hứng lệnh từ các API truyền vào
        self.command_queue: asyncio.Queue = asyncio.Queue()

    async def connect_and_subscribe(self):
        """Duy trì kết nối, lắng nghe Topic, tự kết nối lại và xử lý hàng đợi lệnh"""
        while True:
            try:
                async with aiomqtt.Client(hostname=settings.MQTT_BROKER_URL, port=settings.MQTT_PORT) as client:
                    print(f"[MQTT Service] Đã kết nối thành công tới Broker: {settings.MQTT_BROKER_URL}")
                    
                    await client.subscribe("smart_home/hardware/+/announce")
                    await client.subscribe("smart_home/hardware/+/sensor")
                    await client.subscribe("smart_home/hardware/+/state")
                    
                    # 1. Chạy ngầm tác vụ bốc lệnh từ Queue ra
                    publish_task = asyncio.create_task(self._process_command_queue(client))

                    # 2. Vòng lặp nhận tin nhắn
                    async for message in client.messages:
                        print(f"[MQTT DEBUG] Có tin nhắn mới! Topic: {message.topic}")
                        asyncio.create_task(self.route_message(message))
                
                        
            except aiomqtt.MqttError as e:
                print(f"[MQTT Service] Lỗi mạng/Broker: {e}. Thử lại sau {self.reconnect_interval}s...")
                await asyncio.sleep(self.reconnect_interval)
            except Exception as e:
                print(f"[MQTT Service] Lỗi hệ thống: {e}. Thử lại sau {self.reconnect_interval}s...")
                await asyncio.sleep(self.reconnect_interval)

    async def _process_command_queue(self, client: aiomqtt.Client):
        """Chạy ngầm lấy lệnh và gửi đi"""
        try:
            while True:
                # Lấy 1 lệnh ra khỏi giỏ
                task_data = await self.command_queue.get()
                topic = task_data["topic"]
                payload = task_data["payload"]
                
                # Gửi lệnh
                await client.publish(topic, payload)
                print(f"[MQTT Gửi] Topic: {topic} | Lệnh: {payload}")
                
                # Báo cáo đã làm xong
                self.command_queue.task_done()
        except Exception as e:
            print(f"[MQTT Queue] Dừng xử lý hàng đợi do rớt mạng: {e}")

    async def route_message(self, message):
        """Phân loại và điều hướng tin nhắn"""
        topic = str(message.topic)
        print(f"[MQTT] Nhận tin tại topic: {topic}")
        try:
            payload_str = message.payload.decode()
            payload = json.loads(payload_str)
            print(f"[MQTT] Nội dung: {payload}")
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
            print(f"[MQTT Service] Lỗi JSON từ topic {topic}")
        except Exception as e:
            print(f"[MQTT Service] Lỗi xử lý gói tin: {e}")

    async def publish_command(self, hardware_id: str, pin: str, is_on: bool, value: int = 0):
        """Hàm công khai cho API gọi: Ném lệnh vào giỏ thay vì gửi trực tiếp"""
        topic = f"smart_home/hardware/{hardware_id}/command"
        command_payload = {
            "pin": pin,
            "isOn": is_on,
            "value": value
        }
        
        # Đưa lệnh vào Queue
        await self.command_queue.put({
            "topic": topic,
            "payload": json.dumps(command_payload)
        })
        return True

# Khởi tạo đối tượng
mqtt_service = MQTTService()