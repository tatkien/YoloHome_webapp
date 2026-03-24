import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.service.mqtt import mqtt_service
from app.core.config import settings
from app.realtime.scheduler import run_device_schedule_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Đang khởi động các dịch vụ chạy ngầm...")
    stop_event = asyncio.Event()

    # Khởi chạy song song MQTT và Scheduler
    mqtt_task = asyncio.create_task(mqtt_service.connect_and_subscribe())
    schedule_task = asyncio.create_task(run_device_schedule_loop(stop_event))
    try:
        yield
    finally:
        print("Đang tắt Server, tiến hành dọn dẹp...")
        stop_event.set()
        await schedule_task
        mqtt_task.cancel()
        try:
            if mqtt_service.client:
                await mqtt_service.client.disconnect()
        except Exception as e:
                print(f"Lỗi ngắt kết nối MQTT: {e}")

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

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
