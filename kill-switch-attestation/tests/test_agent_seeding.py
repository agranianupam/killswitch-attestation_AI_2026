"""
tests/test_agent_seeding.py
"""

import pytest
from sqlalchemy import select
from models.agent import Agent
from models.credential import Credential
from services.agent_service import seed_demo_agent

@pytest.mark.asyncio
async def test_agent_seeding(db_session):
    
    agent = await seed_demo_agent(db_session)
    
    assert agent is not None
    assert agent.name == "Research-Agent-01"
    
    result = await db_session.execute(select(Credential).where(Credential.agent_id == agent.id))
    creds = result.scalars().all()
    
    assert len(creds) == 4
    types = {c.channel_type for c in creds}
    assert types == {"api_key", "session_token", "iam_role", "external_tool"}
    
    
    agent_2 = await seed_demo_agent(db_session)
    assert agent_2.id == agent.id
    
    result = await db_session.execute(select(Credential).where(Credential.agent_id == agent.id))
    creds_2 = result.scalars().all()
    assert len(creds_2) == 4
