import logging
import asyncio
from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.device import SensorData, DeviceLog
from app.core.config import settings

logger = logging.getLogger("yolohome")

async def cleanup_sensor_data() -> int:
    """Dọn dẹp bảng sensor_data cũ."""
    async with AsyncSessionLocal() as db:
        try:
            threshold = datetime.now() - timedelta(days=settings.SENSOR_RETENTION_DAYS)
            stmt = sa.delete(SensorData).where(SensorData.created_at < threshold)
            result = await db.execute(stmt)
            await db.commit()
            return result.rowcount
        except Exception as e:
            await db.rollback()
            logger.error(f"[Cleanup] Lỗi khi dọn dẹp dữ liệu cảm biến: {e}")
            return 0


async def cleanup_device_logs() -> int:
    """Dọn dẹp bảng device_logs cũ."""
    async with AsyncSessionLocal() as db:
        try:
            threshold = datetime.now() - timedelta(days=settings.DEVICE_LOG_RETENTION_DAYS)
            stmt = sa.delete(DeviceLog).where(DeviceLog.created_at < threshold)
            result = await db.execute(stmt)
            await db.commit()
            return result.rowcount
        except Exception as e:
            await db.rollback()
            logger.error(f"[Cleanup] Lỗi khi dọn dẹp nhật ký thiết bị: {e}")
            return 0


async def run_all_cleanup() -> None:
    """
    Tác vụ tổng hợp chạy các dọn dẹp định kỳ.
    """
    logger.info("[Cleanup] Bắt đầu dọn dẹp định kỳ...")
    sensor_task = cleanup_sensor_data()
    log_task = cleanup_device_logs()
    sensor_deleted, log_deleted = await asyncio.gather(sensor_task, log_task)

    logger.info(
        f"[Cleanup] Hoàn tất. "
        f"Đã dọn dẹp: {sensor_deleted} cảm biến | {log_deleted} nhật ký thiết bị."
    )
