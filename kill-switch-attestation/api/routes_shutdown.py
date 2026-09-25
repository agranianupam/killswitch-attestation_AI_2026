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
async def trigger_shutdown(strategy: str, trigger_type: str = "manual", db: AsyncSession = Depends(get_db), auth_user: str = Depends(require_auth)):
    if strategy not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Invalid strategy. Must be A, B, or C.")
        
    result = await db.execute(select(Agent).where(Agent.name == "Research-Agent-01"))
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Demo agent not found")
        
    
    shutdown_result = await run_shutdown(db, agent.id, strategy, trigger_type)
    
    return shutdown_result

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
