import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.service.mqtt import mqtt_service
from app.core.config import settings
from app.service.face_service import get_face_service
from app.workers.scheduler import start_scheduler, stop_scheduler
from app.core.voice_stream import voice_streamer
from app.service.voice_service import voice_service
from app.db.init_db import handle_admin_reset
from app.core.logger import logger, logging_middleware
from app.service.system_node import setup_system_node


# Ensure application module logs emit records.
logger.setLevel(logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kiểm tra reset Admin
    await handle_admin_reset()
    # Khởi tạo Server Node
    await setup_system_node()
    # Khởi tạo Face Service
    get_face_service()
    # Chạy MQTT
    mqtt_task = asyncio.create_task(mqtt_service.connect_and_subscribe())
    # Chạy APScheduler
    await start_scheduler()
    # Chạy Voice Services
    logic_task = asyncio.create_task(voice_service.start())
    try:
        yield
    finally:
        logger.info("Đang tắt server, dọn dẹp tài nguyên...")
        await stop_scheduler()
        await voice_service.stop()
        await voice_streamer.stop()
        mqtt_task.cancel()
        try:
            await mqtt_task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title="YoloHome API",
    version="0.0.1",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(logging_middleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
