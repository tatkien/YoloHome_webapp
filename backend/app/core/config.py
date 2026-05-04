from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_root_env_file() -> str | None:
    # Walk up from this file to locate the single project-level .env.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.exists():
            return str(candidate)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_find_root_env_file(), extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/yolohome"
    SECRET_KEY: str = "multidisciplinaryproject"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DEBUG: bool = True
    ADMIN_RESET_MODE: bool = False
    CORS_ORIGINS: str | list[str] = ["http://localhost:3000"]
    SETUP_CODE: str | None = None

    # Face recognition model paths (relative to container or absolute)
    ARCFACE_MODEL_PATH: str = "/models/face/arcface_resnet100.onnx"
    RETINAFACE_MODEL_PATH: str = "/models/face/det_10g.onnx"
    ANTISPOOF_MODEL_PATH: str = "/models/face/MiniFASNetV2.onnx"
    ANTISPOOF_SCALE: float = 2.7
    ANTISPOOF_THRESHOLD: float = 0.9
    FACE_MATCH_THRESHOLD: float = 0.4
    FACE_DETECTION_THRESHOLD: float = 0.7

    # --- HARDWARE SETTINGS ---
    # Auto-close delay for lock servo
    SERVO_AUTO_CLOSE_DELAY_MS: int = 5000 

    # Server ID
    SERVER_ID: str = "SERVER_NODE"

    DEFAULT_DEVICE_METADATA: dict[str, dict] = {
        "fan": {"default_value": 1.0, "range": [0, 3], "unit": "speed"},
        "light": {"default_value": 1023.0, "range": [0, 1023], "unit": "brightness"},
        "lock": {"default_value": 90.0, "range": [0, 90], "unit": "degree"},
        "camera": {"default_value": 1.0, "range": [0, 1], "unit": "state"},
        "mic": {"default_value": 1.0, "range": [0, 1], "unit": "state"},
        "temp_sensor": {"default_value": 0.0, "range": [-40, 80], "unit": "°C"},
        "humidity_sensor": {"default_value": 0.0, "range": [0, 100], "unit": "%"}
    }

    # --- VOICE CONTROL ---
    IP_WEBCAM_AUDIO_URL: str | None = None
    WHISPER_MODEL_PATH: str = "/models/voice/whisper"
    KWS_MODEL_DIR: str = "/models/voice/kws/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"
    WAKE_WORDS: str | list[str] = ["hey computer", "super hero", "go home", "hi home"]

    # --- RETENTION SETTINGS ---
    SENSOR_RETENTION_DAYS: int = 30       
    DEVICE_LOG_RETENTION_DAYS: int = 14  
    LOG_RETENTION_DAYS: int = 14        
    FACE_LOG_RETENTION_DAYS: int = 7    


    # --- MQTT CONFIGURATION ---
    MQTT_BROKER_URL: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_KEEPALIVE: int = 60

    # --- WEBSOCKET CONFIGURATION ---
    WS_IDLE_TIMEOUT_SECONDS: int = 60


    @field_validator("CORS_ORIGINS", "WAKE_WORDS", mode="before")
    @classmethod
    def parse_comma_separated_list(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

settings = Settings()
