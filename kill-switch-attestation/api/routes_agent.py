"""
api/routes_agent.py
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from models.database import get_db
from models.agent import Agent
from models.credential import Credential
from models.operation import SimulatedOperation

router = APIRouter(prefix="/api/agent", tags=["agent"])

async def _get_current_agent(db: AsyncSession) -> Agent:
    # 1. Try Research-Agent-01
    result = await db.execute(select(Agent).where(Agent.name == "Research-Agent-01"))
    agent = result.scalar_one_or_none()
    if not agent:
        # 2. Try most recently created sandboxed agent
        result = await db.execute(select(Agent).order_by(desc(Agent.created_at)).limit(1))
        agent = result.scalar_one_or_none()
    if not agent:
        # 3. Seed agent on demand so Agent Details has valid active credentials
        from services.agent_service import seed_demo_agent
        agent = await seed_demo_agent(db)
    return agent

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
        .limit(20)
    )
    ops = result.scalars().all()
    return [
        {
            "id": op.id,
            "operation_type": op.operation_type,
            "status": op.status,
            "duration_ms": op.duration_ms,
            "started_at": op.started_at,
            "completed_at": op.completed_at
        } for op in ops
    ]
