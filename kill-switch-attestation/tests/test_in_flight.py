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

@pytest.mark.asyncio
async def test_kill_between_agent_steps(db_session):
    agent = await create_test_agent(db_session, "Agent-Between-Steps")
    now = utcnow()
    op1 = SimulatedOperation(
        id=uuid.uuid4().hex,
        agent_id=agent.id,
        operation_type="API_REQUEST",
        status="RUNNING",
        duration_ms=1000,
        started_at=now - timedelta(seconds=5),
        natural_end_time=now - timedelta(seconds=4)
    )
    db_session.add(op1)
    await db_session.commit()

    res = await run_shutdown(db_session, agent.id, strategy="A", trigger_type="test")
    await db_session.refresh(op1)

    assert op1.status == "COMPLETED"
    assert op1.completed_at == op1.natural_end_time
    assert res["actions_started"] == 1
    assert res["actions_completed"] == 1
    assert res["actions_running"] == 0
    assert res["in_flight_failures"] == 0
    assert res["residual_risk"] == 0.0

@pytest.mark.asyncio
async def test_kill_while_operation_running(db_session):
    agent = await create_test_agent(db_session, "Agent-Running-Kill")
    now = utcnow()
    op = SimulatedOperation(
        id=uuid.uuid4().hex,
        agent_id=agent.id,
        operation_type="API_REQUEST",
        status="RUNNING",
        duration_ms=5000,
        started_at=now - timedelta(milliseconds=500),
        natural_end_time=now + timedelta(milliseconds=4500)
    )
    db_session.add(op)
    await db_session.commit()

    res = await run_shutdown(db_session, agent.id, strategy="A", trigger_type="test")
    await db_session.refresh(op)

    assert op.status == "COMPLETED_AFTER_SHUTDOWN"
    assert res["actions_started"] == 1
    assert res["actions_completed"] == 0
    assert res["actions_running"] == 1
    assert res["in_flight_failures"] == 1

@pytest.mark.asyncio
async def test_kill_when_no_operation_in_flight(db_session):
    agent = await create_test_agent(db_session, "Agent-Zero-In-Flight")
    res = await run_shutdown(db_session, agent.id, strategy="B", trigger_type="test")

    assert res["actions_started"] == 0
    assert res["actions_running"] == 0
    assert res["actions_completed"] == 0
    assert res["in_flight_failures"] == 0
    assert res["residual_risk"] == 0.0

@pytest.mark.asyncio
async def test_operation_cancelled_before_completion(db_session):
    agent = await create_test_agent(db_session, "Agent-Cancel-Test")
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

    res = await run_shutdown(db_session, agent.id, strategy="C", trigger_type="test", rng=random.Random(42))
    await db_session.refresh(op)

    assert op.status == "CANCELLED"
    assert res["actions_running"] == 1
    assert res["in_flight_failures"] == 0

@pytest.mark.asyncio
async def test_operation_completing_after_kill(db_session):
    agent = await create_test_agent(db_session, "Agent-Leak-Test")
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

    res = await run_shutdown(db_session, agent.id, strategy="A", trigger_type="test")
    await db_session.refresh(op)

    assert op.status == "COMPLETED_AFTER_SHUTDOWN"
    assert op.completed_at == op.natural_end_time
    assert res["actions_running"] == 1
    assert res["in_flight_failures"] == 1

@pytest.mark.asyncio
async def test_multiple_simultaneous_in_flight_operations(db_session):
    agent = await create_test_agent(db_session, "Agent-Multi-Inflight")
    now = utcnow()
    ops = []
    for _ in range(5):
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
        ops.append(op)
    await db_session.commit()

    res = await run_shutdown(db_session, agent.id, strategy="A", trigger_type="test")
    assert res["actions_running"] == 5
    assert res["in_flight_failures"] == 5

    for op in ops:
        await db_session.refresh(op)
        assert op.status == "COMPLETED_AFTER_SHUTDOWN"

@pytest.mark.asyncio
async def test_concurrent_operation_state_updates(db_session):
    from services.operation_service import _complete_operation

    agent = await create_test_agent(db_session, "Agent-Concurrent-Update")
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

    res = await run_shutdown(db_session, agent.id, strategy="C", trigger_type="test", rng=random.Random(42))
    await db_session.refresh(op)
    assert op.status == "CANCELLED"

    await _complete_operation(op.id, 0)
    await db_session.refresh(op)
    assert op.status == "CANCELLED"

@pytest.mark.asyncio
async def test_zero_exposure_runs(client, auth_headers):
    from models.shutdown_event import ShutdownEvent
    from models.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        agent = await create_test_agent(db, "Agent-Zero-Exp-Analytics")
        now = utcnow()
        op = SimulatedOperation(
            id=uuid.uuid4().hex,
            agent_id=agent.id,
            operation_type="API_REQUEST",
            status="RUNNING",
            duration_ms=500,
            started_at=now - timedelta(seconds=5),
            natural_end_time=now - timedelta(seconds=4)
        )
        db.add(op)
        await db.commit()
        await run_shutdown(db, agent.id, strategy="B", trigger_type="test")

    res = client.get("/api/analytics/exposure?include_scripted=true", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["exposed_runs"] == 0
    assert data["unexposed_runs"] >= 1
    assert data["leak_rate_exposed"] == 0.0

@pytest.mark.asyncio
async def test_consistency_between_recorded_counters_and_leak_rates(db_session, client, auth_headers):
    from models.shutdown_event import ShutdownEvent

    del_stmt = select(ShutdownEvent)
    existing = (await db_session.execute(del_stmt)).scalars().all()
    for e in existing:
        await db_session.delete(e)
    await db_session.commit()

    agent1 = await create_test_agent(db_session, "Agent-Consistency-1")
    res1 = await run_shutdown(db_session, agent1.id, strategy="A", trigger_type="test")

    agent2 = await create_test_agent(db_session, "Agent-Consistency-2")
    now = utcnow()
    for _ in range(2):
        op = SimulatedOperation(
            id=uuid.uuid4().hex,
            agent_id=agent2.id,
            operation_type="API_REQUEST",
            status="RUNNING",
            duration_ms=10000,
            started_at=now,
            natural_end_time=now + timedelta(seconds=10)
        )
        db_session.add(op)
    await db_session.commit()
    res2 = await run_shutdown(db_session, agent2.id, strategy="A", trigger_type="test")

    agent3 = await create_test_agent(db_session, "Agent-Consistency-3")
    res3 = await run_shutdown(db_session, agent3.id, strategy="A", trigger_type="test")
    sh3 = await db_session.get(ShutdownEvent, res3["shutdown_event_id"])
    sh3.partial_failure = True
    sh3.leaked_channels = 0
    await db_session.commit()

    agent4 = await create_test_agent(db_session, "Agent-Consistency-4")
    res4 = await run_shutdown(db_session, agent4.id, strategy="A", trigger_type="test")
    sh4 = await db_session.get(ShutdownEvent, res4["shutdown_event_id"])
    sh4.leaked_channels = 1
    sh4.partial_failure = True
    await db_session.commit()

    events = (await db_session.execute(select(ShutdownEvent))).scalars().all()
    for e in events:
        assert (e.actions_started or 0) == (e.actions_running or 0) + (e.actions_completed or 0)
        assert (e.in_flight_failures or 0) <= (e.actions_running or 0)

    summary_res = client.get("/api/analytics/summary?include_scripted=true", headers=auth_headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()

    assert summary["total_shutdowns"] == 4
    assert summary["exposed_runs"] == 1
    assert summary["runs_with_leaks"] == 2
    assert summary["leak_rate_all"] == 50.0
    assert summary["leak_rate_in_flight"] == 100.0

    matrix = summary["outcome_matrix_2x2"]
    total_matrix = matrix["pass_no_leak"] + matrix["pass_with_leak"] + matrix["fail_no_leak"] + matrix["fail_with_leak"]
    assert total_matrix == 4
    assert matrix["pass_no_leak"] == 1
    assert matrix["pass_with_leak"] == 1
    assert matrix["fail_no_leak"] == 1
    assert matrix["fail_with_leak"] == 1
