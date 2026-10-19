import asyncio
import math
from datetime import datetime, timezone, timedelta
import config
from models.database import AsyncSessionLocal
from services.quota_service import is_daily_budget_reached
from api.websocket import manager

_running = False
_current_mode = None
_current_strategy = None
_next_fire_time = None
_scheduler_task = None
_cycle_lock = asyncio.Lock()

def draw_gap(mode: str) -> float:
    rng = config.get_rng()
    if mode == "heavy_tailed":
        min_log = math.log(config.SCHED_MIN_SECONDS)
        max_log = math.log(config.SCHED_MAX_SECONDS)
        return math.exp(rng.uniform(min_log, max_log))
    return rng.expovariate(1.0 / config.SCHED_MEAN_SECONDS)

async def _scheduler_loop():
    global _running, _next_fire_time
    while _running:
        gap = draw_gap(_current_mode)
        now = datetime.now(timezone.utc)
        _next_fire_time = now + timedelta(seconds=gap)

        await manager.broadcast({
            "type": "scheduler_update",
            "data": {
                "running": True,
                "mode": _current_mode,
                "strategy": _current_strategy,
                "next_fire_time": _next_fire_time.isoformat(),
                "gap_seconds": round(gap, 2)
            }
        })

        try:
            await asyncio.sleep(gap)
        except asyncio.CancelledError:
            break

        if not _running:
            break

        if is_daily_budget_reached():
            stop_scheduler()
            await manager.broadcast({
                "type": "quota_exceeded",
                "data": {"message": "LLM daily budget reached; scheduler paused"}
            })
            break

        async with _cycle_lock:
            if not _running:
                break
            try:
                from services.orchestrator import execute_shutdown_cycle
                async with AsyncSessionLocal() as db:
                    await execute_shutdown_cycle(
                        db,
                        strategy=_current_strategy,
                        trigger_type="scheduler",
                        triggered_by="scheduler"
                    )
            except Exception as exc:
                print(f"[scheduler] error executing cycle: {exc}")

def start_scheduler(mode: str, strategy: str):
    global _running, _current_mode, _current_strategy, _scheduler_task
    stop_scheduler()
    _current_mode = mode if mode in ("poisson", "heavy_tailed") else "poisson"
    _current_strategy = strategy if strategy in ("A", "B", "C") else "A"
    _running = True
    _scheduler_task = asyncio.create_task(_scheduler_loop())

def stop_scheduler():
    global _running, _current_mode, _current_strategy, _next_fire_time, _scheduler_task
    _running = False
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
    _scheduler_task = None
    _current_mode = None
    _current_strategy = None
    _next_fire_time = None

def get_scheduler_status():
    return {
        "running": _running,
        "mode": _current_mode,
        "strategy": _current_strategy,
        "next_fire_time": _next_fire_time.isoformat() if _next_fire_time else None
    }
