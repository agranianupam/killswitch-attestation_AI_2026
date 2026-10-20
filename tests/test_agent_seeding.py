import pytest
from sqlalchemy import select
from models.agent import Agent
from models.credential import Credential
from services.agent_service import provision_fresh_agent

@pytest.mark.asyncio
async def test_agent_seeding(db_session):
    agent = await provision_fresh_agent(db_session)
    assert agent is not None
    assert agent.name.startswith("Sandboxed-Agent-")

    result = await db_session.execute(select(Credential).where(Credential.agent_id == agent.id))
    creds = result.scalars().all()

    assert len(creds) == 4
    types = {c.channel_type for c in creds}
    assert types == {"api_key", "session_token", "iam_role", "network"}
    for c in creds:
        assert c.status == "ACTIVE"

    agent_2 = await provision_fresh_agent(db_session)
    assert agent_2.id != agent.id
    result_2 = await db_session.execute(select(Credential).where(Credential.agent_id == agent_2.id))
    creds_2 = result_2.scalars().all()
    assert len(creds_2) == 4
    for c in creds_2:
        assert c.status == "ACTIVE"
