# WebSocket Protocol

The API exposes a `/ws` endpoint that streams events to connected clients.

Clients connect using the standard WebSocket handshake:

```
ws://<host>:<port>/ws
```

Each message is a JSON-formatted string with a `type` field identifying the
payload. Current message types include:

- `metric` – portfolio metrics updated via the `/metrics/{pf_id}` endpoint.
- `system_log` – new system log entries posted through the `/logs` endpoint.

Example payloads:

```json
{"type": "metric", "portfolio_id": "demo", "metrics": {"ret": 0.01}}
```

```json
{"type": "system_log", "message": "scheduler started", "timestamp": "2024-01-01T00:00:00"}
```

Clients should parse the JSON and branch on the `type` to handle new events.
