from fastapi import APIRouter

from app.api.v1 import devices

api_router = APIRouter()
api_router.include_router(devices.router)
