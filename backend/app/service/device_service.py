import json
import asyncio
import sqlalchemy as sa
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.device import Device, HardwareNode, SensorData
from app.models.device_schedule import DeviceSchedule
from app.schemas.device import DeviceType, DeviceCreate, DeviceUpdate
from app.schemas.mqtt import MqttAnnounceSchema, MqttStateSchema
from app.schemas.schedule import DeviceScheduleCreate, DeviceScheduleUpdate
from app.core.logger import logger
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.service.history_service import add_history_record
from app.service.ws_service import realtime_manager
from app.core.mqtt_infra import mqtt_infra

class DeviceService:
    """
    Unified service for all device-related operations:
    1. Management (CRUD)
    2. Hardware Handlers (Announce, State, Sensor)
    3. Commanding (Send commands to hardware)
    """

    # ==========================================
    # 1. MANAGEMENT (CRUD)
    # ==========================================
    
    @staticmethod
    async def get_device_or_404(db: AsyncSession, device_id: str) -> Device:
        """Find a device by UUID or raise 404."""
        result = await db.execute(sa.select(Device).where(Device.id == device_id))
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found")
        return device

    @staticmethod
    async def create_device(db: AsyncSession, payload: DeviceCreate, admin_id: str) -> Device:
        await DeviceService.validate_pin_assignment(db, payload.hardware_id, payload.pin, payload.type)
        device_data = payload.model_dump(mode="json")

        if not device_data.get("meta_data"):
            device_data["meta_data"] = settings.DEFAULT_DEVICE_METADATA.get(payload.type.value, {})
            
        if not device_data.get("search_keywords"):
            device_data["search_keywords"] = f"{payload.name}; {payload.room or ''}; {payload.type}"

        new_device = Device(**device_data)
        db.add(new_device)
        await db.commit()
        await db.refresh(new_device)

        await add_history_record(
            device_id=new_device.id,
            device_name=new_device.name,
            action=f"Tạo thiết bị mới (Type: {new_device.type}, Pin: {new_device.pin})",
            actor=admin_id,
            source="Web API (Create)",
        )
        return new_device

    @staticmethod
    async def list_devices(db: AsyncSession) -> List[Device]:
        result = await db.execute(sa.select(Device).order_by(Device.created_at.desc()))
        return result.scalars().all()

    @staticmethod
    async def update_device(db: AsyncSession, device_id: str, payload: DeviceUpdate, admin_id: str) -> Device:
        device = await DeviceService.get_device_or_404(db, device_id)
        update_data = payload.model_dump(mode="json", exclude_unset=True)
        for field, value in update_data.items():
            setattr(device, field, value)

        await db.commit()
        await db.refresh(device)
        
        ws_payload = {
            "event": "info_updated",
            "device_id": device.id,
            "data": {"name": device.name, "room": device.room},
        }
        await realtime_manager.broadcast(ws_payload)

        await add_history_record(
            device_id=device.id,
            device_name=device.name,
            action="Updated device configuration info",
            actor=admin_id,
            source="Web API (Update)",
        )
        return device

    @staticmethod
    async def delete_device(db: AsyncSession, device_id: str, admin_id: str) -> None:
        device = await DeviceService.get_device_or_404(db, device_id)
        await db.delete(device)
        await db.commit()

        await add_history_record(
            device_id=device.id,
            device_name=device.name,
            action="Xóa thiết bị khỏi hệ thống",
            actor=admin_id,
            source="Web API (Delete)",
        )

    @staticmethod
    async def validate_pin_assignment(db: AsyncSession, hardware_id: str, pin: str, device_type: DeviceType) -> None:
        node = await db.get(HardwareNode, hardware_id)
        if not node:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hardware node not found")

        pins_data = node.pins or []
        target_pin_config = next((p for p in pins_data if (p.get("pin") if isinstance(p, dict) else p.pin) == pin), None)

        if not target_pin_config:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Pin '{pin}' not found")

        pin_fixed_type = target_pin_config.get("type") if isinstance(target_pin_config, dict) else target_pin_config.type
        if pin_fixed_type != "unknown" and device_type.value != pin_fixed_type:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Pin '{pin}' is dedicated to '{pin_fixed_type}'")
        
        existing = await db.execute(sa.select(Device).where(Device.hardware_id == hardware_id, Device.pin == pin))
        if existing.scalar_one_or_none():
            raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Pin '{pin}' on hardware '{hardware_id}' is already in use")

    # ==========================================
    # 2. HARDWARE HANDLERS
    # ==========================================

    @staticmethod
    async def process_announce(hardware_id: str, payload: dict):
        """Handle hardware announce message."""
        data = MqttAnnounceSchema(**payload)
        async with AsyncSessionLocal() as session:
            stmt = sa.select(HardwareNode).where(HardwareNode.id == hardware_id)
            res = await session.execute(stmt)
            node = res.scalar_one_or_none()

            pin_list_for_db = [p.model_dump() for p in data.pins]
            if node:
                node.name = data.name
                node.pins = pin_list_for_db
            else:
                new_node = HardwareNode(id=hardware_id, name=data.name, pins=pin_list_for_db)
                session.add(new_node)
            await session.commit()
            logger.info(f"[Handler] Đã cập nhật phần cứng: {hardware_id}")

            for p_config in data.pins:
                if p_config.type == DeviceType.UNKNOWN: continue 
                dev_stmt = sa.select(Device).where(Device.hardware_id == hardware_id, Device.pin == p_config.pin)
                dev_res = await session.execute(dev_stmt)
                device = dev_res.scalar_one_or_none()

                if not device:
                    new_dev = Device(
                        hardware_id=hardware_id,
                        pin=p_config.pin,
                        name=f"{p_config.type.capitalize()} on {data.name}",
                        type=p_config.type,
                        meta_data=settings.DEFAULT_DEVICE_METADATA.get(p_config.type.value, {})
                    )
                    session.add(new_dev)
                    logger.info(f"[Handler] Tự tạo thiết bị: {p_config.pin} ({p_config.type})")
                else:
                    device.type = p_config.type
            await session.commit()

    @staticmethod
    async def process_state(hardware_id: str, payload: dict):
        """Handle device state update from hardware."""
        data = MqttStateSchema(**payload)
        async with AsyncSessionLocal() as session:
            stmt = sa.select(Device).where(Device.hardware_id == hardware_id, Device.pin == data.pin)
            res = await session.execute(stmt)
            device = res.scalar_one_or_none()

            if device:
                # Xử lý và ghi log nếu thay đổi trạng thái
                old_state = device.is_on
                old_value = (device.meta_data or {}).get("value")
                
                changed = (old_state != data.is_on) or (data.value is not None and old_value != data.value)

                device.is_on = data.is_on
                device.last_seen_at = sa.func.now()
                if data.value is not None:
                    device.value = data.value
                    device.meta_data = {**(device.meta_data or {}), "value": data.value}
                
                await session.commit()
                
                # Gửi tin nhắn Realtime
                ws_payload = {
                    "event": "device_update",
                    "device_id": device.id,
                    "hardware_id": hardware_id,
                    "data": {
                        "is_on": data.is_on, 
                        "value": data.value,
                        "pending": False
                    },
                }
                await realtime_manager.broadcast(ws_payload)

                # Ghi lịch sử nếu có thay đổi hoặc có lỗi từ phần cứng
                if changed or data.status != "success":
                    status_prefix = "[Feedback]" if data.status == "success" else "[FAILED]"
                    await add_history_record(
                        device_id=device.id,
                        device_name=device.name,
                        action=f"{status_prefix} Trạng thái từ thiết bị: {'Bật' if data.is_on else 'Tắt'} (Giá trị: {data.value})",
                        actor="hardware",
                        source="MQTT (State)"
                    )
                    if data.status != "success":
                        logger.warning(f"[Hardware Error] Thiết bị {device.name} báo lỗi thực thi!")
            else:
                logger.debug(f"[Handler] Bỏ qua state cho {hardware_id}:{data.pin} (Chưa setup)")

    @staticmethod
    async def process_sensor(hardware_id: str, payload: dict):
        """Handle sensor data from hardware."""
        async with AsyncSessionLocal() as session:
            try:
                for pin, val in payload.items():
                    stmt = sa.select(Device).where(Device.hardware_id == hardware_id, Device.pin == pin)
                    res = await session.execute(stmt)
                    device = res.scalar_one_or_none()

                    if device:
                        device.last_seen_at = sa.func.now()
                        new_sensor_data = SensorData(device_id=device.id, value=val, sensor_type=device.type)
                        session.add(new_sensor_data)       

                await session.commit()
                        
                ws_payload = {"event": "sensor_update", "hardware_id": hardware_id, "data": payload}
                await realtime_manager.broadcast(ws_payload)
            except Exception as e:
                await session.rollback()
                logger.error(f"[Handler] Lỗi cập nhật cảm biến: {e}")

    # ==========================================
    # 3. COMMANDING
    # ==========================================

    @staticmethod
    async def send_command(db: AsyncSession, device_id: str, is_on: bool, value: float | None = None, actor: str = "system", source: str = "system") -> bool:
        """Executes a control command: updates DB and publishes to MQTT."""
        device = await DeviceService.get_device_or_404(db, device_id)
        dev_type = device.type.value if hasattr(device.type, 'value') else device.type

        final_value = value

        # Logic điều phối giá trị dựa trên Metadata (DB) và Config (settings)
        meta = device.meta_data or {}
        default_meta = settings.DEFAULT_DEVICE_METADATA.get(dev_type, {})
        
        # Xác định dải giá trị [min, max]
        v_range = meta.get("range") or default_meta.get("range") or [0, 1023]
        v_min, v_max = v_range[0], v_range[1]

        # Xử lý giá trị điều khiển
        if is_on:
            if final_value is None:
                # Ưu tiên: 1. Giá trị hiện tại (nếu > 0), 2. Mặc định DB, 3. Mặc định Config, 4. Max
                final_value = (device.value if device.value and device.value > 0 else None) or \
                              meta.get("default_value") or \
                              default_meta.get("default_value") or \
                              v_max
            final_value = max(v_min, min(v_max, final_value))
        else:
            final_value = v_min

        # Lấy hardware_id để gửi MQTT
        hardware_id = device.hardware_id
        pin = device.pin

        # Publish to MQTT
        topic = f"smart_home/hardware/{hardware_id}/command"
        mqtt_payload = {
            "pin": pin,
            "is_on": is_on,
            "value": int(final_value) if dev_type in ["fan", "light", "lock"] else final_value
        }
        await mqtt_infra.publish(topic, json.dumps(mqtt_payload))

        # WebSocket Broadcast
        ws_payload = {
            "event": "device_update",
            "device_id": device.id,
            "hardware_id": hardware_id,
            "data": {
                "is_on": is_on, 
                "value": final_value,
                "pending": True
            },
        }
        await realtime_manager.broadcast(ws_payload)

        # 4. History Log
        await add_history_record(
            device_id=device.id,
            device_name=device.name,
            action=f"[SENT] Yêu cầu {'Bật' if is_on else 'Tắt'} thiết bị (Giá trị: {final_value})",
            actor=actor,
            source=source
        )
        return True


class HardwareService:
    @staticmethod
    async def list_hardware_nodes(db: AsyncSession) -> List[HardwareNode]:
        result = await db.execute(sa.select(HardwareNode))
        return result.scalars().all()

    @staticmethod
    async def read_hardware_node(db: AsyncSession, hardware_id: str) -> HardwareNode:
        node = await db.get(HardwareNode, hardware_id, options=[selectinload(HardwareNode.devices)])
        if not node:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hardware board not found")
        return node

    @staticmethod
    async def delete_hardware_node(db: AsyncSession, hardware_id: str) -> None:
        node = await db.get(HardwareNode, hardware_id)
        if not node:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hardware board not found")
        await db.delete(node)
        await db.commit()


