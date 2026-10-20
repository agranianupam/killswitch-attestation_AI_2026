from datetime import datetime, timezone, timedelta
import config

_call_timestamps: list[datetime] = []
_token_records: list[dict] = []
_budget_paused: bool = False

def get_calls_today() -> int:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return sum(1 for ts in _call_timestamps if ts >= today_start)

def get_calls_in_last_minute() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    return sum(1 for ts in _call_timestamps if ts >= cutoff)

def get_tokens_today() -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    prompt_total = 0
    completion_total = 0
    total_tokens = 0
    has_tokens = False
    for rec in _token_records:
        if rec["timestamp"] >= today_start:
            has_tokens = True
            prompt_total += (rec.get("prompt_tokens") or 0)
            completion_total += (rec.get("completion_tokens") or 0)
            total_tokens += (rec.get("total_tokens") or 0)
    return {
        "prompt_tokens": prompt_total if has_tokens else 0,
        "completion_tokens": completion_total if has_tokens else 0,
        "total_tokens": total_tokens if has_tokens else 0,
        "has_data": has_tokens
    }

def is_daily_budget_reached() -> bool:
    return get_calls_today() >= config.GEMINI_MAX_CALLS_PER_DAY

def is_minute_rate_reached() -> bool:
    return get_calls_in_last_minute() >= config.GEMINI_MAX_CALLS_PER_MINUTE

def record_call(prompt_tokens: int | None = None, completion_tokens: int | None = None, total_tokens: int | None = None):
    global _budget_paused
    now = datetime.now(timezone.utc)
    _call_timestamps.append(now)
    cutoff = now - timedelta(days=2)
    while _call_timestamps and _call_timestamps[0] < cutoff:
        _call_timestamps.pop(0)

    if prompt_tokens is not None or completion_tokens is not None or total_tokens is not None:
        _token_records.append({
            "timestamp": now,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        })
        while _token_records and _token_records[0]["timestamp"] < cutoff:
            _token_records.pop(0)

    if is_daily_budget_reached():
        _budget_paused = True
        try:
            from services.scheduler_service import stop_scheduler
            stop_scheduler()
        except Exception:
            pass

def record_tokens(prompt_tokens: int | None = None, completion_tokens: int | None = None, total_tokens: int | None = None):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=2)
    _token_records.append({
        "timestamp": now,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens
    })
    while _token_records and _token_records[0]["timestamp"] < cutoff:
        _token_records.pop(0)

def is_budget_paused() -> bool:
    return _budget_paused

def reset_quota():
    global _call_timestamps, _token_records, _budget_paused
    _call_timestamps.clear()
    _token_records.clear()
    _budget_paused = False

def get_quota_status() -> dict:
    return {
        "calls_today": get_calls_today(),
        "max_calls_per_day": config.GEMINI_MAX_CALLS_PER_DAY,
        "calls_last_minute": get_calls_in_last_minute(),
        "max_calls_per_minute": config.GEMINI_MAX_CALLS_PER_MINUTE,
        "daily_budget_reached": is_daily_budget_reached(),
        "scheduler_paused": _budget_paused,
        "tokens_today": get_tokens_today()
    }
