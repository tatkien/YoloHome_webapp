import logging
from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.device import SensorData, DeviceLog
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger("yolohome")

async def handle_admin_reset(db: AsyncSession) -> None:
    """
    Xóa tài khoản admin nếu cờ ADMIN_RESET_MODE bật trong .env.
    Cung cấp cơ chế khi admin quên mật khẩu.
    """
    if not settings.ADMIN_RESET_MODE:
        return

    logger.warning("!!! [RESCUE] Chế độ ADMIN_RESET_MODE đang BẬT. Đang xóa các tài khoản admin cũ...")

    result = await db.execute(sa.delete(User).where(User.role == "admin"))
    deleted_count = result.rowcount
    await db.commit()

    if deleted_count > 0:
        logger.info(f"!!! [RESCUE] Đã xóa thành công {deleted_count} tài khoản admin. Hệ thống sẵn sàng để đăng ký admin lại.")
    else:
        logger.info("!!! [RESCUE] Không tìm thấy tài khoản admin nào để xóa. Hệ thống đã sẵn sàng để đăng ký lại.")


async def cleanup_sensor_data() -> int:
    """
    Xóa dữ liệu cảm biến (bảng sensor_data) cũ hơn SENSOR_RETENTION_DAYS ngày.
    Trả về số bản ghi đã xóa.
    """
    async with AsyncSessionLocal() as db:
        try:
            threshold = datetime.now() - timedelta(days=settings.SENSOR_RETENTION_DAYS)
            stmt = sa.delete(SensorData).where(SensorData.created_at < threshold)
            result = await db.execute(stmt)
            await db.commit()
            deleted = result.rowcount
            if deleted > 0:
                logger.info(
                    f"[Maintenance] Đã xóa {deleted} bản ghi cảm biến cũ "
                    f"(> {settings.SENSOR_RETENTION_DAYS} ngày)."
                )
            return deleted
        except Exception as e:
            await db.rollback()
            logger.error(f"[Maintenance] Lỗi khi dọn dẹp dữ liệu cảm biến: {e}")
            return 0


async def cleanup_device_logs() -> int:
    """
    Xóa nhật ký thiết bị (bảng device_logs) cũ hơn DEVICE_LOG_RETENTION_DAYS ngày.
    Trả về số bản ghi đã xóa.
    """
    async with AsyncSessionLocal() as db:
        try:
            threshold = datetime.now() - timedelta(days=settings.DEVICE_LOG_RETENTION_DAYS)
            stmt = sa.delete(DeviceLog).where(DeviceLog.created_at < threshold)
            result = await db.execute(stmt)
            await db.commit()
            deleted = result.rowcount
            if deleted > 0:
                logger.info(
                    f"[Maintenance] Đã xóa {deleted} bản ghi nhật ký thiết bị cũ "
                    f"(> {settings.DEVICE_LOG_RETENTION_DAYS} ngày)."
                )
            return deleted
        except Exception as e:
            await db.rollback()
            logger.error(f"[Maintenance] Lỗi khi dọn dẹp nhật ký thiết bị: {e}")
            return 0


async def run_all_maintenance() -> None:
    """
    Chạy các tác vụ dọn dẹp định kỳ mỗi 24h (gọi từ scheduler)
    """
    logger.info("[Maintenance] Bắt đầu tác vụ bảo trì định kỳ...")
    sensor_deleted = await cleanup_sensor_data()
    log_deleted = await cleanup_device_logs()
    logger.info(
        f"[Maintenance] Hoàn tất. "
        f"Cảm biến: -{sensor_deleted} bản ghi | Nhật ký: -{log_deleted} bản ghi."
    )
