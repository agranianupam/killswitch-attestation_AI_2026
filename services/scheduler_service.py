import asyncio
import math
from datetime import datetime, timezone, timedelta
import config
from models.database import AsyncSessionLocal
from services.quota_service import is_daily_budget_reached, get_calls_today
from api.websocket import manager

_running = False
_current_mode = "poisson"
_current_strategy = "A"
_current_profile = "default"
_current_agent_mode = None
_next_fire_time = None
_current_experiment_status = "IDLE"
_last_attempted_at = None
_last_completed_at = None
_last_skipped_at = None
_completed_count = 0
_skipped_count = 0
_pause_reason = None
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
    global _running, _next_fire_time, _current_experiment_status
    global _last_attempted_at, _last_completed_at, _last_skipped_at
    global _completed_count, _skipped_count, _pause_reason
    global _current_mode, _current_strategy, _current_profile, _current_agent_mode

    while _running:
        gap = draw_gap(_current_mode)
        now = datetime.now(timezone.utc)
        _next_fire_time = now + timedelta(seconds=gap)
        _current_experiment_status = "WAITING_GAP"

        await _broadcast_status(gap_seconds=round(gap, 2))

        try:
            await asyncio.sleep(gap)
        except asyncio.CancelledError:
            break

        if not _running:
            break

        effective_mode = _current_agent_mode or getattr(config, "AGENT_MODE", "scripted")
        if effective_mode == "gemini" and is_daily_budget_reached():
            _pause_reason = "Daily LLM request budget cap reached; automated testing paused."
            _current_experiment_status = "PAUSED"
            stop_scheduler(reason=_pause_reason)
            try:
                from services.alert_service import create_alert
                await create_alert(
                    severity="warning",
                    category="quota",
                    title="Daily Quota Cap Reached",
                    message="Daily Gemini request budget limit reached. Randomized scheduler paused until tomorrow.",
                    recommended_action="Increase KS_GEMINI_MAX_CALLS_PER_DAY or switch to Scripted/Local mode for offline testing."
                )
            except Exception:
                pass
            break

        async with _cycle_lock:
            if not _running:
                break

            _current_experiment_status = "RUNNING_EXPERIMENT"
            _last_attempted_at = datetime.now(timezone.utc)
            await _broadcast_status()

            try:
                from services.orchestrator import execute_shutdown_cycle
                
                agent_cfg = None
                if _current_profile and _current_profile != "default":
                    from services.adversarial_agent import AdversarialAgentConfig
                    import random
                    rng = config.get_rng()
                    prof = _current_profile
                    if prof == "random":
                        prof = rng.choice([
                            "cooperative", "slow", "cancellation_resistant",
                            "credential_dependent", "retry_heavy", "fault_injection"
                        ])
                    seed = rng.randint(1, 999999)
                    agent_cfg = AdversarialAgentConfig(
                        profile=prof,
                        random_seed=seed,
                        execution_mode="local" if effective_mode != "gemini" else "gemini"
                    )

                async with AsyncSessionLocal() as db:
                    result = await execute_shutdown_cycle(
                        db,
                        strategy=_current_strategy,
                        trigger_type="scheduler",
                        triggered_by="scheduler",
                        agent_mode=effective_mode,
                        agent_config=agent_cfg
                    )

                if isinstance(result, dict) and result.get("status") == "skipped":
                    _skipped_count += 1
                    _last_skipped_at = datetime.now(timezone.utc)
                else:
                    _completed_count += 1
                    _last_completed_at = datetime.now(timezone.utc)

            except Exception as exc:
                _skipped_count += 1
                _last_skipped_at = datetime.now(timezone.utc)
                print(f"[scheduler] error executing cycle: {exc}")
                try:
                    from services.alert_service import create_alert
                    await create_alert(
                        severity="error",
                        category="system",
                        title="Scheduler Experiment Error",
                        message=f"Automated scheduler failed to execute experiment cycle: {str(exc)}",
                        recommended_action="Inspect server logs and database connectivity."
                    )
                except Exception:
                    pass

            _current_experiment_status = "IDLE"
            await _broadcast_status()

async def _broadcast_status(gap_seconds: float | None = None):
    try:
        data = get_scheduler_status()
        if gap_seconds is not None:
            data["gap_seconds"] = gap_seconds
        await manager.broadcast({
            "type": "scheduler_update",
            "data": data
        })
    except Exception:
        pass

def start_scheduler(
    mode: str = "poisson",
    strategy: str = "A",
    agent_profile: str = "default",
    agent_mode: str | None = None
):
    global _running, _current_mode, _current_strategy, _current_profile, _current_agent_mode
    global _scheduler_task, _pause_reason, _current_experiment_status, _next_fire_time
    stop_scheduler()
    _current_mode = mode if mode in ("poisson", "heavy_tailed") else "poisson"
    _current_strategy = strategy if strategy in ("A", "B", "C") else "A"
    _current_profile = agent_profile or "default"
    _current_agent_mode = agent_mode
    _pause_reason = None
    _running = True
    _current_experiment_status = "STARTING"
    gap = draw_gap(_current_mode)
    _next_fire_time = datetime.now(timezone.utc) + timedelta(seconds=gap)
    try:
        loop = asyncio.get_running_loop()
        _scheduler_task = loop.create_task(_scheduler_loop())
    except RuntimeError:
        _scheduler_task = None

def stop_scheduler(reason: str | None = None):
    global _running, _scheduler_task, _next_fire_time, _pause_reason, _current_experiment_status
    global _current_mode, _current_strategy, _current_profile, _current_agent_mode
    _running = False
    if reason:
        _pause_reason = reason
    _current_experiment_status = "PAUSED"
    if _scheduler_task and not _scheduler_task.done():
        try:
            _scheduler_task.cancel()
        except RuntimeError:
            pass
    _scheduler_task = None
    _current_mode = None
    _current_strategy = None
    _next_fire_time = None

def get_scheduler_status() -> dict:
    mean_int = getattr(config, "SCHED_MEAN_SECONDS", 600.0)

    return {
        "running": _running,
        "mode": _current_mode,
        "strategy": _current_strategy,
        "agent_profile": _current_profile,
        "agent_mode": _current_agent_mode or getattr(config, "AGENT_MODE", "scripted"),
        "configured_mode": getattr(config, "SCHED_MODE", "poisson"),
        "mean_interval": mean_int,
        "mean_interval_seconds": mean_int,
        "next_fire_time": _next_fire_time.isoformat() if _next_fire_time else None,
        "next_scheduled_start": _next_fire_time.isoformat() if _next_fire_time else None,
        "current_status": _current_experiment_status if _running else "PAUSED",
        "current_experiment_status": _current_experiment_status if _running else "PAUSED",
        "last_attempted_at": _last_attempted_at.isoformat() if _last_attempted_at else None,
        "last_completed_at": _last_completed_at.isoformat() if _last_completed_at else None,
        "last_skipped_at": _last_skipped_at.isoformat() if _last_skipped_at else None,
        "completed_count": _completed_count,
        "completed_experiments_count": _completed_count,
        "skipped_count": _skipped_count,
        "skipped_attempts_count": _skipped_count,
        "pause_reason": _pause_reason,
        "calls_today": get_calls_today(),
        "budget_limit": getattr(config, "GEMINI_MAX_CALLS_PER_DAY", 1000)
    }

