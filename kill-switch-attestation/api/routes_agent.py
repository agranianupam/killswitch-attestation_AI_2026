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

@router.get("")
async def get_agent_state(db: AsyncSession = Depends(get_db)):
    
    result = await db.execute(select(Agent).where(Agent.name == "Research-Agent-01"))
    agent = result.scalar_one_or_none()
    if not agent:
        return {"error": "Demo agent not found"}
    return {
        "id": agent.id,
        "name": agent.name,
        "status": agent.status,
        "risk_level": agent.risk_level,
        "created_at": agent.created_at
    }

@router.get("/credentials")
async def get_agent_credentials(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.name == "Research-Agent-01"))
    agent = result.scalar_one_or_none()
    if not agent:
        return []
        
    result = await db.execute(select(Credential).where(Credential.agent_id == agent.id))
    creds = result.scalars().all()
    return [
        {
            "id": c.id,
            "channel_type": c.channel_type,
            "credential_value": c.credential_value,
            "status": c.status,
            "revoked_at": c.revoked_at
        } for c in creds
    ]

@router.get("/operations")
async def get_agent_operations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.name == "Research-Agent-01"))
    agent = result.scalar_one_or_none()
    if not agent:
        return []
        
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
