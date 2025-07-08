# Folder Overview

Utilities for logging, metrics and tracing.
- `logging.py` configures structured log output.
- `metrics_router.py` exposes Prometheus metrics over HTTP.
- `tracing.py` integrates OpenTelemetry if configured.

Other packages import these modules to report status and errors.
