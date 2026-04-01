from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/yolohome"
    SECRET_KEY: str = "multidisciplinaryproject"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DEBUG: bool = True
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    SETUP_CODE: str | None = None

    # Face recognition model paths (relative to container or absolute)
    ARCFACE_MODEL_PATH: str = "/models/arcface_resnet100.onnx"
    RETINAFACE_MODEL_PATH: str = "/models/det_10g.onnx"
    ANTISPOOF_MODEL_PATH: str = "/models/MiniFASNetV2.onnx"
    ANTISPOOF_SCALE: float = 2.7
    ANTISPOOF_THRESHOLD: float = 0.9
    FACE_MATCH_THRESHOLD: float = 0.4
    FACE_DETECTION_THRESHOLD: float = 0.7

    DEBUG: bool = True
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
