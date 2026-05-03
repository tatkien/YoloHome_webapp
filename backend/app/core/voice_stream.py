import asyncio
import logging
from app.core.config import settings

logger = logging.getLogger("yolohome")

class VoiceStreamer:
    """
    Duy trì luồng dữ liệu âm thanh liên tục từ mic ngoài.
    Luồng: [IP Mic] --(HTTP dạng .wav)--> [FFmpeg] --(Raw PCM)--> [Async Queue]
    """
    def __init__(self):
        self.stream_url = settings.IP_WEBCAM_AUDIO_URL
        self.is_running = False
        self.audio_queue = asyncio.Queue(maxsize=400)
        self.is_connected = False
        self._task = None
        self._process = None 

    async def start(self):
        if self.is_running or not self.stream_url:
            return
            
        self.is_running = True
        self._task = asyncio.create_task(self._listen_to_stream())
        logger.info(f"[VoiceStreamer] Đã kích hoạt service lắng nghe âm thanh. Target: {self.stream_url}")

    async def stop(self):
        self.is_running = False
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=2.0) 
            except Exception:
                if self._process: self._process.kill()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[VoiceStreamer] Service thu âm thanh đã tắt.")
            
    async def get_audio_chunk(self):
        """
        Cung cấp dữ liệu cho VoiceLogicService. 
        Hàm này await cho đến khi có dữ liệu mới trong queue.
        """
        return await self.audio_queue.get()
    
    async def _watch_ffmpeg_errors(self, stderr_stream):
        """Đọc log từ FFmpeg khi cần thiết."""
        try:
            while True:
                line = await stderr_stream.readline()
                if not line:
                    break
                logger.debug(f"[FFmpeg-Stderr] {line.decode().strip()}")
        except asyncio.CancelledError:
            pass

    async def _listen_to_stream(self):
        """
        Dùng FFmpeg để chuyển đổi luồng âm thanh thành dạng số (PCM) và chia chunk.
        """
        while self.is_running:
            error_task = None
            try:
                if not self.stream_url:
                    break

                logger.info(f"[VoiceStreamer] FFmpeg đang kết nối đến {self.stream_url}...")   
                # Đọc input HTTP -> xuất Raw định dạng 16-bit PCM, Rate 16000Hz, 1 kênh
                self._process = await asyncio.create_subprocess_exec(
                    'ffmpeg', 
                    '-i', self.stream_url,
                    '-f', 's16le',
                    '-acodec', 'pcm_s16le', 
                    '-ac', '1',
                    '-ar', '16000',
                    '-loglevel', 'quiet',
                    '-',  # Xuất ra Pipe/Stdout
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # Kích hoạt task đọc lỗi
                error_task = asyncio.create_task(self._watch_ffmpeg_errors(self._process.stderr))
                first_chunk = True
                chunk_count = 0
                    
                # Vòng lặp nhận dữ liệu PCM từ FFmpeg
                # Tần số 16kHz, 16-bit mono, 30ms = 480 samples = 960 bytes.
                CHUNK_SIZE = 960 
                while self.is_running:
                    chunk = await self._process.stdout.read(CHUNK_SIZE)
                    if not chunk:
                        logger.warning("[VoiceStreamer] Luồng dữ liệu trống (End of Stream).")
                        break

                    if first_chunk:
                        logger.info("[VoiceStreamer] Status: Ok. Đã nhận được dữ liệu âm thanh đầu tiên")
                        self.is_connected = True
                        first_chunk = False

                    # Đẩy vào queue, nếu đầy xóa bớt chunk cũ nhất
                    if self.audio_queue.full():
                        logger.debug("[VoiceStreamer] Queue đầy, tự động dọn dẹp...")
                        try: 
                            self.audio_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass

                    await self.audio_queue.put(chunk)
                    chunk_count += 1
                    if chunk_count % 100 == 0:
                        queue_usage = (self.audio_queue.qsize() / self.audio_queue._maxsize) * 100
                        if queue_usage > 10: 
                            logger.warning(f"[VoiceStreamer] Status: Latency tăng, queue ({queue_usage:.0f}%)")
                        elif chunk_count % 2000 == 0:
                            logger.info(f"[VoiceStreamer] Status: Ok. Đã xử lý {chunk_count} chunks")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[VoiceStreamer] Lỗi kết nối âm thanh {e}")
            
            finally:
                # Dọn dẹp process và task log cũ
                if error_task:
                    error_task.cancel()
                self.is_connected = False
                if self._process and self._process.returncode is None:
                    try:
                        self._process.terminate()
                    except:
                        pass
                self._process = None
            
            if self.is_running:
                    logger.warning("[VoiceStreamer] Thử lại sau 3 giây...")
                    await asyncio.sleep(3)
        logger.info("[VoiceStreamer] Vòng lặp thu Audio đã kết thúc.")

# Khởi tạo instance
voice_streamer = VoiceStreamer()
