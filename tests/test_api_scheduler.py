import os
os.environ["TESTING"] = "1"
import api


def test_scheduler_endpoints():
    api.sched.scheduler.remove_all_jobs()
    job = api.ScheduleJob(
        pf_id="demo",
        name="Demo",
        module="strategies.lobbying_growth",
        cls="LobbyingGrowthStrategy",
        cron_key="monthly",
    )
    api.add_job(job)
    jobs = api.list_jobs()["jobs"]
    assert any(j["id"] == "demo" for j in jobs)
