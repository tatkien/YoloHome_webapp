import asyncio
import base64
import logging
import os
import re
import tempfile
from dataclasses import dataclass

import sqlalchemy as sa

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.device import Device, DeviceTypeEnum
from app.realtime.websocket_manager import realtime_manager
from app.schemas.device import DeviceControlRequest
from app.service.history import add_history_record
from app.service.mqtt import mqtt_service

logger = logging.getLogger(__name__)

VOICE_PROCESSING_TIMEOUT_SECONDS = 3.0


@dataclass
class VoiceSessionState:
    active: bool = False
    awakened: bool = False
    processing: bool = False


class VoiceWebSocketProcessor:
    def __init__(self):
        try:
            from faster_whisper import WhisperModel
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Voice dependencies are not fully installed. Required: faster-whisper, requests."
            ) from exc

        self.model = WhisperModel(
            settings.VOICE_WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
        )
        self.wake_phrases = [
            p.strip().lower() for p in settings.VOICE_WAKE_PHRASES.split(",") if p.strip()
        ] or ["hey yolo", "hi yolo"]
        self.wake_prompt = "hey yolo hi yolo wake word"
        self.sessions: dict[int, VoiceSessionState] = {}

    @staticmethod
    def clean_text(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def detect_intent(text: str) -> str | None:
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

    async def start_session(self, user_id: int) -> None:
        state = self.sessions.get(user_id) or VoiceSessionState()
        state.active = True
        state.awakened = False
        state.processing = False
        self.sessions[user_id] = state
        await realtime_manager.send_to_user(user_id, {
            "event": "voice_status",
            "data": {"status": "waiting_wake_phrase"},
        })

    async def stop_session(self, user_id: int) -> None:
        state = self.sessions.get(user_id)
        if state:
            state.active = False
            state.awakened = False
            state.processing = False
        await realtime_manager.send_to_user(user_id, {
            "event": "voice_status",
            "data": {"status": "stopped"},
        })

    async def _find_default_device(self, device_type: DeviceTypeEnum) -> Device | None:
        async with AsyncSessionLocal() as db:
            stmt = (
                sa.select(Device)
                .where(Device.type == device_type)
                .order_by(Device.created_at.asc())
                .limit(1)
            )
            result = await db.execute(stmt)
            return result.scalars().first()

    async def _execute_intent(self, user_id: int, intent: str, spoken_text: str) -> None:
        if intent in ("FAN_ON", "FAN_OFF"):
            target_type = DeviceTypeEnum.FAN
            is_on = intent == "FAN_ON"
        elif intent in ("LIGHT_ON", "LIGHT_OFF"):
            target_type = DeviceTypeEnum.LIGHT
            is_on = intent == "LIGHT_ON"
        else:
            return

        device = await self._find_default_device(target_type)
        if not device or not device.hardware_id or not device.pin:
            await realtime_manager.send_to_user(user_id, {
                "event": "voice_error",
                "data": {"message": f"No available {target_type.value} device to control."},
            })
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
            actor=f"user:{user_id}",
            source="Voice Command",
        )

        await realtime_manager.send_to_user(user_id, {
            "event": "voice_intent",
            "data": {"intent": intent, "text": spoken_text},
        })

    async def process_chunk(self, user_id: int, audio_base64: str, mime_type: str | None = None) -> None:
        state = self.sessions.get(user_id)
        if not state or not state.active:
            logger.info("[VOICE][user:%s] Chunk ignored: session inactive", user_id)
        elif state.processing:
            logger.info("[VOICE][user:%s] Chunk ignored: processing in progress", user_id)
        else:
            logger.info("[VOICE][user:%s] Recording...", user_id)

            idle_status = "listening_command" if state.awakened else "waiting_wake_phrase"
            can_transcribe = True
            chunk_bytes = b""
            raw_text = ""
            text = ""

            try:
                chunk_bytes = base64.b64decode(audio_base64)
            except Exception:
                can_transcribe = False
                await realtime_manager.send_to_user(user_id, {
                    "event": "voice_error",
                    "data": {"message": "Invalid audio chunk payload."},
                })

            if can_transcribe and len(chunk_bytes) < 1024:
                can_transcribe = False
                logger.info("[VOICE][user:%s] Chunk ignored: too small (%s bytes)", user_id, len(chunk_bytes))

            if can_transcribe:
                state.processing = True
                try:
                    await realtime_manager.send_to_user(user_id, {
                        "event": "voice_status",
                        "data": {"status": "processing"},
                    })
                    await realtime_manager.send_to_user(user_id, {
                        "event": "voice_log",
                        "data": {"message": "Da nhan duoc voice, dang xu ly..."},
                    })

                    try:
                        transcribe_prompt = self.wake_prompt if not state.awakened else settings.VOICE_INITIAL_PROMPT
                        raw_text, text = await asyncio.wait_for(
                            asyncio.to_thread(
                                self._transcribe_bytes_sync,
                                chunk_bytes,
                                mime_type or "audio/webm",
                                transcribe_prompt,
                            ),
                            timeout=VOICE_PROCESSING_TIMEOUT_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "[VOICE][user:%s] Processing timeout after %.1fs. Skip chunk.",
                            user_id,
                            VOICE_PROCESSING_TIMEOUT_SECONDS,
                        )
                        await realtime_manager.send_to_user(user_id, {
                            "event": "voice_log",
                            "data": {"message": "Xu ly qua 2 giay. Bo qua chunk va tiep tuc nghe."},
                        })
                        await realtime_manager.send_to_user(user_id, {
                            "event": "voice_status",
                            "data": {"status": idle_status},
                        })
                        return
                    except Exception as exc:
                        # Some chunks are not decodable yet; wait for next chunk instead of breaking the flow.
                        logger.debug("Voice chunk not decodable yet: %s", exc)
                        text = ""

                    raw_text = (raw_text or "").strip()
                    if raw_text:
                        logger.info("[VOICE][user:%s] RAW: %s", user_id, raw_text)
                    logger.info("[VOICE][user:%s] CLEAN: %s", user_id, text or "-")

                    if text:
                        await realtime_manager.send_to_user(user_id, {
                            "event": "voice_transcript",
                            "data": {"text": text},
                        })

                        if not state.awakened:
                            if any(phrase in text for phrase in self.wake_phrases):
                                state.awakened = True
                                logger.info("[VOICE][user:%s] >>> START LISTENING", user_id)
                                await realtime_manager.send_to_user(user_id, {
                                    "event": "voice_log",
                                    "data": {"message": "Wake word hop le. Chuyen sang Listening Command."},
                                })
                                await realtime_manager.send_to_user(user_id, {
                                    "event": "voice_status",
                                    "data": {"status": "listening_command"},
                                })
                            else:
                                await realtime_manager.send_to_user(user_id, {
                                    "event": "voice_log",
                                    "data": {"message": "Khong khop wake word. Quay ve Waiting hey yolo."},
                                })
                                await realtime_manager.send_to_user(user_id, {
                                    "event": "voice_status",
                                    "data": {"status": "waiting_wake_phrase"},
                                })
                        else:
                            if self.is_exit_command(text):
                                state.awakened = False
                                logger.info("[VOICE][user:%s] >>> STOP LISTENING", user_id)
                                await realtime_manager.send_to_user(user_id, {
                                    "event": "voice_log",
                                    "data": {"message": "Nhan goodbye. Quay ve Waiting hey yolo."},
                                })
                                await realtime_manager.send_to_user(user_id, {
                                    "event": "voice_status",
                                    "data": {"status": "waiting_wake_phrase"},
                                })
                            else:
                                intent = self.detect_intent(text)
                                if intent:
                                    logger.info("[VOICE][user:%s] >>> INTENT: %s", user_id, intent)
                                    await self._execute_intent(user_id, intent, text)
                                    await realtime_manager.send_to_user(user_id, {
                                        "event": "voice_log",
                                        "data": {"message": f"Da thuc thi lenh: {intent}"},
                                    })
                                else:
                                    await realtime_manager.send_to_user(user_id, {
                                        "event": "voice_log",
                                        "data": {"message": "Khong nhan ra lenh. Van o Listening Command."},
                                    })

                                await realtime_manager.send_to_user(user_id, {
                                    "event": "voice_status",
                                    "data": {"status": "listening_command"},
                                })
                    else:
                        await realtime_manager.send_to_user(user_id, {
                            "event": "voice_status",
                            "data": {"status": idle_status},
                        })
                finally:
                    state.processing = False

    def _transcribe_bytes_sync(self, chunk_bytes: bytes, mime_type: str, prompt: str) -> tuple[str, str]:
        suffix = ".webm" if "webm" in mime_type else ".wav"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                f.write(chunk_bytes)
                temp_path = f.name

            segments, _ = self.model.transcribe(
                temp_path,
                initial_prompt=prompt,
            )
            raw = " ".join(seg.text for seg in segments)
            cleaned = self.clean_text(raw)
            return raw, cleaned
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


_voice_ws_processor: VoiceWebSocketProcessor | None = None


def get_voice_ws_processor() -> VoiceWebSocketProcessor:
    global _voice_ws_processor
    if _voice_ws_processor is None:
        _voice_ws_processor = VoiceWebSocketProcessor()
    return _voice_ws_processor


async def run_voice_listener(stop_event: asyncio.Event) -> None:
    if not settings.VOICE_ENABLED:
        logger.info("Voice listener disabled by VOICE_ENABLED")
        return

    logger.info("Voice listener initialized in websocket mode")
    await stop_event.wait()
