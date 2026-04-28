import asyncio
import numpy as np
from faster_whisper import WhisperModel
import logging
import openwakeword
from collections import deque
from openwakeword.model import Model
from app.workers.voice_stream import voice_streamer_service
from app.service.voice_intent import process_voice_intent
from app.core.config import settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("yolohome")

# Cấu hình cho Voice Control
OWW_SAMPLES_PER_CHUNK = 1280 
SILENCE_THRESHOLD = 300  # Ngưỡng RMS để nhận diện kết thúc câu lệnh
MIN_SILENCE_CHUNKS = 8   # Khoảng 1.5 giây im lặng để chốt lệnh

class VoiceLogicService:
    def __init__(self):
        self.whisper_model = None
        self.oww_model = None
        self.is_running = False
        self._task = None
        self.inferring = False # Cờ để tránh chạy song song nhiều Whisper
        
    def load_models(self):
        """Nạp các mô hình AI trong thread riêng."""
        # 1. Nạp Whisper
        if self.whisper_model is None:
            logger.info("[VoiceLogic] Đang nạp mô hình Whisper 'base' (CPU/int8)...")
            self.whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
            logger.info("[VoiceLogic] Whisper AI đã nạp.")

        # 2. Nạp openWakeWord
        if self.oww_model is None:
            wake_word = settings.WAKE_WORD # Mặc định là 'hey_jarvis'
            logger.info(f"[VoiceLogic] Đang nạp mô hình Wake Word: {wake_word}...")
            self.oww_model = Model(
                wakeword_models=[wake_word],
                inference_framework="onnx",
                enable_speex_noise_suppression=True
            )
            logger.info(f"[VoiceLogic] Wake Word '{wake_word}' đã sẵn sàng!")

    async def start(self):
        if not settings.IP_WEBCAM_AUDIO_URL:
            return
        if self.is_running: return
        self.is_running = True
        
        # Chạy vòng lặp lắng nghe
        self._task = asyncio.create_task(self._listen_and_process())
        
        # Nạp model trong thread riêng
        await asyncio.to_thread(self.load_models)

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()

    async def _listen_and_process(self):
        """Vòng lặp chính: Quét Từ khóa -> Thu âm Lệnh -> Dịch Whisper."""
        
        # Bộ đệm cho openWakeWord (1280 samples mỗi lần predict)
        audio_buffer = np.array([], dtype=np.int16)
        
        # Pre-roll buffer: Lưu giữ khoảng 1.5 giây (12 chunks) âm thanh gần nhất
        pre_roll_buffer = deque(maxlen=12) 
        
        # Quản lý trạng thái
        collecting_command = False
        command_audio_chunks = []
        silence_count = 0
        
        logger.info("[VoiceLogic] Bắt đầu lắng nghe âm thanh...")

        while self.is_running:
            try:
                chunk = await voice_streamer_service.get_audio_chunk()
                pre_roll_buffer.append(chunk) # Luôn lưu vào pre-roll

                new_samples = np.frombuffer(chunk, dtype=np.int16)
                audio_buffer = np.append(audio_buffer, new_samples)

                # Chỉ quét từ khóa khi KHÔNG đang trong quá trình xử lý AI (để tiết kiệm CPU)
                if self.oww_model and not self.inferring and not collecting_command:
                    while len(audio_buffer) >= OWW_SAMPLES_PER_CHUNK:
                        oww_chunk = audio_buffer[:OWW_SAMPLES_PER_CHUNK]
                        audio_buffer = audio_buffer[OWW_SAMPLES_PER_CHUNK:]

                        prediction = self.oww_model.predict(oww_chunk)
                        
                        for model_name, score in prediction.items():
                            if score > 0.5: 
                                logger.info(f"[WakeWord] Nhận diện: '{model_name}'! (Score: {score:.2f})")
                                collecting_command = True
                                    # Lấy toàn bộ âm thanh trong pre-roll để làm phần đầu của lệnh
                                command_audio_chunks = list(pre_roll_buffer)
                                silence_count = 0

                # Thu thập đoạn lệnh
                if collecting_command:
                    command_audio_chunks.append(chunk)
                    
                    # Dùng RMS để biết khi nào người dùng nói xong
                    rms_volume = np.sqrt(np.mean(np.square(new_samples.astype(np.float32))))
                    if rms_volume < SILENCE_THRESHOLD:
                        silence_count += 1
                    else:
                        silence_count = 0
                    
                    # Dừng thu âm nếu im lặng lâu hoặc quá 10 giây
                    if silence_count > MIN_SILENCE_CHUNKS or len(command_audio_chunks) > 80:
                        collecting_command = False
                        logger.info(f"[VoiceLogic] Kết thúc lệnh. Đang gửi qua Whisper...")
                        # Gọi xử lý AI (không đợi để không chặn luồng nhận âm thanh)
                        asyncio.create_task(self._infer_audio(command_audio_chunks))
                        command_audio_chunks = []

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.is_running:
                    logger.error(f"[VoiceLogic] Lỗi vòng lặp: {e}")
                    await asyncio.sleep(1)

    async def _infer_audio(self, chunks_list):
        """Dịch âm thanh sang văn bản với khóa bảo vệ inferring."""
        if self.whisper_model is None or self.inferring:
            return

        self.inferring = True # Khóa AI lại
        try:
            raw_audio = b"".join(chunks_list)
            # Chuyển sang float32 [-1, 1] cho Whisper
            audio_np = np.frombuffer(raw_audio, np.int16).astype(np.float32) / 32768.0
            
            segments, info = await asyncio.to_thread(
                self.whisper_model.transcribe, 
                audio_np, 
                beam_size=1,            
                language="vi", 
                condition_on_previous_text=False,
                vad_filter=True
            )
            
            text = "".join([s.text for s in segments]).strip().lower()
            if not text:
                logger.info("[Whisper] Không nhận diện được nội dung.")
                return
                
            logger.info(f"[Whisper] Kết quả: '{text}'")
            
            # Thực thi lệnh qua Intent Service
            async with AsyncSessionLocal() as db:
                await process_voice_intent(db, text)
                    
        except Exception as e:
            logger.error(f"[VoiceLogic] Lỗi Whisper: {e}")
        finally:
            self.inferring = False # Luôn mở khóa sau khi xong (kể cả khi lỗi)

# Khởi tạo instance duy nhất
voice_logic_service = VoiceLogicService()
