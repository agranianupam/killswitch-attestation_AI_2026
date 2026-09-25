"""
tests/test_in_flight.py
"""

import pytest
from sqlalchemy import select
from datetime import timedelta
from models.database import utcnow
from models.operation import SimulatedOperation
from services.agent_service import seed_demo_agent
from services.orchestrator import run_shutdown
import uuid

@pytest.mark.asyncio
async def test_in_flight_classification_strategy_A_B(db_session):
    agent = await seed_demo_agent(db_session)
    
    now = utcnow()
    
    op = SimulatedOperation(
        id=uuid.uuid4().hex,
        agent_id=agent.id,
        operation_type="API_REQUEST",
        status="RUNNING",
        duration_ms=10000,
        started_at=now,
        natural_end_time=now + timedelta(seconds=10)
    )
    db_session.add(op)
    await db_session.commit()
    
    await run_shutdown(db_session, agent.id, "A", "manual")
    
    await db_session.refresh(op)
    assert op.status == "COMPLETED_AFTER_SHUTDOWN"

@pytest.mark.asyncio
async def test_in_flight_classification_strategy_C(db_session):
    agent = await seed_demo_agent(db_session)
    
    now = utcnow()
    op = SimulatedOperation(
        id=uuid.uuid4().hex,
        agent_id=agent.id,
        operation_type="API_REQUEST",
        status="RUNNING",
        duration_ms=10000,
        started_at=now,
        natural_end_time=now + timedelta(seconds=10)
    )
    db_session.add(op)
    await db_session.commit()
    
    await run_shutdown(db_session, agent.id, "C", "manual")
    
    await db_session.refresh(op)
    assert op.status == "CANCELLED"
