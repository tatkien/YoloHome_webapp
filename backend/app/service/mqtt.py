import json
import asyncio
import aiomqtt
from app.core.device_handle import DeviceHandler
from app.core.config import settings

class MQTTService:
    def __init__(self):
        self.client = None
        self.reconnect_interval = 5  # chờ để thử kết nối lại nếu rớt mạng

    async def connect_and_subscribe(self):
        """Duy trì kết nối, lắng nghe Topic và tự động kết nối lại"""
        while True:
            try:
                async with aiomqtt.Client(hostname=settings.MQTT_BROKER_URL, port=settings.MQTT_PORT) as client:
                    self.client = client
                    print(f"[MQTT Service] Đã kết nối thành công tới Broker: {settings.MQTT_BROKER_URL}")
                    
                    # Đăng ký lắng nghe các sự kiện từ phần cứng
                    await client.subscribe("smart_home/hardware/+/announce")
                    await client.subscribe("smart_home/hardware/+/sensor")
                    await client.subscribe("smart_home/hardware/+/state")
                    
                    # Vòng lặp nhận tin nhắn
                    async for message in client.messages:
                        # Dùng create_task để chạy ngầm
                        asyncio.create_task(self.route_message(message))
                        
            except aiomqtt.MqttError as e:
                print(f"[MQTT Service] Lỗi mạng/Broker: {e}. Đang thử kết nối lại sau {self.reconnect_interval}s...")
                self.client = None
                await asyncio.sleep(self.reconnect_interval)
            except Exception as e:
                print(f"[MQTT Service] Lỗi hệ thống nghiêm trọng: {e}. Đang thử khởi động lại sau {self.reconnect_interval}s...")
                self.client = None
                await asyncio.sleep(self.reconnect_interval)

    async def route_message(self, message):
        """Phân loại và điều hướng tin nhắn"""
        topic = str(message.topic)
        
        try:
            payload_str = message.payload.decode()
            parts = topic.split('/')
            
            # Topic chuẩn: smart_home/hardware/{hardware_id}/{event_type}
            if len(parts) < 4: 
                return
            
            hardware_id = parts[2]
            event_type = parts[3]
            
            payload = json.loads(payload_str)
            
            # GỬI ĐẾN HANDLER TƯƠNG ỨNG
            if event_type == 'announce':
                await DeviceHandler.process_announce(hardware_id, payload)
            elif event_type == 'sensor':
                await DeviceHandler.process_sensor(hardware_id, payload)
            elif event_type == 'state':
                await DeviceHandler.process_state(hardware_id, payload)
                
        except json.JSONDecodeError:
            print(f"[MQTT Service] Lỗi sai định dạng JSON từ topic {topic}: {message.payload}")
        except Exception as e:
            print(f"[MQTT Service] Lỗi xử lý gói tin: {e}")

    
    async def publish_command(self, hardware_id: str, pin: str, is_on: bool, value: int = 0):
        """Đóng gói JSON và gửi lệnh qua Broker cho phần cứng."""
        if not self.client:
            print("[MQTT Service] Không thể gửi lệnh: Hệ thống đang rớt kết nối Broker!")
            return False

        topic = f"smart_home/hardware/{hardware_id}/command"
        
        command_payload = {
            "pin": pin,
            "isOn": is_on,
            "value": value
        }

        try:
            await self.client.publish(topic, json.dumps(command_payload))
            print(f"[MQTT Gửi] Topic: {topic} | Lệnh: {command_payload}")
            return True
        except Exception as e:
            print(f"[MQTT Service] Lỗi khi gửi lệnh xuống mạch: {e}")
            return False

# Khởi tạo đối tượng để dùng chung cho toàn bộ app
mqtt_service = MQTTService()