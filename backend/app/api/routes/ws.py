from fastapi import APIRouter, Query, WebSocket
from app.service.ws_service import realtime_manager

router = APIRouter(tags=["ws"])

@router.websocket("/ws")
async def user_global_stream(
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    await realtime_manager.handle_connection(websocket, token)