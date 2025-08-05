import asyncio
import datetime as dt

from analytics import update_all_metrics
from database import metric_coll
from service.logger import get_logger
from ws import broadcast_metrics

log = get_logger("updater")


async def run(interval: int = 300) -> None:
    """Periodically refresh metrics and broadcast updates."""
    while True:
        try:
            await asyncio.to_thread(update_all_metrics)
            doc = metric_coll.find_one(sort=[("date", -1)])
            if doc:
                if isinstance(doc.get("date"), dt.date):
                    doc["date"] = doc["date"].isoformat()
                await broadcast_metrics(doc)
        except Exception as exc:
            log.exception(f"update failed: {exc}")
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(run())
