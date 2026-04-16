from fastapi import APIRouter
from app.api.routes import auth, devices, face, users, ws 

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(devices.router)
api_router.include_router(face.router)
api_router.include_router(ws.router)
