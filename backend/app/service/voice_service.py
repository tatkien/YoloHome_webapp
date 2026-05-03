import asyncio
import logging
import numpy as np
import sentencepiece as spm
import sherpa_onnx
import webrtcvad
from collections import deque
from faster_whisper import WhisperModel

from sqlalchemy import select
from app.models.device import Device
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.service.ws_service import realtime_manager
from app.service.device_service import DeviceService
from app.service.voice_intent import voice_intent_service
from app.core.voice_stream import voice_streamer

logger = logging.getLogger("yolohome")

# 30ms, 16kHz = 960 bytes
MIN_SILENCE_CHUNKS = 50    # 1.5 giây im lặng -> ngắt lệnh
MAX_COMMAND_CHUNKS = 200   # Tối đa 6 giây thu âm lệnh
PRE_ROLL_CHUNKS = 20      # 0.6 giây pre-roll trước khi trigger wake word

# Từ khoá kích hoạt
WAKE_WORDS = settings.WAKE_WORDS

def _build_keywords_file() -> str:
    """
    Mã hoá WAKE_WORDS bằng BPE tokenizer rồi ghi ra custom_keywords.txt.
    """
    kws_dir = settings.KWS_MODEL_DIR
    bpe_model = f"{kws_dir}/bpe.model"
    keywords_txt = f"{kws_dir}/custom_keywords.txt"

    sp = spm.SentencePieceProcessor()
    sp.load(bpe_model)
    with open(keywords_txt, "w", encoding="utf-8") as f:
        for kw in WAKE_WORDS:
            pieces = sp.encode_as_pieces(kw.upper())
            line = " ".join(pieces)
            f.write(f"{line} :0.1\n")
            logger.info(f"[VoiceService] Keyword '{kw}' -> Tokens: {line} (Threshold: 0.1)")
    return keywords_txt


class VoiceService:
    """
    Pipeline nhận dạng giọng nói:
      1. Nhận audio PCM 16 kHz từ VoiceStreamer.
      2. Phát hiện từ khoá kích hoạt bằng Sherpa-ONNX Keyword Spotter 
      3. Thu âm và ngắt lệnh dựa theo VAD (WebRTC).
      4. Nhận dạng giọng nói tiếng Việt bằng Faster-Whisper.
      5. Gọi VoiceIntentService để thực thi lệnh điều khiển.
    """

    def __init__(self):
        self.whisper_model: WhisperModel | None = None
        self.kws_model:     sherpa_onnx.KeywordSpotter | None = None
        self.kws_stream = None
        self.vad = webrtcvad.Vad(3)
        self.is_running  = False
        self._task       = None
        self.inferring   = False        # Khóa tránh chạy song song nhiều Whisper
        self._vibe_counter = 0          
        self._current_status = "idle"   # trạng thái xử lý giọng nói
    
    async def _send_status(self, status: str, text: str = None):
        """Gửi trạng thái logic: idle, active, thinking, done"""
        self._current_status = status
        payload = {
            "event": "voice.status",
            "device_id": "SYS_MIC",
            "hardware_id": settings.SERVER_ID,
            "data": {
                "status": status,
                "text": text
            }
        }
        await realtime_manager.broadcast(payload)
        logger.info(f"[VoiceService] Status Change -> {status.upper()}")

    async def _sync_mic_status(self, is_on: bool):
        """Đồng bộ trạng thái thiết bị SYS_MIC lên hệ thống"""
        payload = {
            "pin": "SYS_MIC",
            "is_on": is_on,
            "value": 1023 if is_on else 0,
            "status": "success"
        }
        try:
            await DeviceService.process_state(settings.SERVER_ID, payload)
        except Exception as e:
            logger.error(f"[VoiceService] Lỗi đồng bộ Mic: {e}")

    async def _send_vibe(self, rms: float, is_collecting: bool):
        """Gửi dữ liệu âm lượng qua WebSocket"""
        # Chuyển RMS về thang 0-100
        vol_pc = min(int((rms / 2000) * 100), 100)
        
        payload = {
            "event": "voice.vibe",
            "hardware_id": settings.SERVER_ID,
            "data": {
                "volume": vol_pc,
                "is_collecting": is_collecting
            }
        }
        asyncio.create_task(realtime_manager.broadcast(payload))

    # Lifecycle

    async def start(self):
        if not settings.IP_WEBCAM_AUDIO_URL:
            logger.warning("[VoiceService] IP_WEBCAM_AUDIO_URL chưa cấu hình, bỏ qua.")
            return
        if self.is_running:
            return
        self.is_running = True
        
        # Bật luồng âm thanh
        await voice_streamer.start()       
        self._task = asyncio.create_task(self._listen_and_process())
        await asyncio.to_thread(self._load_models)

    async def stop(self):
        self.is_running = False
        # Tắt luồng âm thanh
        await voice_streamer.stop()
        await self._sync_mic_status(False)
        
        if self._task:
            self._task.cancel()

    # Model loading

    def _load_models(self):
        """Nạp Whisper và Sherpa-ONNX KWS. Chạy trong thread executor."""
        try:
            # 1. Whisper STT
            if self.whisper_model is None:
                logger.info("[VoiceService] Đang nạp Whisper 'base' (CPU / int8)...")
                self.whisper_model = WhisperModel(
                    "base", 
                    device="cpu", 
                    compute_type="int8",    
                    download_root=settings.WHISPER_MODEL_PATH
                )
                logger.info("[VoiceService] Whisper đã sẵn sàng.")

            # 2. Sherpa-ONNX Keyword
            if self.kws_model is None:
                logger.info("[VoiceService] Đang nạp Sherpa-ONNX Keyword Spotter...")
                keywords_file = _build_keywords_file()
                
                kws_dir = settings.KWS_MODEL_DIR
                # Khởi tạo cơ bản
                self.kws_model = sherpa_onnx.KeywordSpotter(
                    tokens=f"{kws_dir}/tokens.txt",
                    encoder=f"{kws_dir}/encoder-epoch-12-avg-2-chunk-16-left-64.onnx",
                    decoder=f"{kws_dir}/decoder-epoch-12-avg-2-chunk-16-left-64.onnx",
                    joiner=f"{kws_dir}/joiner-epoch-12-avg-2-chunk-16-left-64.onnx",
                    keywords_file=keywords_file,
                    num_threads=2,
                    provider="cpu",
                )
                self.kws_stream = self.kws_model.create_stream()
                logger.info(
                    f"[VoiceService] Wake Word Spotter đã sẵn sàng "
                    f"({len(WAKE_WORDS)} từ khoá: {WAKE_WORDS})"
                )
        except Exception:
            logger.exception("[VoiceService] Lỗi nạp mô hình.")

    def _process_kws_sync(self, audio_data: np.ndarray) -> str:
        """
        Hàm chạy đồng bộ để quét từ khóa.
        """
        if self.kws_model is None or self.kws_stream is None:
            return ""
            
        # Đẩy âm thanh vào stream
        self.kws_stream.accept_waveform(16000, audio_data)
        
        # Vòng lặp giải mã của Sherpa-ONNX
        while self.kws_model.is_ready(self.kws_stream):
            self.kws_model.decode_stream(self.kws_stream)
            
        # Trả về kết quả (hoặc chuỗi rỗng)
        return self.kws_model.get_result(self.kws_stream)

    # Main audio loop

    async def _listen_and_process(self):
        """
        Vòng lặp chính:
          - Chờ model load -> Quét wake word -> thu lệnh -> gửi Whisper.
        """
        pre_roll        = deque(maxlen=PRE_ROLL_CHUNKS)
        collecting      = False
        command_chunks  = []
        silence_count   = 0

        logger.info("[VoiceService] Bắt đầu lắng nghe âm thanh...")
        await self._send_status("idle")
        
        last_conn_state = False

        while self.is_running:
            try:
                # Theo dõi trạng thái kết nối từ Streamer
                try:
                    chunk = await asyncio.wait_for(voice_streamer.get_audio_chunk(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Timeout mà Streamer báo mất kết nối
                    if not voice_streamer.is_connected and last_conn_state:
                        last_conn_state = False
                        await self._sync_mic_status(False)
                    continue

                # Nếu có dữ liệu, kiểm tra xem có kết nối lại không
                if voice_streamer.is_connected and not last_conn_state:
                    last_conn_state = True
                    await self._sync_mic_status(True)
                pre_roll.append(chunk)
                samples = np.frombuffer(chunk, dtype=np.int16)
                
                # WebRTC VAD 30 ms 16000 Hz
                is_speech = False
                if len(chunk) == 960:
                    is_speech = self.vad.is_speech(chunk, 16000)

                # Gửi RMS qua WebSocket
                self._vibe_counter += 1
                if self._vibe_counter % 6 == 0:
                    rms = np.sqrt(np.mean(np.square(samples.astype(np.float32))))
                    await self._send_vibe(rms, collecting)

                if self.kws_model is None or self.kws_stream is None: continue

                # Wake word detection
                if not self.inferring and not collecting:
                    audio_float = samples.astype(np.float32) / 32768.0 
                    # Chạy quét từ khóa
                    result = await asyncio.to_thread(self._process_kws_sync, audio_float)
                    if result:
                        logger.info(f"[WakeWord] Phát hiện: '{result.strip()}'")
                        collecting     = True
                        command_chunks = list(pre_roll)
                        self.kws_model.reset_stream(self.kws_stream) 
                        await self._send_status("active")

                elif collecting:
                    command_chunks.append(chunk) 
                    if is_speech:
                        silence_count = 0
                    else:
                        silence_count += 1
                        
                    # Nếu im lặng lâu hoặc lệnh quá dài
                    if silence_count >= MIN_SILENCE_CHUNKS or len(command_chunks) >= MAX_COMMAND_CHUNKS:
                        logger.info(f"[VoiceService] Đã thu xong lệnh ({len(command_chunks)} chunks).")
                        collecting = False
                        await self._send_status("thinking")
                        asyncio.create_task(self._infer_audio(command_chunks))
                        command_chunks = []

            except asyncio.CancelledError:
                break
            except Exception:
                if self.is_running:
                    logger.exception("[VoiceService] Lỗi vòng lặp audio.")
                    await asyncio.sleep(1)

    # Whisper inference

    async def _get_voice_prompt(self) -> str:
        """
        Tự động tạo chuỗi 'mồi' (initial_prompt) dựa trên dữ liệu thiết bị thực tế.
        """
        base_keywords = [
            "bật", "tắt", "mở", "đóng", "tăng", "giảm", "mức", "đèn", "quạt",
            "một", "hai", "ba", "không"
        ]
        
        try:
            if not voice_intent_service.is_ready:
                async with AsyncSessionLocal() as db:
                    await voice_intent_service.reload_cache(db)
            
            # Tuple: kw_goc, kw_khu_dau, dict_data
            device_keywords = set()
            for kw_goc, _, _ in voice_intent_service._device_cache:
                device_keywords.add(kw_goc)
            
            # Gộp lại thành một chuỗi mồi
            full_prompt = ", ".join(list(device_keywords) + base_keywords)
            
            logger.debug(f"[VoiceService] Whisper prompt: {full_prompt}")
            return full_prompt
            
        except Exception as e:
            logger.error(f"[VoiceService] Lỗi tạo prompt từ Cache: {e}")
            return ", ".join(base_keywords)

    async def _infer_audio(self, chunks: list[bytes]):
        """Chuyển audio -> text -> intent. Có khóa để tránh chạy song song."""
        if self.whisper_model is None or self.inferring:
            return
        self.inferring = True
        try:
            raw   = b"".join(chunks)
            audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
            
            # Lấy danh sách từ khóa mồi cho Whisper
            prompt = await self._get_voice_prompt()       
            segments, _ = await asyncio.to_thread(
                self.whisper_model.transcribe,
                audio,
                initial_prompt=prompt,
                beam_size=2,
                language="vi",
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=1000),
            )
            text_found = "".join(s.text for s in segments).strip().lower()
            if text_found:
                logger.info(f"[Whisper] Kết quả: '{text_found}'")
                await self._send_status("done", text=text_found)
                async with AsyncSessionLocal() as db:
                    success = await voice_intent_service.process_voice_intent(db, text_found)   
                    if success:
                        logger.info("[VoiceService] Đã thực thi lệnh nói thành công.")
                    else:
                        logger.warning("[VoiceService] Không thể phân tích hoặc thực thi lệnh nói này.")
                await asyncio.sleep(2)
            else:
                logger.info("[Whisper] Không ra chữ.")
        except Exception as e:
            logger.error(f"[VoiceService] Lỗi Whisper inference: {e}")
        finally:
            self.inferring = False
            if self.is_running:
                await self._send_status("idle")

# Singleton
voice_service = VoiceService()
