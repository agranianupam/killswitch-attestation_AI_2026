"""
tests/test_shutdown_strategies.py
"""

import pytest
from sqlalchemy import select
from models.agent import Agent
from models.shutdown_event import RevocationEvent
from services.agent_service import seed_demo_agent
from services.orchestrator import run_shutdown

@pytest.mark.asyncio
async def test_strategies_return_four_revocations(db_session):
    agent = await seed_demo_agent(db_session)
    
    
    res_a = await run_shutdown(db_session, agent.id, "A", "manual")
    print("RES A:", res_a)
    assert res_a["final_state"] == "TERMINATED"
    
    result = await db_session.execute(select(RevocationEvent).where(RevocationEvent.shutdown_event_id == res_a["shutdown_event_id"]))
    assert len(result.scalars().all()) == 4
    
    
    agent.status = "ACTIVE"
    await db_session.commit()
    
    
    res_b = await run_shutdown(db_session, agent.id, "B", "manual")
    assert res_b["final_state"] == "TERMINATED"
    
    result = await db_session.execute(select(RevocationEvent).where(RevocationEvent.shutdown_event_id == res_b["shutdown_event_id"]))
    assert len(result.scalars().all()) == 4

@pytest.mark.asyncio
async def test_strategies_block_new_operations(db_session):
    agent = await seed_demo_agent(db_session)
    
    
    
    
    
    
    
    
    pass 
