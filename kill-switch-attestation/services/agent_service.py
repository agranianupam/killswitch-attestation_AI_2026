"""
services/agent_service.py — FR-1: Seed, CRUD
"""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.agent import Agent
from models.credential import Credential, CHANNEL_TYPES


async def get_agent(db: AsyncSession, agent_id: str) -> Agent | None:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    return result.scalar_one_or_none()


async def get_agent_by_name(db: AsyncSession, name: str) -> Agent | None:
    result = await db.execute(select(Agent).where(Agent.name == name))
    return result.scalar_one_or_none()


async def seed_demo_agent(db: AsyncSession) -> Agent:
    """Seeds Research-Agent-01 and its 4 credentials if it doesn't exist."""
    agent_name = "Research-Agent-01"
    agent = await get_agent_by_name(db, agent_name)

    if not agent:
        agent = Agent(
            id=uuid.uuid4().hex,
            name=agent_name,
            status="ACTIVE",
            risk_level="LOW"
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)

    
    result = await db.execute(select(Credential).where(Credential.agent_id == agent.id))
    existing_creds = result.scalars().all()
    existing_types = {c.channel_type for c in existing_creds}

    for channel_type in CHANNEL_TYPES:
        if channel_type not in existing_types:
            cred_val = f"mock-{channel_type}-{uuid.uuid4().hex[:6]}"
            new_cred = Credential(
                id=uuid.uuid4().hex,
                agent_id=agent.id,
                channel_type=channel_type,
                credential_value=cred_val,
                status="ACTIVE"
            )
            db.add(new_cred)

    await db.commit()
    return agent
