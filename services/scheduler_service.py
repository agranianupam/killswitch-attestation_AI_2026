import asyncio
import math
from datetime import datetime, timezone, timedelta
from typing import Optional
import config
from models.database import AsyncSessionLocal
from services.quota_service import is_daily_budget_reached, get_calls_today
from api.websocket import manager

_running = False
_is_paused = False
_is_executing_cycle = False
_current_mode = "poisson"
_current_strategy = "A"
_current_profile = "default"
_current_agent_mode = None
_next_fire_time: Optional[datetime] = None
_current_experiment_status = "IDLE"
_last_attempted_at: Optional[datetime] = None
_last_completed_at: Optional[datetime] = None
_last_skipped_at: Optional[datetime] = None
_completed_count = 0
_skipped_count = 0
_pause_reason: Optional[str] = None
_scheduler_task: Optional[asyncio.Task] = None
_sleep_task: Optional[asyncio.Task] = None
_cycle_lock = asyncio.Lock()


def draw_gap(mode: str) -> float:
    rng = config.get_rng()
    min_cooldown = float(getattr(config, "SCHED_MIN_SECONDS", 10.0))
    max_bound = float(getattr(config, "SCHED_MAX_SECONDS", 86400.0))
    mean_seconds = float(getattr(config, "SCHED_MEAN_SECONDS", 600.0))
    if mean_seconds <= 0:
        mean_seconds = 600.0

    if mode == "heavy_tailed":
        min_log = math.log(max(1.0, min_cooldown))
        max_log = math.log(max_bound)
        val = math.exp(rng.uniform(min_log, max_log))
    else:
        val = rng.expovariate(1.0 / mean_seconds)

    return max(min_cooldown, min(val, max_bound))


async def _scheduler_loop():
    global _running, _is_paused, _is_executing_cycle, _next_fire_time, _current_experiment_status
    global _last_attempted_at, _last_completed_at, _last_skipped_at
    global _completed_count, _skipped_count, _pause_reason
    global _current_mode, _current_strategy, _current_profile, _current_agent_mode
    global _sleep_task

    while _running and not _is_paused:
        gap = draw_gap(_current_mode)
        now = datetime.now(timezone.utc)
        _next_fire_time = now + timedelta(seconds=gap)
        _current_experiment_status = "WAITING FOR NEXT RUN"

        await _broadcast_status(gap_seconds=round(gap, 2))

        try:
            _sleep_task = asyncio.create_task(asyncio.sleep(gap))
            await _sleep_task
        except asyncio.CancelledError:
            break
        finally:
            _sleep_task = None

        if not _running or _is_paused:
            break

        effective_mode = _current_agent_mode or getattr(config, "AGENT_MODE", "scripted")
        if effective_mode == "gemini" and is_daily_budget_reached():
            _pause_reason = "Daily LLM request budget cap reached; automated testing paused."
            _current_experiment_status = "PAUSED"
            pause_scheduler(reason=_pause_reason)
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
            if not _running or _is_paused:
                break

            _is_executing_cycle = True
            _current_experiment_status = "RUN IN PROGRESS"
            _last_attempted_at = datetime.now(timezone.utc)
            await _broadcast_status()

            try:
                from services.orchestrator import execute_shutdown_cycle

                agent_cfg = None
                if _current_profile and _current_profile != "default":
                    from services.adversarial_agent import AdversarialAgentConfig
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
                        strategy=_current_strategy or "A",
                        trigger_type="scheduler",
                        triggered_by="scheduler",
                        agent_mode=effective_mode,
                        agent_config=agent_cfg,
                        scenario=None  # Explicitly None to prevent running manual failure scenario
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
            finally:
                _is_executing_cycle = False

            _current_experiment_status = "WAITING FOR NEXT RUN" if _running else ("PAUSED" if _is_paused else "STOPPED")
            await _broadcast_status()

    if not _running:
        _current_experiment_status = "PAUSED" if _is_paused else "STOPPED"
        _next_fire_time = None
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
    global _running, _is_paused, _current_mode, _current_strategy, _current_profile, _current_agent_mode
    global _scheduler_task, _pause_reason, _current_experiment_status, _next_fire_time

    if _running and _scheduler_task and not _scheduler_task.done():
        _current_mode = mode if mode in ("poisson", "heavy_tailed") else "poisson"
        _current_strategy = strategy if strategy in ("A", "B", "C") else "A"
        _current_profile = agent_profile or "default"
        _current_agent_mode = agent_mode
        return

    if _scheduler_task and not _scheduler_task.done():
        stop_scheduler()

    _current_mode = mode if mode in ("poisson", "heavy_tailed") else "poisson"
    _current_strategy = strategy if strategy in ("A", "B", "C") else "A"
    _current_profile = agent_profile or "default"
    _current_agent_mode = agent_mode
    _pause_reason = None
    _is_paused = False
    _running = True
    _current_experiment_status = "WAITING FOR NEXT RUN"
    gap = draw_gap(_current_mode)
    _next_fire_time = datetime.now(timezone.utc) + timedelta(seconds=gap)

    try:
        loop = asyncio.get_running_loop()
        _scheduler_task = loop.create_task(_scheduler_loop())
    except RuntimeError:
        _scheduler_task = None


def pause_scheduler(reason: str | None = None):
    global _running, _is_paused, _pause_reason, _current_experiment_status, _next_fire_time, _sleep_task
    _running = False
    _is_paused = True
    _pause_reason = reason or "Scheduler paused by operator"
    _current_experiment_status = "PAUSED"
    _next_fire_time = None

    if _sleep_task and not _sleep_task.done():
        try:
            _sleep_task.cancel()
        except RuntimeError:
            pass


def resume_scheduler():
    global _running, _is_paused, _pause_reason
    if _running and _scheduler_task and not _scheduler_task.done():
        return
    mode = _current_mode or "poisson"
    strat = _current_strategy or "A"
    start_scheduler(mode=mode, strategy=strat, agent_profile=_current_profile, agent_mode=_current_agent_mode)


def stop_scheduler(reason: str | None = None):
    global _running, _is_paused, _scheduler_task, _sleep_task, _next_fire_time, _pause_reason, _current_experiment_status
    global _current_mode, _current_strategy, _current_profile, _current_agent_mode
    _running = False
    _is_paused = False
    if reason:
        _pause_reason = reason
    _current_experiment_status = "STOPPED"
    _next_fire_time = None

    if _sleep_task and not _sleep_task.done():
        try:
            _sleep_task.cancel()
        except RuntimeError:
            pass
    _sleep_task = None

    if _scheduler_task and not _scheduler_task.done():
        try:
            _scheduler_task.cancel()
        except RuntimeError:
            pass
    _scheduler_task = None

    _current_mode = None
    _current_strategy = None


def get_scheduler_status() -> dict:
    mean_int = getattr(config, "SCHED_MEAN_SECONDS", 600.0)
    now = datetime.now(timezone.utc)

    if not _running:
        status_label = "PAUSED" if _is_paused else "STOPPED"
    elif _is_executing_cycle:
        status_label = "RUN IN PROGRESS"
    else:
        status_label = "WAITING FOR NEXT RUN"

    sec_until = None
    if _running and _next_fire_time:
        diff = (_next_fire_time - now).total_seconds()
        sec_until = max(0.0, round(diff, 1))

    return {
        "running": _running,
        "is_paused": _is_paused,
        "status": status_label,
        "current_status": status_label,
        "current_experiment_status": status_label,
        "state": status_label,
        "mode": _current_mode,
        "strategy": _current_strategy,
        "agent_profile": _current_profile,
        "agent_mode": _current_agent_mode or getattr(config, "AGENT_MODE", "scripted"),
        "configured_mode": getattr(config, "SCHED_MODE", "poisson"),
        "mean_interval": mean_int,
        "mean_interval_seconds": mean_int,
        "cooldown_seconds": getattr(config, "SCHED_MIN_SECONDS", 10.0),
        "next_fire_time": _next_fire_time.isoformat() if (_running and _next_fire_time) else None,
        "next_scheduled_start": _next_fire_time.isoformat() if (_running and _next_fire_time) else None,
        "seconds_until_next": sec_until,
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
