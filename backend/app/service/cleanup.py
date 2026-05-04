import logging
import asyncio
from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.device import SensorData, DeviceLog
import os
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

async def cleanup_old_images() -> int:
    """Dọn dẹp các file ảnh face recognition cũ trên đĩa."""
    count = 0
    async with AsyncSessionLocal() as db:
        try:
            threshold = datetime.now() - timedelta(days=settings.FACE_LOG_RETENTION_DAYS)
            # Tìm các bản ghi cũ
            from app.models.face_recognition_log import FaceRecognitionLog
            stmt = sa.select(FaceRecognitionLog.image_path).where(FaceRecognitionLog.created_at < threshold)
            result = await db.execute(stmt)
            paths = [row[0] for row in result.all() if row[0]]

            # Xóa file
            for path in paths:
                if os.path.isfile(path):
                    try:
                        os.remove(path)
                        count += 1
                    except Exception:
                        pass
            
            # Xóa bản ghi trong DB sau khi xóa file
            if paths:
                del_stmt = sa.delete(FaceRecognitionLog).where(FaceRecognitionLog.created_at < threshold)
                await db.execute(del_stmt)
                await db.commit()
                
            return count
        except Exception as e:
            await db.rollback()
            logger.error(f"[Cleanup] Lỗi khi dọn dẹp ảnh: {e}")
            return 0

async def run_all_cleanup() -> None:
    """
    Tác vụ tổng hợp chạy các dọn dẹp định kỳ.
    """
    logger.info("[Cleanup] Bắt đầu dọn dẹp định kỳ...")
    sensor_task = cleanup_sensor_data()
    log_task = cleanup_device_logs()
    image_task = cleanup_old_images()
    
    sensor_deleted, log_deleted, img_deleted = await asyncio.gather(
        sensor_task, log_task, image_task
    )

    logger.info(
        f"[Cleanup] Hoàn tất. "
        f"Đã dọn dẹp: {sensor_deleted} cảm biến | {log_deleted} nhật ký | {img_deleted} ảnh."
    )
