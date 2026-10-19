import pytest
from sqlalchemy import select
from datetime import timedelta
import random
import uuid
import config
from models.database import utcnow
from models.agent import Agent
from models.credential import Credential, CHANNEL_TYPES
from models.operation import SimulatedOperation
from services.agent_service import seed_demo_agent
from services.orchestrator import run_shutdown, execute_shutdown_cycle

async def create_test_agent(db, name: str = None) -> Agent:
    agent_id = uuid.uuid4().hex
    agent = Agent(
        id=agent_id,
        name=name or f"Test-Agent-{agent_id[:8]}",
        status="ACTIVE",
        risk_level="LOW"
    )
    db.add(agent)
    for channel_type in CHANNEL_TYPES:
        cred = Credential(
            id=uuid.uuid4().hex,
            agent_id=agent.id,
            channel_type=channel_type,
            credential_value=f"mock-{channel_type}-{uuid.uuid4().hex[:6]}",
            status="ACTIVE"
        )
        db.add(cred)
    await db.commit()
    await db.refresh(agent)
    return agent

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
async def test_two_identical_seeded_cycles_produce_identical_outcomes(db_session):
    agent1 = await create_test_agent(db_session, "Agent-1")
    agent2 = await create_test_agent(db_session, "Agent-2")
    now = utcnow()
    for ag in (agent1, agent2):
        for _ in range(10):
            op = SimulatedOperation(
                id=uuid.uuid4().hex,
                agent_id=ag.id,
                operation_type="API_REQUEST",
                status="RUNNING",
                duration_ms=10000,
                started_at=now,
                natural_end_time=now + timedelta(seconds=10)
            )
            db_session.add(op)
    await db_session.commit()

    res1 = await run_shutdown(db_session, agent1.id, strategy="B", trigger_type="test", rng=random.Random(12345))
    res2 = await run_shutdown(db_session, agent2.id, strategy="B", trigger_type="test", rng=random.Random(12345))

    assert res1["in_flight_failures"] == res2["in_flight_failures"]
    assert res1["residual_risk"] == res2["residual_risk"]

    ops1 = (await db_session.execute(select(SimulatedOperation).where(SimulatedOperation.agent_id == agent1.id).order_by(SimulatedOperation.started_at))).scalars().all()
    ops2 = (await db_session.execute(select(SimulatedOperation).where(SimulatedOperation.agent_id == agent2.id).order_by(SimulatedOperation.started_at))).scalars().all()
    assert [op.status for op in ops1] == [op.status for op in ops2]

@pytest.mark.asyncio
async def test_strategy_classification_deterministic(db_session):
    agent_a = await create_test_agent(db_session, "Agent-A")
    agent_b = await create_test_agent(db_session, "Agent-B")
    agent_c = await create_test_agent(db_session, "Agent-C")
    now = utcnow()

    agents = [agent_a, agent_b, agent_c]
    for ag in agents:
        for _ in range(10):
            op = SimulatedOperation(
                id=uuid.uuid4().hex,
                agent_id=ag.id,
                operation_type="API_REQUEST",
                status="RUNNING",
                duration_ms=10000,
                started_at=now,
                natural_end_time=now + timedelta(seconds=10)
            )
            db_session.add(op)
    await db_session.commit()

    res_a = await run_shutdown(db_session, agent_a.id, strategy="A", trigger_type="test")
    res_b = await run_shutdown(db_session, agent_b.id, strategy="B", trigger_type="test", rng=random.Random(42))
    res_c = await run_shutdown(db_session, agent_c.id, strategy="C", trigger_type="test", rng=random.Random(42))

    assert res_a["in_flight_failures"] == 10
    ops_a = (await db_session.execute(select(SimulatedOperation).where(SimulatedOperation.agent_id == agent_a.id))).scalars().all()
    assert all(op.status == "COMPLETED_AFTER_SHUTDOWN" for op in ops_a)

    assert 0 <= res_b["in_flight_failures"] <= 10
    ops_b = (await db_session.execute(select(SimulatedOperation).where(SimulatedOperation.agent_id == agent_b.id))).scalars().all()
    completed_b = [op for op in ops_b if op.status == "COMPLETED_AFTER_SHUTDOWN"]
    cancelled_b = [op for op in ops_b if op.status == "CANCELLED"]
    assert len(completed_b) == res_b["in_flight_failures"]
    assert len(cancelled_b) == 10 - res_b["in_flight_failures"]

    assert res_c["in_flight_failures"] <= res_b["in_flight_failures"]
    ops_c = (await db_session.execute(select(SimulatedOperation).where(SimulatedOperation.agent_id == agent_c.id))).scalars().all()
    cancelled_c = [op for op in ops_c if op.status == "CANCELLED"]
    assert len(cancelled_c) >= len(cancelled_b)

@pytest.mark.asyncio
async def test_strategy_a_leaks_more_than_b_and_c(db_session):
    old_leak_prob = config.IN_FLIGHT_LEAK_PROB
    config.IN_FLIGHT_LEAK_PROB = 0.25

    try:
        agent_a = await create_test_agent(db_session, "Agent-Leak-A")
        agent_b = await create_test_agent(db_session, "Agent-Leak-B")
        agent_c = await create_test_agent(db_session, "Agent-Leak-C")
        now = utcnow()

        for ag in [agent_a, agent_b, agent_c]:
            for _ in range(20):
                op = SimulatedOperation(
                    id=uuid.uuid4().hex,
                    agent_id=ag.id,
                    operation_type="API_REQUEST",
                    status="RUNNING",
                    duration_ms=10000,
                    started_at=now,
                    natural_end_time=now + timedelta(seconds=10)
                )
                db_session.add(op)
        await db_session.commit()

        res_a = await run_shutdown(db_session, agent_a.id, strategy="A", trigger_type="test", rng=random.Random(42))
        res_b = await run_shutdown(db_session, agent_b.id, strategy="B", trigger_type="test", rng=random.Random(42))
        res_c = await run_shutdown(db_session, agent_c.id, strategy="C", trigger_type="test", rng=random.Random(42))

        leaks_a = res_a["in_flight_failures"]
        leaks_b = res_b["in_flight_failures"]
        leaks_c = res_c["in_flight_failures"]

        assert leaks_a == 20
        assert leaks_a > leaks_b
        assert leaks_a > leaks_c
        assert leaks_b >= leaks_c
    finally:
        config.IN_FLIGHT_LEAK_PROB = old_leak_prob
