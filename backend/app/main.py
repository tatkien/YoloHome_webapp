import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.service.mqtt import mqtt_service
from app.core.config import settings
from app.core.face_service import get_face_service
from app.realtime.scheduler import run_device_schedule_loop


# Ensure application module logs (e.g. app.core.face_service) emit INFO-level records.
logging.getLogger("app").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_face_service()
    stop_event = asyncio.Event()

    # Start MQTT and scheduler in parallel
    mqtt_task = asyncio.create_task(mqtt_service.connect_and_subscribe())
    schedule_task = asyncio.create_task(run_device_schedule_loop(stop_event))
    try:
        yield
    finally:
        print("Shutting down server, cleaning up resources...")
        stop_event.set()
        await schedule_task
        mqtt_task.cancel()
        try:
            if mqtt_service.client:
                await mqtt_service.client.disconnect()
        except Exception as e:
                print(f"Error disconnecting MQTT client: {e}")

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
