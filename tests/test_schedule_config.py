import service.config as cfg


def test_scraper_schedule_cadences():
    sched = cfg.DEFAULT_SCHEDULES
    assert sched["wsb_mentions"] == "0 3 * * *"
    assert sched["wiki_trending"] == "0 3 * * 1"
    assert sched["wiki_views"] == "30 3 * * 1"
    assert sched["app_reviews"] == "0 6 * * 1"
    assert sched["google_trends"] == "0 7 * * 1"

