import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set

router = APIRouter()

clients: Set[WebSocket] = set()


async def broadcast_message(text: str) -> None:
    """Send ``text`` to all connected WebSocket clients."""
    if not clients:
        return

    disconnected: Set[WebSocket] = set()

    async def _send(client: WebSocket) -> None:
        try:
            await client.send_text(text)
        except WebSocketDisconnect:
            disconnected.add(client)

    await asyncio.gather(*(_send(c) for c in list(clients)))

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
