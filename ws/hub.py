"""WebSocket connection hub for push notifications.

This module maintains a simple registry of connected WebSocket clients and
provides a helper to broadcast text payloads to each of them.  The hub is used
by the API layer to push metric updates and system log messages to any
subscribed front end client.
"""

from __future__ import annotations

from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Router exported for inclusion in the main FastAPI app
router = APIRouter()

# Track all active WebSocket connections
clients: Set[WebSocket] = set()


async def register(ws: WebSocket) -> None:
    """Accept and register a WebSocket connection."""
    await ws.accept()
    clients.add(ws)


def unregister(ws: WebSocket) -> None:
    """Remove a WebSocket connection from the registry."""
    clients.discard(ws)


async def broadcast_message(text: str) -> None:
    """Send ``text`` to all currently connected clients.

    Connections that fail during send are removed from the registry to avoid
    leaking stale sockets.
    """
    for ws in list(clients):
        try:
            await ws.send_text(text)
        except Exception:
            unregister(ws)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Default WebSocket endpoint that simply keeps the connection alive."""
    await register(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        unregister(ws)


__all__ = ["router", "broadcast_message", "register", "unregister"]
