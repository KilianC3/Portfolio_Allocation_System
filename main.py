import asyncio
import signal
import os
import sentry_sdk
from logger import get_logger
from scheduler import StrategyScheduler
from observability.tracing import setup_tracer
_log = get_logger("main")
def main():
    sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))
    setup_tracer()
    sched=StrategyScheduler()
    # example strategies (must exist)
    try:
        sched.add("lobby","Lobbying","strategies.lobbying_growth","LobbyingGrowthStrategy","monthly")
    except Exception as e:
        _log.warning(e)
    loop=asyncio.get_event_loop()
    for sig in (signal.SIGINT,signal.SIGTERM):
        loop.add_signal_handler(sig,lambda s=sig: sched.scheduler.shutdown(wait=False))
    sched.start(); _log.info("running"); loop.run_forever()
if __name__=="__main__": main()
