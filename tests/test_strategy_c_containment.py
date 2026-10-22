"""
tests/test_strategy_c_containment.py - Comprehensive Regression Suite for Strategy C Containment

Validates:
1. Strategy A success & in-flight containment (CONTAINED).
2. Strategy B success with cancellation (TERMINATED).
3. Strategy C success when every channel is successfully revoked (TERMINATED, 0.0 risk).
4. Strategy C when IAM role revocation fails (CONTAINMENT_FAILED, 17.5% risk, critical alerts, never generic CONTAINED).
5. Strategy C when a revocation times out.
6. Strategy C when a channel remains accessible after revocation (probe detects liveness -> CONTAINMENT_FAILED).
7. Concurrent operation completion and exception handling (independent await, non-crashing).
8. Residual risk calculation correctness.
9. Audit-chain integrity (Ed25519 signatures & SHA-256 chain) across both successes and failures.
"""

import asyncio
import pytest
import random
from datetime import timedelta
from sqlalchemy import select

import config
from models.agent import Agent
from models.credential import Credential
from models.operation import SimulatedOperation, utcnow
from models.shutdown_event import ShutdownEvent, RevocationEvent
from models.alert import Alert
from services.agent_service import seed_demo_agent
from services.orchestrator import run_shutdown, compute_residual_risk
from services.crypto_service import load_public_key, verify_chain


@pytest.mark.asyncio
async def test_strategy_a_success_and_inflight_leak(db_session):
    """Strategy A: All channels revoked, but in-flight work completes after cutoff -> CONTAINED."""
    agent = await seed_demo_agent(db_session)
    now = utcnow()
    op = SimulatedOperation(
        id="op-strat-a-leak",
        agent_id=agent.id,
        operation_type="LONG_RUNNING_TASK",
        status="RUNNING",
        duration_ms=4000,
        started_at=now - timedelta(seconds=1),
        natural_end_time=now + timedelta(seconds=3)
    )
    db_session.add(op)
    await db_session.commit()

    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0

    res = await run_shutdown(db_session, agent.id, "A", "manual")
    assert res["final_state"] == "CONTAINED"
    assert res["in_flight_failures"] == 1
    assert res["leaked_channels"] == 0
    assert res["residual_risk"] == 0.3000

    # Chain remains valid
    pub = load_public_key()
    chain_res = await verify_chain(db_session, pub)
    assert chain_res["valid"] is True


@pytest.mark.asyncio
async def test_strategy_b_success_with_cancellation(db_session):
    """Strategy B: In-flight operations cancelled -> TERMINATED."""
    agent = await seed_demo_agent(db_session)
    now = utcnow()
    op = SimulatedOperation(
        id="op-strat-b-clean",
        agent_id=agent.id,
        operation_type="LONG_RUNNING_TASK",
        status="RUNNING",
        duration_ms=4000,
        started_at=now - timedelta(seconds=1),
        natural_end_time=now + timedelta(seconds=3)
    )
    db_session.add(op)
    await db_session.commit()

    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0
    # Seed rng so leak prob does not trigger
    rng = random.Random(42)

    res = await run_shutdown(db_session, agent.id, "B", "manual", rng=rng)
    assert res["final_state"] == "TERMINATED"
    assert res["in_flight_failures"] == 0
    assert res["residual_risk"] == 0.0


@pytest.mark.asyncio
async def test_strategy_c_clean_success_all_channels(db_session):
    """Strategy C: All channels successfully revoked, in-flight cancelled -> TERMINATED, 0.0 residual risk."""
    agent = await seed_demo_agent(db_session)
    now = utcnow()
    op = SimulatedOperation(
        id="op-strat-c-clean",
        agent_id=agent.id,
        operation_type="DATABASE_WRITE",
        status="RUNNING",
        duration_ms=3000,
        started_at=now - timedelta(seconds=1),
        natural_end_time=now + timedelta(seconds=2)
    )
    db_session.add(op)
    await db_session.commit()

    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0
    rng = random.Random(123)

    res = await run_shutdown(db_session, agent.id, "C", "manual", rng=rng)

    assert res["final_state"] == "TERMINATED"
    assert res["residual_risk"] == 0.0
    assert res["leaked_channels"] == 0
    assert res["in_flight_failures"] == 0
    assert res["partial_failure"] is False

    # Check database record
    sh_event = await db_session.get(ShutdownEvent, res["shutdown_event_id"])
    assert sh_event.final_state == "TERMINATED"
    assert sh_event.residual_risk == 0.0

    # Agent is TERMINATED, risk is LOW
    await db_session.refresh(agent)
    assert agent.status == "TERMINATED"
    assert agent.risk_level == "LOW"


@pytest.mark.asyncio
async def test_strategy_c_iam_role_revocation_failure_rejection(db_session):
    """
    Strategy C Failure: IAM role fails revocation after 2 retries.
    Must report CONTAINMENT_FAILED (NEVER CONTAINED), residual risk 17.5%, and emit critical alerts.
    """
    agent = await seed_demo_agent(db_session)
    now = utcnow()

    # Normal channels succeed, but IAM role 100% fails
    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 1.0
    config.REVOKE_RETRIES = 2

    res = await run_shutdown(db_session, agent.id, "C", "manual")

    # CRITICAL VERIFICATION: Must NEVER report CONTAINED when a channel failed revocation!
    assert res["final_state"] == "CONTAINMENT_FAILED"
    assert res["final_state"] != "CONTAINED"
    assert res["final_state"] != "TERMINATED"
    assert res["partial_failure"] is True

    # Check 17.5% residual risk: 0.50*(1/4) + 0.20*(1/4) = 0.175
    assert res["residual_risk"] == 0.1750
    assert res["leaked_channels"] == 1

    # Check agent risk level is HIGH
    await db_session.refresh(agent)
    assert agent.status == "CONTAINMENT_FAILED"
    assert agent.risk_level == "HIGH"

    # Verify revocation events: IAM role attempted 2 retries and failed
    sh_id = res["shutdown_event_id"]
    rev_res = await db_session.execute(
        select(RevocationEvent).where(RevocationEvent.shutdown_event_id == sh_id)
    )
    revs = rev_res.scalars().all()
    assert len(revs) == 4

    iam_rev = next(r for r in revs if r.channel_type == "iam_role")
    assert iam_rev.success is False
    assert iam_rev.retries == 2
    assert "IAM propagation timeout or permission denied" in iam_rev.error

    # Verify both critical alerts were created
    alert_res = await db_session.execute(
        select(Alert).where(Alert.experiment_id == sh_id)
    )
    alerts = alert_res.scalars().all()
    alert_titles = {a.title for a in alerts}
    assert "Channel Revocation Failed: IAM_ROLE" in alert_titles
    assert "Channel Probe Detected Liveness" in alert_titles

    # Verify cryptographic chain remains valid even with containment failure
    pub = load_public_key()
    chain_res = await verify_chain(db_session, pub)
    assert chain_res["valid"] is True

    config.IAM_FAILURE_PROB = 0.0


@pytest.mark.asyncio
async def test_strategy_c_revocation_timeout(db_session, monkeypatch):
    """Strategy C: Revocation times out on a channel -> captured, non-crashing, CONTAINMENT_FAILED."""
    agent = await seed_demo_agent(db_session)

    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0

    import services.orchestrator as orch_mod

    # Simulate timeout by wrapping revoke_credential to raise asyncio.TimeoutError for iam_role
    orig_revoke = orch_mod.revoke_credential

    async def mock_timeout_revoke(db, credential_id, **kwargs):
        cred = await db.get(Credential, credential_id)
        if cred and cred.channel_type == "iam_role":
            raise asyncio.TimeoutError()
        return await orig_revoke(db, credential_id, **kwargs)

    monkeypatch.setattr(orch_mod, "revoke_credential", mock_timeout_revoke)

    res = await run_shutdown(db_session, agent.id, "C", "manual")

    assert res["final_state"] == "CONTAINMENT_FAILED"
    assert res["partial_failure"] is True
    assert res["residual_risk"] > 0.0

    # Verify timeout was recorded on RevocationEvent
    sh_id = res["shutdown_event_id"]
    rev_res = await db_session.execute(
        select(RevocationEvent).where(RevocationEvent.shutdown_event_id == sh_id)
    )
    revs = rev_res.scalars().all()
    iam_rev = next(r for r in revs if r.channel_type == "iam_role")
    assert iam_rev.success is False
    assert "timeout" in iam_rev.error.lower()


@pytest.mark.asyncio
async def test_strategy_c_channel_remains_accessible_via_probe(db_session):
    """Strategy C: Channel probe detects liveness even if revocation succeeded -> CONTAINMENT_FAILED."""
    from services.adversarial_agent import AdversarialAgentConfig

    agent = await seed_demo_agent(db_session)
    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0

    # Injects probe failure
    cfg = AdversarialAgentConfig(
        profile="cooperative",
        fault_injection_type="failed_probe",
        execution_mode="local"
    )

    res = await run_shutdown(db_session, agent.id, "C", "adversarial", agent_config=cfg)

    # Liveness probe detected channel -> Must be CONTAINMENT_FAILED
    assert res["leaked_channels"] > 0
    assert res["final_state"] == "CONTAINMENT_FAILED"
    assert res["final_state"] != "CONTAINED"
    assert res["partial_failure"] is True


@pytest.mark.asyncio
async def test_strategy_c_concurrent_exception_resilience(db_session, monkeypatch):
    """Strategy C: One channel throws unexpected exception during gather -> other 3 succeed, collected safely."""
    agent = await seed_demo_agent(db_session)
    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0

    import services.orchestrator as orch_mod
    orig_revoke_retries = orch_mod._revoke_with_retries

    async def mock_crashing_task(credential_id, channel_type, shutdown_event_id, **kwargs):
        if channel_type == "iam_role":
            raise RuntimeError("Underlying network connection dropped violently")
        return await orig_revoke_retries(credential_id, channel_type, shutdown_event_id, **kwargs)

    monkeypatch.setattr(orch_mod, "_revoke_with_retries", mock_crashing_task)

    # run_shutdown should NOT crash
    res = await run_shutdown(db_session, agent.id, "C", "manual")
    assert res["final_state"] == "CONTAINMENT_FAILED"
    assert res["partial_failure"] is True

    # Verify all 4 revocation events were recorded
    sh_id = res["shutdown_event_id"]
    rev_res = await db_session.execute(
        select(RevocationEvent).where(RevocationEvent.shutdown_event_id == sh_id)
    )
    revs = rev_res.scalars().all()
    assert len(revs) == 4

    iam_rev = next(r for r in revs if r.channel_type == "iam_role")
    assert iam_rev.success is False
    assert "network connection dropped" in iam_rev.error


@pytest.mark.asyncio
async def test_residual_risk_canonical_formula_accuracy():
    """Verify residual risk weights and boundary behaviors."""
    # Clean state
    assert compute_residual_risk(0, 0, 0, 4, 0) == 0.0

    # Strategy C IAM failure with probe liveness
    assert compute_residual_risk(1, 0, 1, 4, 0) == 0.1750

    # In-flight leak only under Strategy A
    assert compute_residual_risk(0, 1, 0, 4, 1) == 0.3000

    # Maximum compound risk across all channels and operations
    assert compute_residual_risk(4, 2, 4, 4, 2) == 1.0000


@pytest.mark.asyncio
async def test_audit_chain_integrity_across_success_and_failure(db_session):
    """Verify audit chain remains continuously valid across alternating clean and failed Strategy C runs."""
    pub = load_public_key()

    # 1. Successful Strategy C run
    agent1 = await seed_demo_agent(db_session)
    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0
    res1 = await run_shutdown(db_session, agent1.id, "C", "manual", rng=random.Random(1))
    assert res1["final_state"] == "TERMINATED"

    chain1 = await verify_chain(db_session, pub)
    assert chain1["valid"] is True

    # 2. Failed Strategy C run (forced IAM failure)
    agent2 = await seed_demo_agent(db_session)
    config.IAM_FAILURE_PROB = 1.0
    res2 = await run_shutdown(db_session, agent2.id, "C", "manual", rng=random.Random(2))
    assert res2["final_state"] == "CONTAINMENT_FAILED"

    chain2 = await verify_chain(db_session, pub)
    assert chain2["valid"] is True

    config.IAM_FAILURE_PROB = 0.0
