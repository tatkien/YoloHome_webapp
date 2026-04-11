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
    SECRET_KEY: str = "multidisciplinaryproject"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DEBUG: bool = True
    CORS_ORIGINS: str | list[str] = ["http://localhost:3000"]
    SETUP_CODE: str | None = None

    # Face recognition model paths (relative to container or absolute)
    ARCFACE_MODEL_PATH: str = "/models/arcface_resnet100.onnx"
    RETINAFACE_MODEL_PATH: str = "/models/det_10g.onnx"
    ANTISPOOF_MODEL_PATH: str = "/models/MiniFASNetV2.onnx"
    ANTISPOOF_SCALE: float = 2.7
    ANTISPOOF_THRESHOLD: float = 0.9
    FACE_MATCH_THRESHOLD: float = 0.4
    FACE_DETECTION_THRESHOLD: float = 0.7

    # --- HARDWARE SETTINGS ---
    # Auto-close delay for lock servo
    SERVO_AUTO_CLOSE_DELAY_MS: int = 5000 
    
    # Servo angle presets
    SERVO_OPEN_ANGLE: int = 90
    SERVO_CLOSE_ANGLE: int = 0

    # --- MQTT CONFIGURATION ---
    MQTT_BROKER_URL: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_KEEPALIVE: int = 60


    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

settings = Settings()
