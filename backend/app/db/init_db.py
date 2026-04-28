import logging
import sqlalchemy as sa
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger("yolohome")

async def handle_admin_reset() -> None:
    """
    Xóa tài khoản admin nếu cờ ADMIN_RESET_MODE bật trong .env.
    Dùng để cứu hộ khi quên mật khẩu admin.
    """
    if not settings.ADMIN_RESET_MODE:
        return

    logger.warning("!!! [RESCUE] Chế độ ADMIN_RESET_MODE đang bật...")
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(sa.delete(User).where(User.role == "admin"))
            deleted_count = result.rowcount
            await db.commit()
            if deleted_count > 0:
                logger.info(f"[RESCUE] Đã xóa {deleted_count} tài khoản admin cũ. Sẵn sàng đăng ký mới.")
            else:
                logger.info("[RESCUE] Không tìm thấy tài khoản admin nào để xóa.")
        except Exception as e:
            await db.rollback()
            logger.error(f"[RESCUE] Lỗi khi reset admin: {e}")
