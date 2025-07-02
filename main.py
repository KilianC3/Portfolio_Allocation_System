import asyncio, signal
from logger import get_logger
from scheduler import StrategyScheduler
_log = get_logger("main")
def main():
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
