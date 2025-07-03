from fastapi import WebSocket, WebSocketDisconnect
from fastapi import APIRouter

router = APIRouter()

clients = set()

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.remove(ws)
