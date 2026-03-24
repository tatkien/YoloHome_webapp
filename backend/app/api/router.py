from fastapi import APIRouter
from app.api.routes import auth, dashboards, devices, face, users, ws 

api_router = APIRouter()
api_router.include_router(auth.router, prefix="", tags=["auth"])
api_router.include_router(users.router, prefix="", tags=["users"])
api_router.include_router(devices.router, prefix="", tags=["devices"])
api_router.include_router(dashboards.router, prefix="", tags=["dashboards"])
api_router.include_router(face.router, prefix="", tags=["face"])
api_router.include_router(ws.router, prefix="", tags=["websocket"])

