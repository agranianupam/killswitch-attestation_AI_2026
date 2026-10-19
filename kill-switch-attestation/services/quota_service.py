from datetime import datetime, timezone, timedelta
import config

_call_timestamps: list[datetime] = []
_budget_paused: bool = False

def get_calls_today() -> int:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return sum(1 for ts in _call_timestamps if ts >= today_start)

def get_calls_in_last_minute() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    return sum(1 for ts in _call_timestamps if ts >= cutoff)

def is_daily_budget_reached() -> bool:
    return get_calls_today() >= config.GEMINI_MAX_CALLS_PER_DAY

def is_minute_rate_reached() -> bool:
    return get_calls_in_last_minute() >= config.GEMINI_MAX_CALLS_PER_MINUTE

def record_call():
    global _budget_paused
    now = datetime.now(timezone.utc)
    _call_timestamps.append(now)
    cutoff = now - timedelta(days=2)
    while _call_timestamps and _call_timestamps[0] < cutoff:
        _call_timestamps.pop(0)

    if is_daily_budget_reached():
        _budget_paused = True
        try:
            from services.scheduler_service import stop_scheduler
            stop_scheduler()
        except Exception:
            pass

def is_budget_paused() -> bool:
    return _budget_paused

def reset_quota():
    global _call_timestamps, _budget_paused
    _call_timestamps.clear()
    _budget_paused = False

def get_quota_status() -> dict:
    return {
        "calls_today": get_calls_today(),
        "max_calls_per_day": config.GEMINI_MAX_CALLS_PER_DAY,
        "calls_last_minute": get_calls_in_last_minute(),
        "max_calls_per_minute": config.GEMINI_MAX_CALLS_PER_MINUTE,
        "daily_budget_reached": is_daily_budget_reached(),
        "scheduler_paused": _budget_paused
    }
