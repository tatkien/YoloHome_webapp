import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.service.schedule_service import ScheduleService
from app.service.cleanup import run_all_cleanup

scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)

async def start_scheduler():
    """Hàm khởi chạy các Job"""
    # Job 1: Kiểm tra lịch hẹn giờ thiết bị mỗi phút
    scheduler.add_job(
        ScheduleService.run_schedule_check, 
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
