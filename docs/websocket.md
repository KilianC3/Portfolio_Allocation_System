# WebSocket Protocol

The API exposes two WebSocket endpoints used for real-time updates:

- `/ws` – generic endpoint that keeps connections alive for broadcast
  messages.
- `/ws/metrics` – streams portfolio metric updates as they are computed.

Messages are JSON objects with a `type` field.

```json
{
  "type": "metrics",
  "portfolio_id": "abc123",
  "date": "2024-01-01",
  "metrics": {"sharpe": 1.2, "var": -0.05}
}
```

System log pushes use the following form:

```json
{"type": "logs", "records": [{"timestamp": "...", "message": "..."}]}
```

Clients should ignore messages with unknown `type` values so the protocol
can evolve without breaking backwards compatibility.

Front end charts can be exported to PNG files for reporting.  Components use
a shared `exportChart` helper that calls the Chart.js `toBase64Image()`
method and triggers a download in the browser.
