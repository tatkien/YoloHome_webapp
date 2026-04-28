from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from app.models.device import Device, HardwareNode, SensorData, DeviceLog
from app.models.device_schedule import DeviceSchedule
from app.schemas.device import DeviceType, DeviceCreate, DeviceUpdate
from app.schemas.schedule import DeviceScheduleCreate, DeviceScheduleUpdate
from app.core.logger import logger
from app.core.config import settings
from app.service.history_service import add_history_record
from app.service.ws_service import realtime_manager


class DeviceService:
    @staticmethod
    async def get_device_or_404(db: AsyncSession, device_id: str) -> Device:
        """Find a device by UUID or raise 404."""
        result = await db.execute(sa.select(Device).where(Device.id == device_id))
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found")
        return device

    @staticmethod
    async def validate_pin_assignment(
        db: AsyncSession, hardware_id: str, pin: str, device_type: DeviceType
    ) -> None:
        dt_str = device_type.value
        node = await db.get(HardwareNode, hardware_id)
        if not node:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hardware node not found")

        pins_data = node.pins or []
        target_pin_config = None
        for p in pins_data:
            p_name = p.get("pin") if isinstance(p, dict) else p.pin
            if p_name == pin:
                target_pin_config = p
                break

        if not target_pin_config:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Pin '{pin}' not found")

        pin_fixed_type = target_pin_config.get("type") if isinstance(target_pin_config, dict) else target_pin_config.type

        if pin_fixed_type != "unknown":
            if dt_str != pin_fixed_type:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"Pin '{pin}' is dedicated to '{pin_fixed_type}', cannot be used for '{dt_str}'"
                )
        
        existing = await db.execute(
            sa.select(Device).where(
                Device.hardware_id == hardware_id, 
                Device.pin == pin
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Pin '{pin}' on hardware '{hardware_id}' is already in use by another device",
            )

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
    async def get_camera_devices(db: AsyncSession) -> List[Device]:
        result = await db.execute(
            sa.select(Device).where(Device.type == DeviceType.CAMERA)
        )
        return result.scalars().all()

    @staticmethod
    async def get_device(db: AsyncSession, device_id: str) -> Device:
        return await DeviceService.get_device_or_404(db, device_id)

    @staticmethod
    async def update_device(db: AsyncSession, device_id: str, payload: DeviceUpdate, admin_id: str) -> Device:
        device = await DeviceService.get_device_or_404(db, device_id)

        update_data = payload.model_dump(mode="json", exclude_unset=True)
        for field, value in update_data.items():
            setattr(device, field, value)

        await db.commit()
        await db.refresh(device)

        user_ids = list(realtime_manager.active_connections.keys())
        if user_ids:
            ws_payload = {
                "event": "info_updated",
                "device_id": device.id,
                "data": {"name": device.name, "room": device.room},
            }
            for uid in user_ids:
                await realtime_manager.send_to_user(uid, ws_payload)

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

        await add_history_record(
            device_id=device.id,
            device_name=device.name,
            action="Xóa thiết bị khỏi hệ thống",
            actor=admin_id,
            source="Web API (Delete)",
        )

        await db.delete(device)
        await db.commit()

class HardwareService:
    @staticmethod
    async def list_hardware_nodes(db: AsyncSession) -> List[HardwareNode]:
        result = await db.execute(sa.select(HardwareNode))
        return result.scalars().all()

    @staticmethod
    async def read_hardware_node(db: AsyncSession, hardware_id: str) -> HardwareNode:
        node = await db.get(
            HardwareNode, 
            hardware_id, 
            options=[selectinload(HardwareNode.devices)]
        )
        if not node:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Hardware board not found"
            )
        return node

    @staticmethod
    async def delete_hardware_node(db: AsyncSession, hardware_id: str) -> None:
        node = await db.get(HardwareNode, hardware_id)
        if not node:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hardware board not found")

        await db.delete(node)
        await db.commit()
        

class ScheduleService:
    @staticmethod
    async def create_schedule(db: AsyncSession, device_id: str, payload: DeviceScheduleCreate) -> DeviceSchedule:
        await DeviceService.get_device_or_404(db, device_id)
        device_type = await db.scalar(
            sa.select(Device.type).where(Device.id == device_id)
        )
        if device_type in (DeviceType.LOCK, DeviceType.TEMP, DeviceType.HUMI):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Scheduling is not supported for lock and sensor devices",
            )

        schedule = DeviceSchedule(
            device_id=device_id,
            action=payload.action,
            time_of_day=payload.time_of_day,
            is_active=payload.is_active,
        )
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
        return schedule

    @staticmethod
    async def list_schedules(db: AsyncSession, device_id: str) -> List[DeviceSchedule]:
        await DeviceService.get_device_or_404(db, device_id)

        result = await db.execute(
            sa.select(DeviceSchedule).where(DeviceSchedule.device_id == device_id)
        )
        return result.scalars().all()

    @staticmethod
    async def update_schedule(db: AsyncSession, schedule_id: str, payload: DeviceScheduleUpdate) -> DeviceSchedule:
        schedule = await db.get(DeviceSchedule, schedule_id)
        if not schedule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(schedule, field, value)

        await db.commit()
        await db.refresh(schedule)
        return schedule

    @staticmethod
    async def delete_schedule(db: AsyncSession, schedule_id: str) -> None:
        schedule = await db.get(DeviceSchedule, schedule_id)
        if not schedule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")

        await db.delete(schedule)
        await db.commit()
