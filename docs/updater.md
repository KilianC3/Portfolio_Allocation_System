# Metrics Updater Task

The background updater runs continuously to compute portfolio metrics and
broadcast them over the WebSocket feed.

```bash
python scripts/run_updater.py
```

The script loads recent returns from the `returns` collection, aggregates
daily exposure, stores new metrics in the `metrics` table and pushes a
`metrics` message to `/ws/metrics`.  Deployments run the task as a separate
systemd service (`deploy/updater.service`).
