import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from service.logger import get_logger
from database import init_db, db_ping
from execution.gateway import AlpacaGateway
from ledger.master_ledger import MasterLedger
from analytics.allocation_engine import compute_weights
import pandas as pd
from service.start import start_api

_log = get_logger("bootstrap")


async def system_checklist() -> None:
    """Verify connectivity to core components."""
    errs = []

    if db_ping():
        _log.info("mariadb PASS")
    else:
        _log.warning("mariadb FAIL")
        errs.append("mariadb")

    try:
        gw = AlpacaGateway()
        await gw.account()
        await gw.close()
        _log.info("alpaca PASS")
    except Exception as exc:  # pragma: no cover - network optional
        _log.warning(f"alpaca FAIL: {exc}")
        errs.append(f"alpaca: {exc}")

    try:
        led = MasterLedger()
        await led.redis.ping()
        _log.info("ledger PASS")
    except Exception as exc:  # pragma: no cover - redis optional
        _log.warning(f"ledger FAIL: {exc}")
        errs.append(f"ledger: {exc}")

    try:
        df = pd.DataFrame(
            {"A": [0.1, -0.1], "B": [0.05, 0.02]},
            index=pd.to_datetime(["2024-01-01", "2024-01-08"]),
        )
        compute_weights(df)
        _log.info("allocation PASS")
    except Exception as exc:  # pragma: no cover - numeric errors
        _log.warning(f"allocation FAIL: {exc}")
        errs.append(f"allocation: {exc}")

    if errs:
        _log.warning({"checklist": errs})
        raise RuntimeError("; ".join(errs))
    _log.info("system checklist complete")


def main() -> None:
    asyncio.run(system_checklist())
    _log.info("bootstrap complete")
    start_api()


if __name__ == "__main__":
    main()
