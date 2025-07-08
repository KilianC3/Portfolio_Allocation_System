# Folder Overview

Risk management models and limits.
- `circuit.py` – circuit breaker checks for portfolio losses.
- `corr_regime.py` – correlation regime shift detection.
- `exposure.py` – limits by symbol and sector.
- `position_risk.py` and `var.py` – value-at-risk calculations.

Strategies query these modules before executing trades.
