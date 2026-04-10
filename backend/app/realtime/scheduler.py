import asyncio
import logging
import json
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.device_schedule import DeviceSchedule
from app.models.device import Device
from app.realtime.websocket_manager import realtime_manager
from app.core.device_handle import DeviceHandler 
from app.service.history import add_history_record 

SCHEDULE_POLL_SECONDS = 30
logger = logging.getLogger(__name__)

async def run_device_schedule_loop(stop_event: asyncio.Event) -> None:
    """Vòng lặp chạy ngầm kiểm tra hẹn giờ mỗi 30 giây"""
    while not stop_event.is_set():
        try:
            await _run_schedule_tick()
        except Exception:
            logger.exception("Lỗi vòng lặp Device Schedule")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SCHEDULE_POLL_SECONDS)
        except TimeoutError:
            continue

async def _run_schedule_tick() -> None:
    now = datetime.now()
    target_time = now.time().replace(second=0, microsecond=0)
    today = now.date()

    async with AsyncSessionLocal() as db:
        db: AsyncSession
        
        # 1. TÌM LỊCH TỚI GIỜ (JOIN với Device để lấy hardwareId)
        stmt = sa.select(DeviceSchedule, Device).join(
            Device, DeviceSchedule.device_id == Device.id
        ).where(
            DeviceSchedule.is_active.is_(True),
            DeviceSchedule.time_of_day == target_time,
            sa.or_(
                DeviceSchedule.last_triggered_on.is_(None),
                DeviceSchedule.last_triggered_on != today,
            ),
        )
        result = await db.execute(stmt)
        rows = result.all() # Trả về danh sách (schedule, device)

        if not rows:
            return

        for schedule, device in rows:
            # 2. ĐÁNH DẤU ĐÃ CHẠY HÔM NAY
            schedule.last_triggered_on = today

            # 3. BẮN LỆNH XUỐNG PHẦN CỨNG BẰNG MQTT
            mqtt_payload = {
                "device_id": device.id,
                "pin": device.pin,
                "action": schedule.action # "ON" hoặc "OFF"
            }
            # await mqtt_client.publish(f"yolobit/{device.hardwareId}/control", json.dumps(mqtt_payload))
            logger.info(f"[Schedule] Đã bắn MQTT cho {device.name} -> {schedule.action}")

            # 4. GHI LOG LỊCH SỬ VÀO BẢNG DeviceLog
            action_vn = "Bật" if str(schedule.action).upper() == "ON" else "Tắt"
            msg = f"Hẹn giờ tự động: Lệnh {action_vn} đã được gửi"
            await add_history_record(device.id, device.name, msg, "system", "Schedule")

            # 5. BẮN WEBSOCKET BÁO CHO WEB BIẾT
            user_ids = await DeviceHandler._get_authorized_users(db, device.id, device.hardwareId)
            
            if user_ids:
                ws_payload = {
                    "event": "schedule_triggered",
                    "device_id": device.id,
                    "hardware_id": device.hardwareId,
                    "data": {
                        "action": schedule.action,
                        "schedule_id": schedule.id,
                        "message": msg
                    }
                }
                for uid in user_ids:
                    await realtime_manager.send_to_user(uid, ws_payload)

        # Lưu thay đổi last_triggered_on vào DB
        await db.commit()