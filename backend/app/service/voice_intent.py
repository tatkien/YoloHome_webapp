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
        logger.debug(f"[VoiceIntent] Loại bỏ (Không thấy từ hành động): '{sentence}'")
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
    is_on = None
    value = None
    
    if found_action == "ON":
        is_on = True
    elif found_action == "OFF":
        is_on = False
    elif found_action in ["UP", "DOWN"]:
        if target_device.type != "fan":
            logger.debug(f"[VoiceIntent] Lệnh {found_action} bị từ chối vì {target_device.name} không phải là quạt.")
            return False
            
        meta = target_device.meta_data or {}
        range_val = meta.get("range", [0, 1023])
        min_v, max_v = range_val[0], range_val[1]
        
        # Bước nhảy mặc định là 20% của dải giá trị (hoặc 200 nếu max là 1023)
        step = max_v * 0.2 if max_v > 0 else 200
        
        if found_action == "UP":
            is_on = True
            value = min(max_v, target_device.value + step)
        else: # DOWN
            value = max(min_v, target_device.value - step)
            if value <= 0:
                is_on = False
                value = 0
                
    logger.info(f"[VoiceIntent] Trích xuất ý định thành công: Lệnh={'BẬT' if is_on else 'TẮT'} (Value: {value}) | Device= {target_device.name}")
    
    # Gửi lệnh
    try:
        await device_command(db, target_device.id, is_on, value, "system", "Voice Control")
        return True
    except Exception as e:
        logger.error(f"[VoiceIntent] Gửi lệnh bị lỗi: {e}")
        return False
