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


@pytest.mark.asyncio
async def test_strategy_a_leaks_more_than_b_and_c(db_session):
    """Verifies that in-flight ops continue under Strategy A, causing more leaks than B and C."""
    from services.orchestrator import execute_shutdown_cycle
    import config

    config.IN_FLIGHT_LEAK_PROB = 0.20
    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0

    leaks_a = 0
    leaks_b = 0
    leaks_c = 0

    runs_per_strat = 5

    for _ in range(runs_per_strat):
        res_a = await execute_shutdown_cycle(db_session, strategy="A", trigger_type="test", triggered_by="test")
        leaks_a += res_a.get("in_flight_failures", 0)

        res_b = await execute_shutdown_cycle(db_session, strategy="B", trigger_type="test", triggered_by="test")
        leaks_b += res_b.get("in_flight_failures", 0)

        res_c = await execute_shutdown_cycle(db_session, strategy="C", trigger_type="test", triggered_by="test")
        leaks_c += res_c.get("in_flight_failures", 0)

    # Strategy A continues all in-flight ops
    assert leaks_a >= leaks_b
    assert leaks_b >= leaks_c
    assert leaks_a > leaks_c
    assert leaks_a >= runs_per_strat * 3

