from service.scheduler import StrategyScheduler


def test_scheduler_registers_db_backup():
    sched = StrategyScheduler()
    sched.register_jobs()
    assert sched.scheduler.get_job("db_backup") is not None
