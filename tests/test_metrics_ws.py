import asyncio
from fastapi.testclient import TestClient

from service.api import app
from ws import broadcast_metrics

client = TestClient(app)


def test_metrics_websocket_broadcast():
    with client.websocket_connect("/ws/metrics") as ws:
        asyncio.run(broadcast_metrics({"ret": 0.1, "win_rate": 0.5}))
        data = ws.receive_json()
        assert data["ret"] == 0.1
        assert data["win_rate"] == 0.5
