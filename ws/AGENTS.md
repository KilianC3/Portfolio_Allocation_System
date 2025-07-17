# Folder Overview

WebSocket hub used for push updates to the frontend.
- `hub.py` handles active connections and broadcast messages.

Depends on the API module to orchestrate portfolio events.
Recent commits added automatic connection metrics so clients can monitor feed
health via Prometheus.
