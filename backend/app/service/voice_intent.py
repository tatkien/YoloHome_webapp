import re
import unicodedata
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from logging import getLogger
from app.models.device import Device
from app.service.command_service import device_command

logger = getLogger("yolohome")

# Từ điển ánh xạ hành động thô cơ bản
ACTION_MAP = {
    "bật": "ON", "mở": "ON", 
    "tắt": "OFF", "đóng": "OFF", 
    "tăng": "UP", "giảm": "DOWN"
}

def remove_accents(input_str: str) -> str:
    """Loại bỏ dấu tiếng Việt để so khớp phần cứng dễ hơn (Ví dụ: bạt, bật -> bat)"""
    s1 = u'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
    s0 = u'AAAAEEEIIOOOOUUYaaaaeeeiioooouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeEeIiIiOoOoOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuUuYyYyYyYy'
    s = ""
    for c in input_str:
        if c in s1:
            s += s0[s1.index(c)]
        else:
            s += c
    return s.lower()

async def process_voice_intent(db: AsyncSession, sentence: str) -> bool:
    """
    Phân tích câu nói, tìm hành động và thiết bị, sau đó thực thi lệnh.
    """
    original = sentence.lower()
    # Khử dấu
    no_accent_txt = remove_accents(original)
    
    # 1. Tìm hành động
    found_action = None
    for kw, action in ACTION_MAP.items():
        if kw in original or remove_accents(kw) in no_accent_txt:
            found_action = action
            break
            
    if not found_action:
        logger.debug(f"[VoiceIntent] Vứt bỏ (Không thấy động từ): '{sentence}'")
        return False
        
    # 2. Tìm thiết bị khớp
    stmt = select(Device)
    result = await db.execute(stmt)
    devices = result.scalars().all()
    
    target_device = None
    for dev in devices:
        # Check field search_keywords
        if dev.search_keywords:
            keywords = [k.strip() for k in dev.search_keywords.split(';')]
            for kw in keywords:
                if kw.lower() in original or remove_accents(kw) in no_accent_txt:
                    target_device = dev
                    break
        else:
            # Fallback dùng tên gốc
            if dev.name.lower() in original or remove_accents(dev.name) in no_accent_txt:
                target_device = dev
                break
        if target_device:
            break
            
    if not target_device:
        logger.debug(f"[VoiceIntent] Đã thấy lệnh {found_action} nhưng không rõ thiết bị nào: '{sentence}'")
        return False
        
    # 3. Tính toán thông số gửi lệnh
    is_on = True
    value = 1023
    
    if found_action == "ON":
        is_on = True
        value = 1023
    elif found_action == "OFF":
        is_on = False
        value = 0
    elif found_action == "UP":
        is_on = True
        # Ví dụ đơn giản: cộng thêm 200 đơn vị (Mạch YoloBit max 1023)
        value = min(1023, target_device.value + 200)
    elif found_action == "DOWN":
        value = max(0, target_device.value - 200)
        if value <= 0:
            is_on = False
            value = 0
            
    logger.info(f"[VoiceIntent] TRÍCH XUẤT Ý ĐỊNH THÀNH CÔNG: Lệnh={'BẬT' if is_on else 'TẮT'} ({value}) | Device= {target_device.name}")
    
    # Gửi lệnh
    try:
        await device_command(db, target_device.id, is_on, value, "system", "Voice Control")
        return True
    except Exception as e:
        logger.error(f"[VoiceIntent] Gửi lệnh bị lỗi: {e}")
        return False
