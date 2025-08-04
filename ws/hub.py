from fastapi import APIRouter
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set

router = APIRouter()

clients: Set[WebSocket] = set()


async def broadcast_message(text: str) -> None:
    """Send ``text`` to all connected WebSocket clients."""
    disconnected: Set[WebSocket] = set()
    for client in list(clients):
        try:
            await client.send_text(text)
        except WebSocketDisconnect:
            disconnected.add(client)

    for client in disconnected:
        clients.discard(client)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.remove(ws)
