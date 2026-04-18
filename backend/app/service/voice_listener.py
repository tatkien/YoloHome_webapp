import asyncio
import logging
import re
import threading
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np
import sqlalchemy as sa

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.device import Device, DeviceTypeEnum
from app.schemas.device import DeviceControlRequest
from app.service.history import add_history_record
from app.service.mqtt import mqtt_service

logger = logging.getLogger(__name__)


class VoiceCommandListener:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        try:
            import webrtcvad
            from faster_whisper import WhisperModel
            from pvporcupine import create as create_porcupine
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Voice dependencies are not fully installed. "
                "Required: pvporcupine, faster-whisper, webrtcvad-wheels, requests."
            ) from exc

        self.loop = loop
        self.mode = "WAIT"
        self.audio_buffer: deque[int] = deque()
        self.silence_counter = 0

        self.porcupine = create_porcupine(
            access_key=settings.VOICE_ACCESS_KEY,
            keywords=["hey google"],
        )
        self.model = WhisperModel(
            settings.VOICE_WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
        )
        self.vad = webrtcvad.Vad(settings.VOICE_VAD_AGGRESSIVENESS)

        self.samplerate = settings.VOICE_SAMPLERATE
        self.porcupine_frame = self.porcupine.frame_length
        self.vad_frame = int(self.samplerate * 30 / 1000)

    @staticmethod
    def clean_text(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def detect_intent(text: str) -> Optional[str]:
        if any(x in text for x in ["fan on", "turn on fan", "turn fan on"]):
            return "FAN_ON"
        if any(x in text for x in ["fan off", "turn off fan", "turn fan off"]):
            return "FAN_OFF"
        if any(x in text for x in ["light on", "turn on light", "turn light on"]):
            return "LIGHT_ON"
        if any(x in text for x in ["light off", "turn off light", "turn light off"]):
            return "LIGHT_OFF"
        return None

    @staticmethod
    def is_exit_command(text: str) -> bool:
        return any(x in text for x in ["goodbye", "good bye"])

    async def _find_default_device(self, device_type: DeviceTypeEnum) -> Optional[Device]:
        async with AsyncSessionLocal() as db:
            stmt = (
                sa.select(Device)
                .where(Device.type == device_type)
                .order_by(Device.created_at.asc())
                .limit(1)
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def _execute_intent(self, intent: str, spoken_text: str) -> None:
        if intent in ("FAN_ON", "FAN_OFF"):
            target_type = DeviceTypeEnum.FAN
            is_on = intent == "FAN_ON"
        elif intent in ("LIGHT_ON", "LIGHT_OFF"):
            target_type = DeviceTypeEnum.LIGHT
            is_on = intent == "LIGHT_ON"
        else:
            logger.info("Voice intent not supported: %s", intent)
            return

        device = await self._find_default_device(target_type)
        if not device:
            logger.warning("No %s device found for voice command", target_type.value)
            return

        if not device.hardware_id or not device.pin:
            logger.warning("Device %s does not have hardware linkage", device.id)
            return

        payload = DeviceControlRequest(is_on=is_on, value=1 if is_on else 0)
        await mqtt_service.publish_command(
            hardware_id=device.hardware_id,
            pin=device.pin,
            payload=payload,
        )

        await add_history_record(
            device_id=device.id,
            device_name=device.name,
            action=f"Voice command {intent} (text='{spoken_text}')",
            actor="system",
            source="Voice Command",
        )

        logger.info(
            "Voice command queued: %s -> device=%s hardware=%s pin=%s",
            intent,
            device.id,
            device.hardware_id,
            device.pin,
        )

    def _process_command(self) -> None:
        if not self.audio_buffer:
            return

        audio = np.array(self.audio_buffer, dtype=np.float32) / 32768.0
        segments, _ = self.model.transcribe(
            audio,
            initial_prompt="fan on fan off light on light off",
        )
        raw_text = " ".join(seg.text for seg in segments)
        text = self.clean_text(raw_text)

        if not text:
            logger.info("Voice transcript empty")
            return

        logger.info("Voice transcript: %s", text)

        if self.is_exit_command(text):
            self.mode = "WAIT"
            logger.info("Voice listener switched to WAIT mode")
            return

        intent = self.detect_intent(text)
        if not intent:
            logger.info("No known intent detected from transcript")
            return

        future = asyncio.run_coroutine_threadsafe(self._execute_intent(intent, text), self.loop)
        try:
            future.result(timeout=10)
        except Exception as exc:
            logger.exception("Voice intent execution failed: %s", exc)

    def run(self, stop_flag: threading.Event) -> None:
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            raise RuntimeError(
                "sounddevice/PortAudio is not available. Install PortAudio in the runtime environment."
            ) from exc

        try:
            devices = sd.query_devices()
        except Exception as exc:
            raise RuntimeError(f"Unable to query audio devices: {exc}") from exc

        input_device_indexes = [
            idx for idx, dev in enumerate(devices) if dev.get("max_input_channels", 0) > 0
        ]
        if not input_device_indexes:
            raise RuntimeError("No input audio device available in current runtime")

        selected_device = settings.VOICE_DEVICE_INDEX
        if selected_device is None:
            selected_device = input_device_indexes[0]

        if selected_device not in input_device_indexes:
            raise RuntimeError(
                f"Selected VOICE_DEVICE_INDEX={selected_device} is invalid. "
                f"Available input device indexes: {input_device_indexes}"
            )

        logger.info(
            "Voice listener started on input device index %s and waiting for wake word",
            selected_device,
        )

        def audio_callback(indata, frames, callback_time, status):
            del frames, callback_time
            if status:
                logger.warning("Audio callback status: %s", status)

            pcm = np.frombuffer(indata, dtype=np.int16)

            if self.mode == "WAIT":
                if len(pcm) == self.porcupine_frame:
                    result = self.porcupine.process(pcm)
                    if result >= 0:
                        self.mode = "LISTEN"
                        self.audio_buffer.clear()
                        self.silence_counter = 0
                        logger.info("Wake word detected, entering LISTEN mode")
                return

            for i in range(0, len(pcm), self.vad_frame):
                frame = pcm[i : i + self.vad_frame]
                if len(frame) < self.vad_frame:
                    continue

                is_speech = self.vad.is_speech(frame.tobytes(), self.samplerate)
                if is_speech:
                    self.audio_buffer.extend(frame)
                    self.silence_counter = 0
                else:
                    self.silence_counter += 1

                if self.silence_counter > settings.VOICE_SILENCE_LIMIT and self.audio_buffer:
                    self._process_command()
                    self.audio_buffer.clear()
                    self.silence_counter = 0
                    break

        try:
            with sd.RawInputStream(
                device=selected_device,
                samplerate=self.porcupine.sample_rate,
                blocksize=self.porcupine_frame,
                dtype="int16",
                channels=1,
                callback=audio_callback,
            ):
                while not stop_flag.is_set():
                    stop_flag.wait(0.1)
        except Exception as exc:
            raise RuntimeError(f"Unable to open audio input stream: {exc}") from exc

    def close(self) -> None:
        if self.porcupine:
            self.porcupine.delete()


async def run_voice_listener(stop_event: asyncio.Event) -> None:
    if not settings.VOICE_ENABLED:
        logger.info("Voice listener disabled by VOICE_ENABLED")
        return

    if not settings.VOICE_ACCESS_KEY:
        logger.warning("Voice listener disabled: VOICE_ACCESS_KEY is missing")
        return

    keyword_path = Path(settings.VOICE_KEYWORD_PATH)
    if not keyword_path.exists():
        logger.warning("Voice listener disabled: keyword file not found at %s", keyword_path)
        return

    loop = asyncio.get_running_loop()

    while not stop_event.is_set():
        stop_flag = threading.Event()

        async def bridge_stop() -> None:
            await stop_event.wait()
            stop_flag.set()

        bridge_task = asyncio.create_task(bridge_stop())
        listener: Optional[VoiceCommandListener] = None

        try:
            listener = VoiceCommandListener(loop)
            await asyncio.to_thread(listener.run, stop_flag)
        except Exception as exc:
            message = str(exc)
            if "ActivationLimitError" in message or "PorcupineActivationLimitError" in message:
                logger.error(
                    "Voice listener disabled: Picovoice activation limit reached for current access key. "
                    "Use a valid key with available quota or disable voice temporarily."
                )
                return
            if (
                "No input audio device available" in message
                or "Unable to open audio input stream" in message
                or "Unable to query audio devices" in message
                or "Error querying device" in message
            ):
                logger.error("Voice listener disabled: %s", message)
                return
            # Porcupine keyword files are platform-specific. If a mismatched .ppn is used
            # (e.g., Windows keyword in Linux container), disable voice worker gracefully.
            if "belongs to a different platform" in message or "Loading keyword file" in message:
                logger.error(
                    "Voice listener disabled: keyword file at %s is not compatible with this platform. "
                    "Provide a Linux-compatible .ppn file and set VOICE_KEYWORD_PATH accordingly.",
                    settings.VOICE_KEYWORD_PATH,
                )
                return
            logger.exception("Voice listener crashed. Retrying in 3s: %s", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3)
            except TimeoutError:
                pass
        finally:
            stop_flag.set()
            if listener:
                listener.close()
            bridge_task.cancel()
            try:
                await bridge_task
            except asyncio.CancelledError:
                pass
