from contextlib import asynccontextmanager

import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.security import hash_secret
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def _seed_admin() -> None:
    """Create the default admin account if no users exist yet."""
    async with AsyncSessionLocal() as db:
        count = await db.scalar(sa.select(sa.func.count()).select_from(User))
        if count == 0:
            db.add(User(
                username="admin",
                full_name="Administrator",
                hashed_password=hash_secret("kiendeptrai"),
                role="admin",
                is_active=True,
            ))
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _seed_admin()
    yield


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
