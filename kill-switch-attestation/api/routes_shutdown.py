"""
api/routes_shutdown.py
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import get_db
from models.agent import Agent
from services.orchestrator import run_shutdown
from api.auth import require_auth

router = APIRouter(prefix="/api/shutdown", tags=["shutdown"])

@router.post("")
async def trigger_shutdown(strategy: str = "A", trigger_type: str = "manual", db: AsyncSession = Depends(get_db), auth_user: str = Depends(require_auth)):
    if strategy not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Invalid strategy. Must be A, B, or C.")
        
    result = await db.execute(select(Agent).where(Agent.name == "Research-Agent-01"))
    agent = result.scalar_one_or_none()
    
    if agent:
        shutdown_result = await run_shutdown(db, agent.id, strategy, trigger_type, triggered_by=trigger_type)
    else:
        from services.orchestrator import execute_shutdown_cycle
        shutdown_result = await execute_shutdown_cycle(db, strategy=strategy, trigger_type=trigger_type, triggered_by=trigger_type)
        
    return shutdown_result

@router.post("/batch")
async def trigger_batch_shutdown(count: int = 5, strategy: str = "A", db: AsyncSession = Depends(get_db), auth_user: str = Depends(require_auth)):
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
                "latest_result": res
            }
        })
    return {"total": count, "completed": len(results), "results": results}

@router.get("/history")
async def get_shutdown_history(db: AsyncSession = Depends(get_db)):
    from models.shutdown_event import ShutdownEvent
    result = await db.execute(select(ShutdownEvent).order_by(ShutdownEvent.started_at.desc()))
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "strategy": e.strategy,
            "trigger_type": e.trigger_type,
            "triggered_by": e.triggered_by or e.trigger_type or "manual",
            "trigger_timestamp": (e.trigger_timestamp or e.started_at).isoformat() if (e.trigger_timestamp or e.started_at) else None,
            "started_at": e.started_at.isoformat() if e.started_at else None,
            "finished_at": e.finished_at.isoformat() if e.finished_at else None,
            "final_state": e.final_state,
            "residual_risk": e.residual_risk,
            "leaked_channels": e.leaked_channels,
            "in_flight_failures": e.in_flight_failures
        }
        for e in events
    ]

@router.get("/verify")
async def verify_chain_endpoint(db: AsyncSession = Depends(get_db)):
    from services.crypto_service import verify_chain, load_public_key
    try:
        public_key = load_public_key()
        res = await verify_chain(db, public_key)
        is_valid = res.get("valid", False)
        return {
            "status": "valid" if is_valid else "invalid",
            "valid": is_valid,
            "entries_checked": res.get("entries_checked", 0),
            "message": "Chain verified successfully" if is_valid else f"Broken chain at entry index {res.get('first_failure_index')}"
        }
    except Exception as e:
        return {"status": "error", "valid": False, "message": str(e)}

from pydantic import BaseModel
import config

class SettingsModel(BaseModel):
    net_delay_min: int | None = None
    net_delay_max: int | None = None
    revoke_failure_prob: float | None = None
    iam_failure_prob: float | None = None
    in_flight_leak_prob: float | None = None

@router.get("/settings")
async def get_settings():
    return {
        "net_delay_min": config.NET_DELAY_MIN,
        "net_delay_max": config.NET_DELAY_MAX,
        "revoke_failure_prob": config.REVOKE_FAILURE_PROB,
        "iam_failure_prob": config.IAM_FAILURE_PROB,
        "in_flight_leak_prob": config.IN_FLIGHT_LEAK_PROB,
    }

@router.post("/settings")
async def update_settings(s: SettingsModel, auth_user: str = Depends(require_auth)):
    if s.net_delay_min is not None: config.NET_DELAY_MIN = s.net_delay_min
    if s.net_delay_max is not None: config.NET_DELAY_MAX = s.net_delay_max
    if s.revoke_failure_prob is not None: config.REVOKE_FAILURE_PROB = s.revoke_failure_prob
    if s.iam_failure_prob is not None: config.IAM_FAILURE_PROB = s.iam_failure_prob
    if s.in_flight_leak_prob is not None: config.IN_FLIGHT_LEAK_PROB = s.in_flight_leak_prob
    return {"status": "ok", "settings": await get_settings()}


@router.get("/{id}/report")
async def get_shutdown_report(id: str, db: AsyncSession = Depends(get_db)):
    from models.shutdown_event import ShutdownEvent, RevocationEvent
    
    result = await db.execute(select(ShutdownEvent).where(ShutdownEvent.id == id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Shutdown event not found")
        
    rev_result = await db.execute(select(RevocationEvent).where(RevocationEvent.shutdown_event_id == id))
    revocations = rev_result.scalars().all()
    
    return {
        "id": event.id,
        "strategy": event.strategy,
        "trigger_type": event.trigger_type,
        "started_at": event.started_at,
        "finished_at": event.finished_at,
        "final_state": event.final_state,
        "residual_risk": event.residual_risk,
        "partial_failure": event.partial_failure,
        "leaked_channels": event.leaked_channels,
        "in_flight_failures": event.in_flight_failures,
        "revocations": [
            {
                "channel_type": r.channel_type,
                "latency_ms": r.latency_ms,
                "success": r.success,
                "retries": r.retries,
                "error": r.error
            } for r in revocations
        ]
    }
