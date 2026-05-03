import logging
import sqlalchemy as sa
from datetime import datetime
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.device import Device
from app.models.device_schedule import DeviceSchedule, ScheduleActionEnum
from app.schemas.device import DeviceType
from app.schemas.schedule import DeviceScheduleCreate, DeviceScheduleUpdate
from app.db.session import AsyncSessionLocal
from app.service.ws_service import realtime_manager
from app.service.device_service import DeviceService

logger = logging.getLogger("yolohome")

class ScheduleService:
    """
    Service quản lý logic liên quan đến hẹn giờ / lập lịch.
    """

    # --- CRUD OPERATIONS ---

    @staticmethod
    async def create_schedule(db: AsyncSession, device_id: str, payload: DeviceScheduleCreate) -> DeviceSchedule:
        await DeviceService.get_device_or_404(db, device_id)
        device_type = await db.scalar(sa.select(Device.type).where(Device.id == device_id))
        
        if device_type in (DeviceType.LOCK, DeviceType.TEMP, DeviceType.HUMI):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Scheduling not supported for this device type")

        schedule = DeviceSchedule(
            device_id=device_id, 
            action=payload.action, 
            time_of_day=payload.time_of_day, 
            is_active=payload.is_active
        )
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
        return schedule

    @staticmethod
    async def list_schedules(db: AsyncSession, device_id: str) -> List[DeviceSchedule]:
        await DeviceService.get_device_or_404(db, device_id)
        result = await db.execute(sa.select(DeviceSchedule).where(DeviceSchedule.device_id == device_id))
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

    # --- RUNTIME OPERATIONS ---

    @staticmethod
    async def run_schedule_check() -> None:
        """
        Logic chạy ngầm: Quét các lịch trình và thực thi nếu khớp thời gian.
        """
        now = datetime.now()
        current_hhmm = now.strftime("%H:%M")

        async with AsyncSessionLocal() as db:
            # Tìm các lịch trình đang hoạt động
            stmt = (
                sa.select(DeviceSchedule, Device)
                .join(Device, DeviceSchedule.device_id == Device.id)
                .where(DeviceSchedule.is_active.is_(True))
            )
            result = await db.execute(stmt)
            rows = result.all()
            
            if not rows:
                return

            for schedule, device in rows:
                # So khớp thời gian
                if current_hhmm != schedule.time_of_day.strftime("%H:%M"):
                    continue

                # THỰC THI LỆNH
                try:
                    is_on = (schedule.action == ScheduleActionEnum.ON)
                    await DeviceService.send_command(
                        db=db,
                        device_id=device.id,
                        is_on=is_on,
                        actor="System Scheduler",
                        source="Automated Schedule"
                    )
                    logger.info(f"[ScheduleService] Kích hoạt {device.name} -> {schedule.action}")

                    # THÔNG BÁO REALTIME
                    ws_payload = {
                        "event": "schedule_triggered",
                        "device_id": device.id,
                        "hardware_id": device.hardware_id,
                        "data": {
                            "action": schedule.action.value,
                            "schedule_id": schedule.id,
                            "message": f"Lịch trình: Đã tự động { 'Bật' if is_on else 'Tắt' } {device.name}",
                        },
                    }
                    await realtime_manager.broadcast(ws_payload)

                except Exception as e:
                    logger.error(f"[ScheduleService] Lỗi thực thi cho {device.name}: {e}")
