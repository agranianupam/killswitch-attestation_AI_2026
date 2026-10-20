from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from models.database import get_db
from models.agent import Agent
from models.credential import Credential
from models.operation import SimulatedOperation
from services.quota_service import get_calls_today, is_budget_paused
import config

router = APIRouter(prefix="/api/agent", tags=["agent"])

async def _get_current_agent(db: AsyncSession) -> Agent:
    result = await db.execute(select(Agent).order_by(desc(Agent.created_at)).limit(1))
    agent = result.scalar_one_or_none()
    if not agent:
        from services.agent_service import provision_fresh_agent
        agent = await provision_fresh_agent(db)
    return agent

@router.get("/status")
async def get_agent_status():
    key = getattr(config, "GEMINI_API_KEY", "")
    key_status = "configured" if (key and key != "PASTE_YOUR_GEMINI_API_KEY_HERE") else "missing"
    return {
        "key_status": key_status,
        "model": getattr(config, "AGENT_MODEL", "gemini-3.5-flash-lite"),
        "mode": getattr(config, "AGENT_MODE", "Gemini"),
        "calls_used_today": get_calls_today(),
        "max_calls_per_day": config.GEMINI_MAX_CALLS_PER_DAY,
        "daily_budget_reached": is_budget_paused()
    }

@router.get("")
async def get_agent_state(db: AsyncSession = Depends(get_db)):
    agent = await _get_current_agent(db)
    return {
        "id": agent.id,
        "name": agent.name,
        "status": agent.status,
        "risk_level": agent.risk_level,
        "created_at": agent.created_at
    }

@router.get("/credentials")
async def get_agent_credentials(db: AsyncSession = Depends(get_db)):
    agent = await _get_current_agent(db)
    result = await db.execute(select(Credential).where(Credential.agent_id == agent.id))
    creds = result.scalars().all()
    return [
        {
            "id": c.id,
            "channel_type": c.channel_type,
            "credential_value": (c.credential_value[:6] + "••••••••" + c.credential_value[-4:]) if len(c.credential_value) > 10 else "••••••••••••",
            "status": c.status,
            "revoked_at": c.revoked_at
        } for c in creds
    ]

@router.get("/operations")
async def get_agent_operations(db: AsyncSession = Depends(get_db)):
    agent = await _get_current_agent(db)
    result = await db.execute(
        select(SimulatedOperation)
        .where(SimulatedOperation.agent_id == agent.id)
        .order_by(desc(SimulatedOperation.started_at))
        .limit(50)
    )
    ops = result.scalars().all()
    return [
        {
            "id": o.id,
            "operation_type": o.operation_type,
            "status": o.status,
            "duration_ms": o.duration_ms,
            "started_at": o.started_at,
            "natural_end_time": o.natural_end_time,
            "completed_at": o.completed_at
        } for o in ops
    ]
