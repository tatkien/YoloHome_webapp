import json
import uuid
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.device import Device, HardwareNode, DeviceShare
from app.schemas.mqtt import MqttAnnounceSchema, MqttStateSchema
from app.realtime.websocket_manager import realtime_manager
from app.service.history import add_history_record

class DeviceHandler:
    @staticmethod
    def guess_device_type(pin_name: str) -> str:
        """
        Infer device type from pin name.
        """
        name = pin_name.lower()
        
        if "temp" in name:
            return "temp_sensor"
        if "humi" in name:
            return "humidity_sensor"
        if "servo" in name:
            return "lock" 
        return "unknown"
    
    @staticmethod
    async def _get_authorized_users(session: AsyncSession, hardware_id: str, device_id: str | None = None) -> list[int]:
        """Get list of users authorized to receive notifications."""
        authorized_users = set()
        
        # 1. Find owner via HardwareNode
        stmt_owner = select(HardwareNode.owner_id).where(HardwareNode.id == hardware_id)
        res_owner = await session.execute(stmt_owner)
        owner_id = res_owner.scalar_one_or_none()
        
        if owner_id:
            authorized_users.add(owner_id)
            
        # 2. Find users shared on this device
        if device_id:
            stmt_shared = select(DeviceShare.user_id).where(DeviceShare.device_id == device_id)
            res_shared = await session.execute(stmt_shared)
            shared_user_ids = res_shared.scalars().all()
            authorized_users.update(shared_user_ids)
            
        return list(authorized_users)
    
    @staticmethod
    async def process_announce(hardware_id: str, payload: dict):
        """Handle hardware announce message."""
        data = MqttAnnounceSchema(**payload)
        async with AsyncSessionLocal() as session:
            session: AsyncSession
            stmt = select(HardwareNode).where(HardwareNode.id == hardware_id)
            res = await session.execute(stmt)
            node = res.scalar_one_or_none()
            
            if node:
                node.name = data.name
                node.pins = data.pins
            else:
                # New hardware node, create in DB
                new_node = HardwareNode(id=hardware_id, name=data.name, pins=data.pins)
                session.add(new_node)
            await session.commit()
            print(f"[Handler] Hardware updated: {hardware_id}")

    @staticmethod
    async def process_state(hardware_id: str, payload: dict):
        """Handle state feedback (servo/light/fan)."""
        data = MqttStateSchema(**payload) 
        async with AsyncSessionLocal() as session:
            session: AsyncSession

            try:
                stmt = select(Device).where(Device.hardwareId == hardware_id, Device.pin == data.pin)
                res = await session.execute(stmt)
                device = res.scalar_one_or_none()
                
                device_id_to_broadcast = None
                
                if device:
                    # Device already exists in DB
                    if device.isOn != data.isOn or device.value != data.value:
                        device.isOn = data.isOn
                        device.value = data.value
                        
                        msg = f"Updated: {'ON' if data.isOn else 'OFF'}, Value: {data.value}"
                        await add_history_record(device.id, device.name, f"[Feedback] {msg}", "system", "Hardware")
                        
                        await session.commit()
                        print(f"[Handler] Synced device {data.pin} on hardware {hardware_id}")

                        device_id_to_broadcast = device.id
                else:
                    # Auto-create servo lock device
                    if "servo" in data.pin.lower():
                        new_id = str(uuid.uuid4())
                        new_device = Device(
                            id=new_id,
                            name="Auto Lock",
                            type="lock",
                            hardwareId=hardware_id,
                            pin=data.pin,
                            isOn=data.isOn,
                            value=data.value
                        )
                        session.add(new_device)
                        await session.commit()
                        print(f"[Handler] Auto-added door lock on pin {data.pin}")

                        device_id_to_broadcast = new_id

                # ==========================================
                    # SEND WEBSOCKET TO AUTHORIZED USERS
                # ==========================================
                if device_id_to_broadcast:
                    user_ids = await DeviceHandler._get_authorized_users(session, hardware_id, device_id_to_broadcast)
                    
                    if user_ids:
                        ws_payload = {
                            "event": "device_update",
                            "device_id": device_id_to_broadcast,
                            "hardware_id": hardware_id,
                            "data": {
                                "isOn": data.isOn,
                                "value": data.value
                            }
                        }
                        for uid in user_ids:
                            await realtime_manager.send_to_user(uid, ws_payload)   
                   

            except Exception as e:
                await session.rollback()
                print(f"[Handler] State update error: {e}")
    

    @staticmethod
    async def process_sensor(hardware_id: str, payload: dict):
        """Handle sensor payloads (temperature/humidity)."""
        async with AsyncSessionLocal() as session:
            session: AsyncSession

            try:
                is_changed = False
                
                for pin_name, val in payload.items():
                    stmt = select(Device).where(Device.hardwareId == hardware_id, Device.pin == pin_name)
                    res = await session.execute(stmt)
                    device = res.scalar_one_or_none()
                    
                    if device:
                        if device.value != val:
                            device.value = val
                            is_changed = True
                            await add_history_record(device.id, device.name, f"[Sensor] {val}", "system", "Hardware")
                    else:
                        new_device_id = str(uuid.uuid4())
                        new_device = Device(
                            id = new_device_id,
                            name = f"Sensor ({pin_name})", 
                            type = DeviceHandler.guess_device_type(pin_name),
                            hardwareId = hardware_id,
                            pin = pin_name,
                            value = val
                        )
                        session.add(new_device)
                        is_changed = True
                        await add_history_record(new_device_id, new_device.name, f"[Sensor] Initialized value: {val}", "system", "Hardware")
                
                # Send websocket only when data changed
                if is_changed:
                    await session.commit()
                    print(f"[Handler] Synced sensor data for hardware {hardware_id}")
                    # ==========================================
                    # SEND WEBSOCKET TO AUTHORIZED USERS
                    # ==========================================
                    # Check hardware owner
                    user_ids = await DeviceHandler._get_authorized_users(session, hardware_id, device_id=None)
                    
                    if user_ids:
                        ws_payload = {
                            "event": "sensor_update",
                            "hardware_id": hardware_id,
                            "data": payload
                        }
                        for uid in user_ids:
                            await realtime_manager.send_to_user(uid, ws_payload)
                    
            except Exception as e:
                await session.rollback()
                print(f"[Handler] Sensor update error: {e}")