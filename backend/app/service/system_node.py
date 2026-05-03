from app.service.device_service import DeviceService
from app.core.logger import logger
from app.core.config import settings

async def setup_system_node():
    """
    Tạo Hardware Node nội bộ.
    """
    server_id = settings.SERVER_ID
    payload = {
        "name": "YoloHome",
        "pins": [
            {"pin": "SYS_CAM", "type": "camera"},
            {"pin": "SYS_MIC", "type": "microphone"}
        ]
    }
    try:
        await DeviceService.process_announce(server_id, payload)
        logger.info(f"[System] Đã đồng bộ Hardware Node nội bộ: {server_id}")
    except Exception as e:
        logger.error(f"[System] Lỗi đồng bộ Hardware Node nội bộ: {e}")