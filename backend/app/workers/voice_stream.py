import asyncio
import logging
import subprocess
from app.core.config import settings

logger = logging.getLogger("yolohome")

class VoiceStreamer:
    def __init__(self):
        """
        Khởi tạo bộ thu luồng âm thanh dạng vòng lặp.
        - `audio_queue`: Hàng đợi chứa các chunk âm thanh để module STT/VAD lấy nhận diện
        """
        self.stream_url = settings.IP_WEBCAM_AUDIO_URL
        
        self.is_running = False
        self.audio_queue = asyncio.Queue(maxsize=1000) 

    async def start(self):
        if self.is_running:
            return
            
        if not self.stream_url:
            logger.warning("[VoiceStreamer] Chưa cấu hình biến môi trường 'IP_WEBCAM_AUDIO_URL'.")
            return
            
        self.is_running = True
        self._task = asyncio.create_task(self._listen_to_stream())
        logger.info(f"[VoiceStreamer] Đã kích hoạt service lắng nghe âm thanh. Target: {self.stream_url}")

    async def stop(self):
        self.is_running = False
        if hasattr(self, '_process') and self._process.returncode is None:
            try:
                self._process.terminate()
                await self._process.wait() 
            except Exception:
                pass
        if self._task:
            self._task.cancel()
        logger.info("[VoiceStreamer] Service thu âm thanh đã tắt.")
            
    async def get_audio_chunk(self):
        """Hàm nhận diện Whisper để lấy dữ liệu ra để khử nhạy (VAD)"""
        return await self.audio_queue.get()

    async def _listen_to_stream(self):
        # Xử lý kết nối HTTP Audio và chia chunk.
        while self.is_running:
            try:
                if self.stream_url:
                    # Chạy FFmpeg dưới dạng tiến trình con
                    logger.info(f"[VoiceStreamer] FFmpeg đang kết nối đến {self.stream_url}...")
                    
                    # Đọc input HTTP -> xuất Raw định dạng 16-bit PCM, Rate 16000Hz, 1 kênh
                    process = await asyncio.create_subprocess_exec(
                        'ffmpeg', 
                        '-i', self.stream_url, 
                        '-f', 's16le', 
                        '-acodec', 'pcm_s16le', 
                        '-ac', '1', 
                        '-ar', '16000', 
                        '-',  # Xuất ra Pipe/Stdout
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    self._process = process
                    async def watch_errors(stderr_stream):
                        while True:
                            line = await stderr_stream.readline()
                            if not line:
                                break
                            error_msg = line.decode().strip()
                            # Không gây nhầm lẫn là lỗi hệ thống
                            logger.debug(f"[FFmpeg-Stderr] {error_msg}")

                    # Kích hoạt task đọc lỗi
                    error_task = asyncio.create_task(watch_errors(process.stderr))
                    
                    # Vòng lặp nhận dữ liệu PCM sạch
                    while self.is_running:
                        chunk = await process.stdout.read(4096)
                        if chunk:
                            # logger.debug(f"Đã nhận chunk: {len(chunk)} bytes") # Thêm dòng này để test
                            if self.audio_queue.full():
                                await self.audio_queue.get() 
                            await self.audio_queue.put(chunk)
                        if not chunk:
                            # Nếu đứt luồng
                            break
                        
                        if self.audio_queue.full():
                            await self.audio_queue.get() 
                        await self.audio_queue.put(chunk)
                        
                    # Dọn dẹp process khi đứt luồng
                    try:
                        if process.returncode is None:
                            process.terminate()
                    except Exception:
                        pass
                    
                    if self.is_running:
                        logger.warning("[VoiceStreamer] Luồng FFmpeg bị ngắt, chuẩn bị kết nối lại...")
                        await asyncio.sleep(3)
            except asyncio.CancelledError:
                logger.info("[VoiceStreamer] Vòng lặp thu Audio đã bị huỷ.")
                break
            except Exception as e:
                logger.error(f"[VoiceStreamer] Rớt luồng kết nối âm thanh (IP Webcam tắt?): {e}")
                await asyncio.sleep(5)

# Khởi tạo instance
voice_streamer_service = VoiceStreamer()
