import asyncio
import logging
import json
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.device_schedule import DeviceSchedule, ScheduleActionEnum
from app.models.device import Device, SensorData, DeviceTypeEnum
from app.realtime.websocket_manager import realtime_manager
from app.core.logger import add_history_record
from app.service.command_service import device_command
from app.core.config import settings

SCHEDULE_POLL_SECONDS = 30
CLEANUP_INTERVAL_SECONDS = 3600 * 24 # Chạy dọn dẹp mỗi 24 giờ


logger = logging.getLogger(__name__)


async def cleanup_sensor_data():
    """Xóa dữ liệu cảm biến cũ hơn SENSOR_RETENTION_DAYS ngày."""
    async with AsyncSessionLocal() as db:
        try:
            threshold = datetime.now() - timedelta(days=settings.SENSOR_RETENTION_DAYS)
            stmt = sa.delete(SensorData).where(SensorData.created_at < threshold)
            result = await db.execute(stmt)
            await db.commit()
            
            deleted_count = result.rowcount
            if deleted_count > 0:
                logger.info(f"[Cleanup] Đã xóa {deleted_count} bản ghi cảm biến cũ (> {settings.SENSOR_RETENTION_DAYS} ngày).")
        except Exception as e:
            await db.rollback()
            logger.error(f"[Cleanup] Lỗi khi dọn dẹp dữ liệu cảm biến: {e}")


async def run_device_schedule_loop(stop_event: asyncio.Event) -> None:
    """Background loop that checks schedules every 30 seconds."""
    # Khởi tạo last_cleanup là thời điểm hiện tại để tránh chạy dọn dẹp ngay khi vừa start
    last_cleanup = datetime.now()
    
    logger.info("[Scheduler] Vòng lặp kiểm tra lịch hẹn giờ đã bắt đầu.")
    
    while not stop_event.is_set():
        # Dọn dẹp dữ liệu cũ định kỳ (sau mỗi CLEANUP_INTERVAL_SECONDS)
        if (datetime.now() - last_cleanup).total_seconds() >= CLEANUP_INTERVAL_SECONDS:
            logger.info("[Scheduler] Đang chạy task dọn dẹp dữ liệu cảm biến cũ...")
            await cleanup_sensor_data()
            last_cleanup = datetime.now()

        try:
            await _run_schedule_tick()
        except Exception as e:
            logger.error(f"[Scheduler] Lỗi trong vòng lặp tick: {e}")
            logger.exception(e)
        
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SCHEDULE_POLL_SECONDS)
        except (asyncio.TimeoutError, TimeoutError):
            continue


async def _run_schedule_tick() -> None:
    now = datetime.now()
    current_hhmm = now.strftime("%H:%M")
    today = now.date()

    async with AsyncSessionLocal() as db:
        db: AsyncSession

        # 1. Find active schedules that haven't been triggered today
        stmt = (
            sa.select(DeviceSchedule, Device)
            .join(Device, DeviceSchedule.device_id == Device.id)
            .where(
                DeviceSchedule.is_active.is_(True),
                sa.or_(
                    DeviceSchedule.last_triggered_on.is_(None),
                    DeviceSchedule.last_triggered_on != today,
                ),
            )
        )
        result = await db.execute(stmt)
        rows = result.all()  # Returns list of (schedule, device)

        if rows:
            logger.debug(f"[Scheduler] Đang kiểm tra {len(rows)} lịch hẹn giờ active.")
        
        if not rows:
            return

        for schedule, device in rows:
            time = schedule.time_of_day
            if current_hhmm != time.strftime("%H:%M"):
                continue

            # Mark as triggered today
            schedule.last_triggered_on = today

            # 3. GỬI LỆNH XUỐNG PHẦN CỨNG
            try:
                is_on = (schedule.action == ScheduleActionEnum.ON)
                
                # Nếu là đèn (Light) thì gửi 1, nếu là các loại khác (quạt, dimmer) thì gửi 1023
                if device.type == DeviceTypeEnum.LIGHT:
                    value = 1 if is_on else 0
                else:
                    value = 1023 if is_on else 0
                
                await device_command(
                    db=db,
                    device_id=device.id,
                    is_on=is_on,
                    value=float(value),
                    actor="system",
                    source="Schedule"
                )
                logger.info(f"[Schedule] Sent command for {device.name} -> {schedule.action} (Value: {value})")
            except Exception as e:
                logger.error(f"[Schedule] Failed to send command for {device.name}: {e}")
            
            logger.info(
                f"[Schedule] MQTT command sent for {device.name} -> {schedule.action}"
            )

            # Write activity log via history service (logs to file)
            action_str = schedule.action.value.upper() if hasattr(schedule.action, 'value') else str(schedule.action).upper()
            msg = f"Automated schedule: {action_str} command has been sent"
            await add_history_record(
                device.id, device.name, msg, "system", "Schedule"
            )

            # Send websocket event to all connected users
            user_ids = list(realtime_manager.active_connections.keys())

            if user_ids:
                ws_payload = {
                    "event": "schedule_triggered",
                    "device_id": device.id,
                    "hardware_id": device.hardware_id,
                    "data": {
                        "action": schedule.action.value if hasattr(schedule.action, 'value') else schedule.action,
                        "schedule_id": schedule.id,
                        "message": msg,
                    },
                }
                for uid in user_ids:
                    await realtime_manager.send_to_user(uid, ws_payload)

        # Persist last_triggered_on updates
        await db.commit()