"""WebSocket connection hub for push notifications.

This module maintains a simple registry of connected WebSocket clients and
provides a helper to broadcast text payloads to each of them.  The hub is used
by the API layer to push metric updates and system log messages to any
subscribed front end client.
"""

from __future__ import annotations

from typing import Set
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from service.logger import get_logger

# Router exported for inclusion in the main FastAPI app
router = APIRouter()

# Track all active WebSocket connections
clients: Set[WebSocket] = set()
log = get_logger("ws.hub")


async def register(ws: WebSocket) -> None:
    """Accept and register a WebSocket connection."""
    await ws.accept()
    clients.add(ws)


def unregister(ws: WebSocket) -> None:
    """Remove a WebSocket connection from the registry."""
    clients.discard(ws)


async def _send(ws: WebSocket, text: str) -> None:
    try:
        await ws.send_text(text)
    except Exception as exc:
        log.warning(f"websocket send failed: {exc}")
        unregister(ws)


async def broadcast_message(text: str) -> None:
    """Send ``text`` to all currently connected clients."""
    await asyncio.gather(
        *[_send(ws, text) for ws in list(clients)], return_exceptions=True
    )


async def heartbeat(interval: int = 30) -> None:
    """Periodically send ping frames to keep connections alive."""
    while True:
        await asyncio.sleep(interval)
        await broadcast_message("ping")


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Default WebSocket endpoint that simply keeps the connection alive."""
    await register(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        unregister(ws)


__all__ = ["router", "broadcast_message", "register", "unregister", "heartbeat"]
