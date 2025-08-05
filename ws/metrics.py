from __future__ import annotations

from typing import Set, Any

from fastapi import WebSocket

# Set of active WebSocket connections for metrics updates
metrics_clients: Set[WebSocket] = set()


async def broadcast_metrics(payload: Any) -> None:
    """Send a payload to all connected metrics clients.

    Parameters
    ----------
    payload: Any
        JSON-serialisable data to push to clients.
    """
    for ws in list(metrics_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            # Drop broken connections
            metrics_clients.discard(ws)
