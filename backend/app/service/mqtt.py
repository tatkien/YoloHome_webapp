import json
import asyncio
import aiomqtt
from typing import Dict, Any
from app.core.device_handle import DeviceHandler
from app.core.config import settings

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
                    print(f"[MQTT Service] Connected successfully to broker: {settings.MQTT_BROKER_URL}")
                    
                    await client.subscribe("smart_home/hardware/+/announce")
                    await client.subscribe("smart_home/hardware/+/sensor")
                    await client.subscribe("smart_home/hardware/+/state")
                    
                    # 1. Start background task to publish commands from queue
                    publish_task = asyncio.create_task(self._process_command_queue(client))

                    # 2. Message receive loop
                    async for message in client.messages:
                        print(f"[MQTT DEBUG] New message received! Topic: {message.topic}")
                        asyncio.create_task(self.route_message(message))
                
                        
            except aiomqtt.MqttError as e:
                print(f"[MQTT Service] Network/Broker error: {e}. Retrying in {self.reconnect_interval}s...")
                await asyncio.sleep(self.reconnect_interval)
            except Exception as e:
                print(f"[MQTT Service] System error: {e}. Retrying in {self.reconnect_interval}s...")
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
                print(f"[MQTT Publish] Topic: {topic} | Command: {payload}")
                
                # Mark queue item as processed
                self.command_queue.task_done()
        except Exception as e:
            print(f"[MQTT Queue] Stopped processing queue due to connection issue: {e}")

    async def route_message(self, message):
        """Classify and route incoming messages."""
        topic = str(message.topic)
        print(f"[MQTT] Message received on topic: {topic}")
        try:
            payload_str = message.payload.decode()
            payload = json.loads(payload_str)
            print(f"[MQTT] Payload: {payload}")
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
            print(f"[MQTT Service] Invalid JSON received from topic {topic}")
        except Exception as e:
            print(f"[MQTT Service] Error while processing message: {e}")

    async def publish_command(self, hardware_id: str, pin: str, is_on: bool, value: int = 0):
        """Public API method: enqueue command instead of publishing directly."""
        topic = f"smart_home/hardware/{hardware_id}/command"
        command_payload = {
            "pin": pin,
            "isOn": is_on,
            "value": value
        }
        
        # Enqueue command for publisher worker
        await self.command_queue.put({
            "topic": topic,
            "payload": json.dumps(command_payload)
        })
        return True

# Service singleton instance
mqtt_service = MQTTService()