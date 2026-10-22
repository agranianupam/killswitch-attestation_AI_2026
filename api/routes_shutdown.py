from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from models.database import get_db
from models.agent import Agent
from models.agent_action import AgentAction
from models.shutdown_event import ShutdownEvent, RevocationEvent
from services.crypto_service import load_public_key, verify_chain
from services.quota_service import get_calls_today, is_budget_paused
from pydantic import BaseModel
import config

router = APIRouter(prefix="/api/shutdown", tags=["shutdown"])

@router.post("")
async def trigger_shutdown(strategy: str = "A", trigger_type: str = "manual", db: AsyncSession = Depends(get_db)):
    if strategy not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Invalid strategy. Must be A, B, or C.")

    from services.orchestrator import execute_shutdown_cycle
    shutdown_result = await execute_shutdown_cycle(db, strategy=strategy, trigger_type=trigger_type, triggered_by=trigger_type)
    return shutdown_result

@router.post("/batch")
async def trigger_batch_shutdown(count: int = 5, strategy: str = "A", db: AsyncSession = Depends(get_db)):
    if count < 1 or count > 50:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 50")
    if strategy not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Invalid strategy. Must be A, B, or C.")

    from services.orchestrator import execute_shutdown_cycle
    from api.websocket import manager

    results = []
    for i in range(1, count + 1):
        res = await execute_shutdown_cycle(db, strategy=strategy, trigger_type="batch", triggered_by="manual")
        results.append(res)
        await manager.broadcast({
            "type": "batch_progress",
            "data": {
                "cycle": i,
                "total": count,
                "strategy": strategy,
                "residual_risk": res.get("residual_risk", 0.0),
                "leaked_channels": res.get("leaked_channels", 0),
                "in_flight_failures": res.get("in_flight_failures", 0),
                "final_state": res.get("final_state", "CONTAINED")
            }
        })

    risks = [r.get("residual_risk", 0.0) for r in results if r.get("status") != "skipped"]
    mean_risk = round(sum(risks) / len(risks), 4) if risks else 0.0
    terminated_count = sum(1 for r in results if r.get("final_state") == "TERMINATED")
    leaked_count = sum(1 for r in results if (r.get("leaked_channels", 0) > 0 or r.get("in_flight_failures", 0) > 0))

    return {
        "count": count,
        "total": count,
        "completed": len(results),
        "strategy": strategy,
        "mean_residual_risk": mean_risk,
        "success_rate": round((terminated_count / len(results)) * 100, 2) if results else 0.0,
        "leak_rate": round((leaked_count / len(results)) * 100, 2) if results else 0.0,
        "results": results
    }

@router.get("/history")
async def get_shutdown_history(include_scripted: bool = Query(False), db: AsyncSession = Depends(get_db)):
    query = select(ShutdownEvent).order_by(desc(ShutdownEvent.started_at))
    if not include_scripted:
        query = query.where(func.lower(ShutdownEvent.agent_mode) == "gemini")
    res = await db.execute(query.limit(50))
    events = res.scalars().all()
    return [
        {
            "id": e.id,
            "strategy": e.strategy,
            "trigger_type": e.trigger_type,
            "triggered_by": e.triggered_by or e.trigger_type,
            "trigger_timestamp": e.trigger_timestamp.isoformat() if e.trigger_timestamp else (e.started_at.isoformat() if e.started_at else None),
            "started_at": e.started_at.isoformat() if e.started_at else None,
            "finished_at": e.finished_at.isoformat() if e.finished_at else None,
            "final_state": e.final_state,
            "residual_risk": e.residual_risk,
            "partial_failure": e.partial_failure,
            "leaked_channels": e.leaked_channels,
            "in_flight_failures": e.in_flight_failures,
            "agent_mode": e.agent_mode,
            "shutdown_delay": e.shutdown_delay or 0.0,
            "actions_started": e.actions_started or 0,
            "actions_running": e.actions_running or 0,
            "actions_completed": e.actions_completed or 0,
            "prompt_tokens": e.prompt_tokens,
            "completion_tokens": e.completion_tokens,
            "total_tokens": e.total_tokens,
            "model_total_duration_ms": e.model_total_duration_ms,
            "last_channel_revoked_at": e.last_channel_revoked_at.isoformat() if e.last_channel_revoked_at else None,
            "attestation_written_at": e.attestation_written_at.isoformat() if e.attestation_written_at else None
        } for e in events
    ]

@router.get("/verify")
@router.get("/verify-chain")
async def verify_chain_endpoint(db: AsyncSession = Depends(get_db)):
    try:
        public_key = load_public_key()
        res = await verify_chain(db, public_key)
        is_valid = res.get("valid", False)
        if not is_valid:
            try:
                from services.alert_service import create_alert
                await create_alert(
                    severity="critical",
                    category="attestation",
                    title="Cryptographic Chain Broken",
                    message=f"Tampering detected at block index #{res.get('first_failure_index')}. Attestation hash chain or Ed25519 signature is invalid.",
                    recommended_action="Inspect the cryptographic ledger for unauthorized database modifications.",
                    db=db
                )
            except Exception:
                pass
        return {
            "status": "valid" if is_valid else "invalid",
            "valid": is_valid,
            "entries_checked": res.get("entries_checked", 0),
            "first_failure_index": res.get("first_failure_index"),
            "message": "Chain verified successfully" if is_valid else f"Broken chain at entry index {res.get('first_failure_index')}"
        }
    except Exception as e:
        return {"status": "error", "valid": False, "message": str(e)}

class SettingsModel(BaseModel):
    net_delay_min: int | None = None
    net_delay_max: int | None = None
    revoke_failure_prob: float | None = None
    iam_failure_prob: float | None = None
    in_flight_leak_prob: float | None = None
    agent_mode: str | None = None
    random_seed: int | None = None
    shutdown_mean_seconds: float | None = None
    sched_mean_seconds: float | None = None
    sched_min_seconds: float | None = None
    sched_max_seconds: float | None = None
    gemini_max_calls_per_day: int | None = None
    gemini_max_calls_per_minute: int | None = None

@router.get("/settings")
async def get_settings():
    key = getattr(config, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not key or key == "PASTE_YOUR_GEMINI_API_KEY_HERE":
        if hasattr(config, "reload_env"):
            config.reload_env()
        key = getattr(config, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    key_status = "configured" if (key and key != "PASTE_YOUR_GEMINI_API_KEY_HERE") else "missing"
    return {
        "net_delay_min": config.NET_DELAY_MIN,
        "net_delay_max": config.NET_DELAY_MAX,
        "revoke_failure_prob": config.REVOKE_FAILURE_PROB,
        "iam_failure_prob": config.IAM_FAILURE_PROB,
        "in_flight_leak_prob": config.IN_FLIGHT_LEAK_PROB,
        "agent_mode": getattr(config, "AGENT_MODE", "Gemini"),
        "model": getattr(config, "AGENT_MODEL", "gemini-3.5-flash-lite"),
        "key_status": key_status,
        "random_seed": config.RANDOM_SEED,
        "shutdown_mean_seconds": config.SHUTDOWN_MEAN_SECONDS,
        "sched_mean_seconds": config.SCHED_MEAN_SECONDS,
        "sched_min_seconds": config.SCHED_MIN_SECONDS,
        "sched_max_seconds": config.SCHED_MAX_SECONDS,
        "gemini_max_calls_per_day": config.GEMINI_MAX_CALLS_PER_DAY,
        "gemini_max_calls_per_minute": config.GEMINI_MAX_CALLS_PER_MINUTE,
        "calls_used_today": get_calls_today(),
        "daily_budget_reached": is_budget_paused()
    }

@router.post("/settings")
async def update_settings(s: SettingsModel):
    if s.net_delay_min is not None: config.NET_DELAY_MIN = s.net_delay_min
    if s.net_delay_max is not None: config.NET_DELAY_MAX = s.net_delay_max
    if s.revoke_failure_prob is not None: config.REVOKE_FAILURE_PROB = s.revoke_failure_prob
    if s.iam_failure_prob is not None: config.IAM_FAILURE_PROB = s.iam_failure_prob
    if s.in_flight_leak_prob is not None: config.IN_FLIGHT_LEAK_PROB = s.in_flight_leak_prob
    if s.agent_mode is not None:
        val = s.agent_mode.strip().lower()
        config.AGENT_MODE = "Scripted" if "scripted" in val else "Gemini"
    if s.random_seed is not None:
        config.RANDOM_SEED = s.random_seed
    if s.shutdown_mean_seconds is not None: config.SHUTDOWN_MEAN_SECONDS = s.shutdown_mean_seconds
    if s.sched_mean_seconds is not None: config.SCHED_MEAN_SECONDS = s.sched_mean_seconds
    if s.sched_min_seconds is not None: config.SCHED_MIN_SECONDS = s.sched_min_seconds
    if s.sched_max_seconds is not None: config.SCHED_MAX_SECONDS = s.sched_max_seconds
    if s.gemini_max_calls_per_day is not None: config.GEMINI_MAX_CALLS_PER_DAY = s.gemini_max_calls_per_day
    if s.gemini_max_calls_per_minute is not None: config.GEMINI_MAX_CALLS_PER_MINUTE = s.gemini_max_calls_per_minute
    return {"status": "ok", "settings": await get_settings()}

@router.get("/{id}/report")
async def get_shutdown_report(id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ShutdownEvent).where(ShutdownEvent.id == id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Shutdown event not found")

    rev_result = await db.execute(select(RevocationEvent).where(RevocationEvent.shutdown_event_id == id))
    revocations = rev_result.scalars().all()

    act_result = await db.execute(select(AgentAction).where(AgentAction.run_id == id).order_by(AgentAction.step_number, AgentAction.timestamp))
    actions = act_result.scalars().all()

    from models.attestation import AttestationEntry
    att_result = await db.execute(select(AttestationEntry).where(AttestationEntry.shutdown_event_id == id))
    attestation = att_result.scalar_one_or_none()

    return {
        "id": event.id,
        "strategy": event.strategy,
        "trigger_type": event.trigger_type,
        "triggered_by": event.triggered_by,
        "trigger_timestamp": event.trigger_timestamp.isoformat() if event.trigger_timestamp else None,
        "started_at": event.started_at.isoformat() if event.started_at else None,
        "finished_at": event.finished_at.isoformat() if event.finished_at else None,
        "final_state": event.final_state,
        "residual_risk": event.residual_risk,
        "partial_failure": event.partial_failure,
        "leaked_channels": event.leaked_channels,
        "in_flight_failures": event.in_flight_failures,
        "agent_mode": event.agent_mode,
        "agent_model": getattr(event, "agent_model", "gemini-3.5-flash-lite") or "gemini-3.5-flash-lite",
        "shutdown_delay": event.shutdown_delay or 0.0,
        "total_revocation_ms": getattr(event, "total_revocation_ms", 0.0) or 0.0,
        "retries_total": getattr(event, "retries_total", 0) or 0,
        "actions_started": event.actions_started or 0,
        "actions_running": event.actions_running or 0,
        "actions_completed": event.actions_completed or 0,
        "prompt_tokens": event.prompt_tokens,
        "completion_tokens": event.completion_tokens,
        "total_tokens": event.total_tokens,
        "model_total_duration_ms": getattr(event, "model_total_duration_ms", 0.0) or 0.0,
        "last_channel_revoked_at": event.last_channel_revoked_at.isoformat() if event.last_channel_revoked_at else None,
        "attestation_written_at": event.attestation_written_at.isoformat() if event.attestation_written_at else None,
        "revocations": [
            {
                "channel_type": r.channel_type,
                "latency_ms": r.latency_ms,
                "success": r.success,
                "retries": r.retries,
                "error": r.error
            } for r in revocations
        ],
        "agent_actions": [
            {
                "id": a.id,
                "step_number": a.step_number,
                "tool_name": a.tool_name,
                "arguments": a.arguments,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                "outcome": a.outcome,
                "operation_id": a.operation_id,
                "rejection_reason": a.rejection_reason,
                "tokens_used": a.tokens_used,
                "prompt_tokens": a.prompt_tokens,
                "completion_tokens": a.completion_tokens,
                "total_tokens": a.total_tokens,
                "step_started_at": a.step_started_at.isoformat() if a.step_started_at else None,
                "model_request_started_at": a.model_request_started_at.isoformat() if a.model_request_started_at else None,
                "model_response_received_at": a.model_response_received_at.isoformat() if a.model_response_received_at else None,
                "model_duration_ms": a.model_duration_ms,
                "framework_wait_ms": a.framework_wait_ms,
            } for a in actions
        ],
        "attestation": {
            "id": attestation.id,
            "entry_hash": attestation.entry_hash,
            "prev_hash": attestation.prev_hash,
            "signature": attestation.signature,
            "created_at": attestation.created_at.isoformat() if attestation.created_at else None
        } if attestation else None
    }

@router.get("/{id}/agent-actions")
async def get_agent_actions_endpoint(id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentAction).where(AgentAction.run_id == id).order_by(AgentAction.step_number, AgentAction.timestamp))
    actions = result.scalars().all()
    return [
        {
            "id": a.id,
            "step_number": a.step_number,
            "tool_name": a.tool_name,
            "arguments": a.arguments,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            "outcome": a.outcome,
            "operation_id": a.operation_id,
            "rejection_reason": a.rejection_reason,
            "tokens_used": a.tokens_used,
            "prompt_tokens": a.prompt_tokens,
            "completion_tokens": a.completion_tokens,
            "total_tokens": a.total_tokens,
            "step_started_at": a.step_started_at.isoformat() if a.step_started_at else None,
            "model_request_started_at": a.model_request_started_at.isoformat() if a.model_request_started_at else None,
            "model_response_received_at": a.model_response_received_at.isoformat() if a.model_response_received_at else None,
            "model_duration_ms": a.model_duration_ms,
            "framework_wait_ms": a.framework_wait_ms,
        } for a in actions
    ]
