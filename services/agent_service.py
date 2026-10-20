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

async def provision_fresh_agent(db: AsyncSession) -> Agent:
    agent_id = uuid.uuid4().hex
    agent = Agent(
        id=agent_id,
        name=f"Sandboxed-Agent-{agent_id[:8]}",
        status="ACTIVE",
        risk_level="LOW"
    )
    db.add(agent)
    for channel_type in CHANNEL_TYPES:
        cred_val = f"mock-{channel_type}-{uuid.uuid4().hex[:6]}"
        cred = Credential(
            id=uuid.uuid4().hex,
            agent_id=agent.id,
            channel_type=channel_type,
            credential_value=cred_val,
            status="ACTIVE"
        )
        db.add(cred)
    await db.commit()
    await db.refresh(agent)
    return agent

async def seed_demo_agent(db: AsyncSession) -> Agent:
    return await provision_fresh_agent(db)
