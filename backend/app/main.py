import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.service.mqtt import mqtt_service
from app.core.config import settings
from app.ai.face_service import get_face_service
from app.realtime.scheduler import run_device_schedule_loop
from app.realtime.voice_stream import voice_streamer_service
from app.ai.voice_logic import voice_logic_service
from app.service.maintenance import handle_admin_reset
from app.db.session import AsyncSessionLocal
from app.core.logger import logger, logging_middleware


# Ensure application module logs emit records.
logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo Face Service
    get_face_service()
    
    # Kiểm tra cứu hộ Admin
    async with AsyncSessionLocal() as db:
        await handle_admin_reset(db)
    stop_event = asyncio.Event()

    # Khởi chạy song song MQTT, Scheduler, Thu Âm và AI STT
    mqtt_task = asyncio.create_task(mqtt_service.connect_and_subscribe())
    schedule_task = asyncio.create_task(run_device_schedule_loop(stop_event))
    voice_task = asyncio.create_task(voice_streamer_service.start())
    logic_task = asyncio.create_task(voice_logic_service.start())
    try:
        yield
    finally:
        logger.info("Đang tắt server, dọn dẹp tài nguyên...")
        stop_event.set()
        await schedule_task
        await voice_logic_service.stop()
        await voice_streamer_service.stop()
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
