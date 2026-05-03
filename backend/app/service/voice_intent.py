import asyncio
import re
import unicodedata
from rapidfuzz import process, fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from logging import getLogger
from app.models.device import Device
from app.service.device_service import DeviceService

logger = getLogger("yolohome")

def remove_dau(input_str: str) -> str:
    if not input_str: return ""
    # Chữ đ
    s = input_str.replace('đ', 'd').replace('Đ', 'D')
    nfkd_form = unicodedata.normalize('NFKD', s)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()

def normalize_numbers(text: str) -> str:
    # Chuyển chữ thành số (sau khi đã khử dấu)
    num_map = {
        "khong": "0", "mot": "1", "hai": "2", "ba": "3", "tu": "4", "bon": "4",
        "nam": "5", "sau": "6", "bay": "7", "tam": "8", "chin": "9", "muoi": "10"
    }
    words = text.split()
    return " ".join([num_map.get(w, w) for w in words])

def extract_level(sentence_khongdau: str, device_kw_khongdau: str = None) -> int | None:
    """
    :param sentence_khongdau: Câu lệnh đã khử dấu và chuyển chữ thành số.
    :param device_kw_khongdau: Từ khóa của thiết bị đã khớp.
    """
    text = sentence_khongdau
    
    # Xóa tên thiết bị khỏi câu
    if device_kw_khongdau:
        text = text.replace(device_kw_khongdau, " [DEVICE] ")

    # Tìm số theo từ khóa neo
    patterns = [
        r'(?:muc|so|nac|toc do|kenh|gia tri)\s*(\d+)',
        r'\b(\d+)\s*(?:do|phan tram|%)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            # Lấy 1 trong 2 group tùy cái nào khớp
            val = match.group(1) or match.group(2)
            return int(val)

    # Nếu không tìm thấy từ khóa, lấy số cuối cùng
    remaining_numbers = re.findall(r'\b(\d+)\b', text)
    if remaining_numbers:
        return int(remaining_numbers[-1])

    return None

class VoiceIntentService:
    """
    Voice Intent Service: Trích xuất ý định và thực thi lệnh từ giọng nói.
    """
    def __init__(self):
        self._device_cache = []  # Lưu: (kw_goc, kw_khu_dau, device_obj)
        self._action_list = []   # Lưu: (kw_goc, kw_khu_dau, action_type)
        self.is_ready = False
        self._lock = asyncio.Lock()

        self.action_map = {
            "ON": ["bật", "mở", "chạy", "kích hoạt"],
            "OFF": ["tắt", "đóng", "ngắt", "dừng"],
            "SET_LEVEL": ["mức", "số", "nấc", "tốc độ"]
        }
        self.stop_words = ["ơi", "giùm", "với", "nhỉ", "đi", "tôi", "cho", "cái"]
        self._prepare_actions()

    def _prepare_actions(self):
        """Phẳng hóa và chuẩn bị danh sách hành động hai lớp"""
        flat = []
        for a_type, kws in self.action_map.items():
            for k in kws:
                # Lưu bản gốc và bản đã khử dấu
                flat.append((k.lower(), remove_dau(k), a_type))
        # Sắp xếp từ dài đến ngắn theo bản gốc
        self._action_list = sorted(flat, key=lambda x: len(x[0]), reverse=True)
    
    def _clean_text(self, text: str) -> str:
        """Làm sạch sơ (viết thường, xóa dấu câu, xóa từ thừa)"""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', ' ', text)
        for w in self.stop_words:
            text = re.sub(rf'\b{w}\b', '', text)
        return " ".join(text.split())

    def _get_hybrid_score(self, query_dau, query_khongdau, ref_dau, ref_khongdau):
        """Tính điểm cao nhất giữa có dấu và không dấu"""
        score_dau = fuzz.partial_ratio(query_dau, ref_dau)
        score_khongdau = fuzz.partial_ratio(query_khongdau, ref_khongdau)
        return max(score_dau, score_khongdau)

    async def reload_cache(self, db) -> None:
        """Hàm được gọi khi khởi động hoặc khi thêm/sửa thiết bị trong DB"""
        async with self._lock: 
            result = await db.execute(select(Device))
            devices = result.scalars().all()   
            new_cache = []
        
            for dev in devices:
                kws = dev.search_keywords.split(';') if dev.search_keywords else [dev.name]
                dev_data = {
                    "id": dev.id,
                    "name": dev.name,
                    "meta_data": dev.meta_data,
                    "value": dev.value
                }

                for k in kws:
                    clean = k.strip().lower()
                    if clean:
                        # Tuple (gốc, không dấu, dữ liệu cần của thiết bị)
                        new_cache.append((clean, remove_dau(clean), dev_data))

            self._device_cache = sorted(new_cache, key=lambda x: len(x[0]), reverse=True)
            self.is_ready = True 
            logger.info(f"[VoiceIntent] Đã tải {len(self._device_cache)} từ khóa thiết bị vào cache.")

    async def process_voice_intent(self, db: AsyncSession, sentence: str) -> bool:
        """Hàm chính: Trích xuất action + target và thực thi"""
        if not self.is_ready: 
            await self.reload_cache(db)

        sent_dau = self._clean_text(sentence)
        logger.debug(f"[VoiceIntent] Raw: '{sentence}' -> Cleaned: '{sent_dau}'")
        sent_khongdau = normalize_numbers(remove_dau(sent_dau))

        if not sent_khongdau: 
            return False

        # 1. Tìm hành động (quét từ dài đến ngắn)
        found_action = None
        for kw_goc, kw_khongdau, a_type in self._action_list:
            score = self._get_hybrid_score(sent_dau, sent_khongdau, kw_goc, kw_khongdau)
            if score >= 90: 
                found_action = a_type
                break

        # 2. Tìm thiết bị (tìm từ dài đến ngắn)
        target_device = None
        matched_kw_khongdau = ""
        for kw_d, kw_no_d, dev_obj in self._device_cache:
            score = self._get_hybrid_score(sent_dau, sent_khongdau, kw_d, kw_no_d)
            if score >= 80: 
                target_device = dev_obj
                matched_kw_khongdau = kw_no_d
                break
        
        # 3. Lấy mức độ (nếu có)
        level = extract_level(sent_khongdau, matched_kw_khongdau)
        
        if not found_action or not target_device:
            logger.debug(f"[VoiceIntent] Không tìm thấy: Action={found_action}, Device={target_device}")
            return False

        logger.info(f"[VoiceIntent] Thực thi {found_action} cho thiết bị {target_device['name']}")
        return await self._execute_command(db, target_device, found_action, level)
    
    async def _execute_command(self, db, device: dict, action: str, level: int | None) -> bool:
        """Hàm dịch ý định thành tham số và gọi DeviceService"""
        is_on = None
        value = None

        if action == "ON":
            is_on = True
            # Nếu có mức đi kèm thì dùng luôn mức đó, nếu không mới để None
            value = float(level) if level is not None else None
        elif action == "OFF":
            is_on = False
            value = None 
        elif action == "SET_LEVEL":
            is_on = True
            value = float(level) if level is not None else None
        
        if is_on is None:
            return False
            
        try:
            success = await DeviceService.send_command(
                db=db, 
                device_id=device["id"], 
                is_on=is_on,
                value=value,
                actor="Voice Assistant",
                source="Voice AI"
            )
            return success
        except Exception as e:
            logger.error(f"[VoiceIntent] Lỗi khi điều khiển thiết bị: {e}")
            return False

# Khởi tạo Singleton
voice_intent_service = VoiceIntentService()