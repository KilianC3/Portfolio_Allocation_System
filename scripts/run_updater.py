import asyncio
from collections import defaultdict
import pandas as pd

from tasks.updater import update_loop
from database import returns_coll


def fetch_returns() -> dict:
    """Load daily returns from the ``returns`` collection.

    Returns
    -------
    dict
        Mapping of ``{pf_id: pd.Series}`` where the series index is a
        ``DatetimeIndex``.
    """

    data: defaultdict[str, list] = defaultdict(list)
    for doc in returns_coll.find({}):
        data[doc["strategy"]].append((doc["date"], doc["return_pct"]))
    out: dict[str, pd.Series] = {}
    for pf_id, rows in data.items():
        rows.sort(key=lambda r: r[0])
        dates = [r[0] for r in rows]
        rets = [r[1] for r in rows]
        out[pf_id] = pd.Series(rets, index=pd.to_datetime(dates))
    return out


if __name__ == "__main__":
    asyncio.run(update_loop(fetch_returns))
