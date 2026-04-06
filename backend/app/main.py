import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.face_service import get_face_service
from app.realtime.scheduler import run_device_schedule_loop


# Ensure application module logs (e.g. app.core.face_service) emit INFO-level records.
logging.getLogger("app").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_face_service()
    stop_event = asyncio.Event()
    task = asyncio.create_task(run_device_schedule_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await task


app = FastAPI(
    title="YoloHome API",
    version="0.1.0",
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
