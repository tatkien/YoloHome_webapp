import json
import uuid
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.device import Device, DeviceTypeEnum, HardwareNode
from app.schemas.mqtt import MqttAnnounceSchema, MqttStateSchema
from app.realtime.websocket_manager import realtime_manager
from app.service.history import add_history_record, add_sensor_data


class DeviceHandler:
    @staticmethod
    def guess_device_type(pin_name: str) -> str:
        """
        Infer device type from pin name.
        Raises ValueError if the pin name cannot be mapped to a known type.
        """
        name = pin_name.lower()

        if "temp" in name:
            return DeviceTypeEnum.TEMP_SENSOR.value
        if "humi" in name:
            return DeviceTypeEnum.HUMIDITY_SENSOR.value
        if "servo" in name:
            return DeviceTypeEnum.LOCK.value

        raise ValueError(
            f"Cannot infer device type from pin name '{pin_name}'. "
            "Only temp, humi, and servo pins are auto-created."
        )

    @staticmethod
    async def _get_authorized_users(
        session: AsyncSession, hardware_id: str, device_id: str | None = None
    ) -> list[int]:
        """Return all connected user IDs — devices are available to every user."""
        return list(realtime_manager.active_connections.keys())

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
                new_node = HardwareNode(
                    id=hardware_id, name=data.name, pins=data.pins
                )
                session.add(new_node)
            await session.commit()
            print(f"[Handler] Hardware updated: {hardware_id}")

    @staticmethod
    async def process_state(hardware_id: str, payload: dict):
        """Handle state feedback (servo/light/fan)."""
        data = MqttStateSchema(**payload)
        # Check if status is not "success", if so, log and skip DB update
        if data.status.lower() != "success":
            print(
                f"[Handler] Received error status from hardware {hardware_id} "
                f"for pin {data.pin}: {data.status}"
            )
            return
        async with AsyncSessionLocal() as session:
            session: AsyncSession

            try:
                stmt = select(Device).where(
                    Device.hardware_id == hardware_id, Device.pin == data.pin
                )
                res = await session.execute(stmt)
                device = res.scalar_one_or_none()

                device_id_to_broadcast = None

                if device:
                    new_value = data.value
                    new_is_on = data.is_on

                    if device.is_on != new_is_on or device.value != new_value:
                        device.is_on = new_is_on
                        device.value = new_value  # @validates on Device handles range checks

                        await session.commit()
                        print(
                            f"[Handler] Synced device {data.pin} on hardware {hardware_id}"
                        )

                        msg = f"Updated: {'ON' if new_is_on else 'OFF'}, Value: {new_value}"
                        await add_history_record(
                            device.id,
                            device.name,
                            f"[Feedback] {msg}",
                            "system",
                            "Hardware",
                        )

                        device_id_to_broadcast = device.id
                else:
                    # Auto-create servo lock device
                    if "servo" in data.pin.lower():
                        new_id = str(uuid.uuid4())
                        new_is_on = data.is_on
                        new_device = Device(
                            id=new_id,
                            name="Auto Lock",
                            type=DeviceTypeEnum.LOCK,
                            hardware_id=hardware_id,
                            pin=data.pin,
                            is_on=new_is_on,
                            value=data.value,
                        )
                        session.add(new_device)
                        await session.commit()
                        print(f"[Handler] Auto-added door lock on pin {data.pin}")

                        device_id_to_broadcast = new_id

                # ==========================================
                # SEND WEBSOCKET TO ALL CONNECTED USERS
                # ==========================================
                if device_id_to_broadcast:
                    user_ids = await DeviceHandler._get_authorized_users(
                        session, hardware_id, device_id_to_broadcast
                    )

                    if user_ids:
                        ws_payload = {
                            "event": "device_update",
                            "device_id": device_id_to_broadcast,
                            "hardware_id": hardware_id,
                            "data": {
                                "is_on": data.is_on,
                                "value": data.value,
                            },
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
                for pin_name, val in payload.items():
                    is_changed = False

                    stmt = select(Device).where(
                        Device.hardware_id == hardware_id, Device.pin == pin_name
                    )
                    res = await session.execute(stmt)
                    device = res.scalar_one_or_none()
                    device_id = device.id if device else None
                    device_type = device.type if device else None
                    device_name = device.name if device else f"Sensor ({pin_name})"
                    if device:
                        if device.value != val:
                            device.value = val
                            device.is_on = True
                            is_changed = True
                    else:
                        # Attempt to guess device type — raises ValueError if unknown pin
                        try:
                            device_type = DeviceHandler.guess_device_type(pin_name)
                        except ValueError as e:
                            print(f"[Handler] Skipping unknown sensor pin: {e}")
                            continue

                        device_id = str(uuid.uuid4())
                        device_type = DeviceTypeEnum(device_type)
                        new_device = Device(
                            id=device_id,
                            name=f"Sensor ({pin_name})",
                            type=device_type,
                            hardware_id=hardware_id,
                            pin=pin_name,
                            value=val,
                            is_on=True,
                        )
                        session.add(new_device)
                        is_changed = True
                       

                    # Send websocket only when data changed
                    if is_changed:
                        await session.commit()
                        await add_history_record(
                            device_id,
                            device_name,
                            f"[Sensor] {val}",
                            "system",
                            "Hardware",
                        )
                        await add_sensor_data(
                            device_id,
                            val,
                            DeviceTypeEnum(device_type),
                        )
                        print(
                            f"[Handler] Synced sensor data for hardware {hardware_id}"
                        )
                        # ==========================================
                        # SEND WEBSOCKET TO ALL CONNECTED USERS
                        # ==========================================
                        user_ids = await DeviceHandler._get_authorized_users(
                            session, hardware_id, device_id=None
                        )

                        if user_ids:
                            ws_payload = {
                                "event": "sensor_update",
                                "hardware_id": hardware_id,
                                "data": payload,
                            }
                            for uid in user_ids:
                                await realtime_manager.send_to_user(uid, ws_payload)

            except Exception as e:
                await session.rollback()
                print(f"[Handler] Sensor update error: {e}")