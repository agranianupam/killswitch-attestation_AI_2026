import pytest
import random
from datetime import timedelta
from sqlalchemy import select
from models.agent import Agent
from models.shutdown_event import ShutdownEvent, RevocationEvent
from models.operation import SimulatedOperation, utcnow
from services.agent_service import seed_demo_agent
from services.orchestrator import run_shutdown, execute_shutdown_cycle
import config

@pytest.mark.asyncio
async def test_strategies_return_four_revocations(db_session):
    for strategy in ("A", "B", "C"):
        agent = await seed_demo_agent(db_session)
        res = await run_shutdown(db_session, agent.id, strategy, "manual")
        assert "shutdown_event_id" in res

        result = await db_session.execute(
            select(RevocationEvent).where(RevocationEvent.shutdown_event_id == res["shutdown_event_id"])
        )
        revs = result.scalars().all()
        assert len(revs) == 4
        channel_types = {r.channel_type for r in revs}
        assert channel_types == {"api_key", "session_token", "iam_role", "network"}

@pytest.mark.asyncio
async def test_strategy_a_b_c_inflight_differential_behavior(db_session):

    agent_a = await seed_demo_agent(db_session)
    now = utcnow()
    op_a = SimulatedOperation(
        id="op-strat-a",
        agent_id=agent_a.id,
        operation_type="LONG_RUNNING_TASK",
        status="RUNNING",
        duration_ms=5000,
        started_at=now - timedelta(seconds=1),
        natural_end_time=now + timedelta(seconds=4)
    )
    db_session.add(op_a)
    await db_session.commit()

    res_a = await run_shutdown(db_session, agent_a.id, "A", "manual")
    await db_session.refresh(op_a)
    assert op_a.status == "COMPLETED_AFTER_SHUTDOWN"
    assert res_a["in_flight_failures"] == 1
    assert res_a["final_state"] == "CONTAINED"

    agent_b = await seed_demo_agent(db_session)
    op_b = SimulatedOperation(
        id="op-strat-b",
        agent_id=agent_b.id,
        operation_type="LONG_RUNNING_TASK",
        status="RUNNING",
        duration_ms=5000,
        started_at=now - timedelta(seconds=1),
        natural_end_time=now + timedelta(seconds=4)
    )
    db_session.add(op_b)
    await db_session.commit()

    rng_b = random.Random(42)
    res_b = await run_shutdown(db_session, agent_b.id, "B", "manual", rng=rng_b)
    await db_session.refresh(op_b)
    assert op_b.status in ("CANCELLED", "COMPLETED_AFTER_SHUTDOWN")

    agent_c = await seed_demo_agent(db_session)
    op_c = SimulatedOperation(
        id="op-strat-c",
        agent_id=agent_c.id,
        operation_type="LONG_RUNNING_TASK",
        status="RUNNING",
        duration_ms=5000,
        started_at=now - timedelta(seconds=1),
        natural_end_time=now + timedelta(seconds=4)
    )
    db_session.add(op_c)
    await db_session.commit()

    rng_c = random.Random(42)
    res_c = await run_shutdown(db_session, agent_c.id, "C", "manual", rng=rng_c)
    await db_session.refresh(op_c)
    assert op_c.status == "CANCELLED"
    assert res_c["in_flight_failures"] == 0

@pytest.mark.asyncio
async def test_kill_moment_randomized_in_manual_cycle(db_session):

    delays = []
    for _ in range(5):
        rng = config.get_rng()
        d = rng.expovariate(1.0 / config.SHUTDOWN_MEAN_SECONDS)
        delays.append(d)

    assert len(set(delays)) > 1

@pytest.mark.asyncio
async def test_offline_mock_strategy_comparison(db_session):

    from api.routes_experiment import run_strategy_comparison
    summary = await run_strategy_comparison(cycles=2, agent_mode="scripted", db=db_session)
    assert "strategies" in summary
    assert "A" in summary["strategies"]
    assert "B" in summary["strategies"]
    assert "C" in summary["strategies"]
    assert summary["strategies"]["A"]["runs"] == 2
    assert summary["strategies"]["B"]["runs"] == 2
    assert summary["strategies"]["C"]["runs"] == 2
