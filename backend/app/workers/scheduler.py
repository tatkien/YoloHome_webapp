import logging
from datetime import datetime
import sqlalchemy as sa
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.device_schedule import DeviceSchedule, ScheduleActionEnum
from app.models.device import Device
from app.service.ws_service import realtime_manager
from app.service.command_service import device_command
from app.service.cleanup import run_all_cleanup
from app.core.config import settings

scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)

async def _run_schedule_tick() -> None:
    now = datetime.now()
    current_hhmm = now.strftime("%H:%M")

    async with AsyncSessionLocal() as db:
        db: AsyncSession
        # TÌM CÁC LICH TRÌNH ĐANG HOẠT ĐỘNG VÀ KHỚP GIỜ
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
            time = schedule.time_of_day
            if current_hhmm != time.strftime("%H:%M"):
                continue

            # GỬI LỆNH ĐIỀU KHIỂN
            try:
                is_on = (schedule.action == ScheduleActionEnum.ON)
                await device_command(
                    db=db,
                    device_id=device.id,
                    is_on=is_on,
                    value=None,  # Lấy giá trị mặc định từ config
                    actor="system",
                    source="Schedule"
                )
                logger.info(f"[Schedule] Đã kích hoạt {device.name} -> {schedule.action}")

                # THÔNG BÁO QUA WEBSOCKET
                user_ids = list(realtime_manager.active_connections.keys())
                if user_ids:
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
                    for uid in user_ids:
                        await realtime_manager.send_to_user(uid, ws_payload)

            except Exception as e:
                logger.error(f"[Schedule] Lỗi khi gửi lệnh cho {device.name}: {e}")

async def start_scheduler():
    """Hàm khởi chạy các Job"""
    # Job 1: Kiểm tra lịch hẹn giờ thiết bị mỗi phút
    scheduler.add_job(
        _run_schedule_tick, 
        CronTrigger(minute="*"),
        id="device_schedule_job",
        replace_existing=True
    )
    # Job 2: Chạy tác vụ dọn dẹp định kỳ mỗi 24h
    scheduler.add_job(
        run_all_cleanup,
        CronTrigger(hour=0, minute=0),
        id="cleanup_job",
        replace_existing=True
    )

    scheduler.start()
    logger.info("[APScheduler] Đã khởi động các tác vụ tự động.")

async def stop_scheduler():
    """Hàm dừng Scheduler khi tắt App"""
    scheduler.shutdown()
    logger.info("[APScheduler] Đã dừng các tác vụ tự động.")
