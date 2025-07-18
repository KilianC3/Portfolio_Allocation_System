# Folder Overview

Utilities for logging, metrics and tracing.
- `logging.py` configures structured log output.
- `metrics_router.py` exposes Prometheus metrics over HTTP.
- `tracing.py` integrates OpenTelemetry if configured.

Other packages import these modules to report status and errors.
Logging now includes the scheduler startup routine and prints first-row samples
from scrapers during testing for easier debugging.

- **Reminder:** triple-check modifications and run tests to prevent regressions.
