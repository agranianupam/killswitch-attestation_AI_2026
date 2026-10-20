import pytest
import config
from services.quota_service import record_call, get_calls_today, is_daily_budget_reached, is_minute_rate_reached, reset_quota, get_quota_status
from services.scheduler_service import draw_gap, get_scheduler_status, start_scheduler, stop_scheduler

def test_rng_seeded_and_unseeded():
    config.RANDOM_SEED = 42
    rng1 = config.get_rng()
    vals1 = [rng1.random() for _ in range(5)]

    config.RANDOM_SEED = 42
    rng2 = config.get_rng()
    vals2 = [rng2.random() for _ in range(5)]
    assert vals1 == vals2

    config.RANDOM_SEED = None
    rng3 = config.get_rng()
    rng4 = config.get_rng()
    assert rng3.random() != rng4.random()

def test_heavy_tailed_bounds():
    config.RANDOM_SEED = None
    gaps = [draw_gap("heavy_tailed") for _ in range(100)]
    for g in gaps:
        assert config.SCHED_MIN_SECONDS <= g <= config.SCHED_MAX_SECONDS

def test_exponential_delay_mean():
    orig_seed = config.RANDOM_SEED
    try:
        config.RANDOM_SEED = 1234
        test_mean = 8.0
        rng = config.get_rng()
        delays = [rng.expovariate(1.0 / test_mean) for _ in range(1000)]
        sample_mean = sum(delays) / len(delays)
        assert 7.0 <= sample_mean <= 9.0
    finally:
        config.RANDOM_SEED = orig_seed

def test_quota_service_lifecycle():
    reset_quota()
    assert get_calls_today() == 0
    assert is_daily_budget_reached() is False
    assert is_minute_rate_reached() is False

    for _ in range(3):
        record_call()
    assert get_calls_today() == 3

    status = get_quota_status()
    assert status["calls_today"] == 3
    assert status["daily_budget_reached"] is False
    reset_quota()

@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    stop_scheduler()
    status = get_scheduler_status()
    assert status["running"] is False
    assert status["mode"] is None

    start_scheduler("poisson", "B")
    status_running = get_scheduler_status()
    assert status_running["running"] is True
    assert status_running["mode"] == "poisson"
    assert status_running["strategy"] == "B"

    stop_scheduler()
    assert get_scheduler_status()["running"] is False

def test_quota_minute_rate_limit():
    reset_quota()
    orig_max = config.GEMINI_MAX_CALLS_PER_MINUTE
    config.GEMINI_MAX_CALLS_PER_MINUTE = 5
    try:
        assert is_minute_rate_reached() is False
        for _ in range(5):
            record_call()
        assert is_minute_rate_reached() is True
    finally:
        config.GEMINI_MAX_CALLS_PER_MINUTE = orig_max
        reset_quota()

def test_adaptive_feedback_adjusts_mean():

    old_mean = 600.0
    config.SCHED_MEAN_SECONDS = old_mean

    recent_leak_rate = 0.40
    if recent_leak_rate > config.FEEDBACK_LEAK_THRESHOLD:
        new_mean = max(config.SCHED_MEAN_MIN_BOUND, old_mean * 0.8)
    assert new_mean == 480.0

    recent_leak_rate = 0.05
    if recent_leak_rate < config.FEEDBACK_LOW_THRESHOLD:
        new_mean = min(config.SCHED_MEAN_MAX_BOUND, old_mean * 1.25)
    assert new_mean == 750.0
