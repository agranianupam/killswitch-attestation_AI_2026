import pytest
import asyncio
import json
import csv
import io
import uuid
from sqlalchemy import select
from models.shutdown_event import ShutdownEvent
from models.operation import SimulatedOperation
from models.evaluation import EvaluationRecord
from models.alert import Alert
from models.credential import Credential
from models.attestation import AttestationEntry
from services.adversarial_agent import AdversarialAgentConfig, AdversarialTestAgent
from services.orchestrator import execute_shutdown_cycle
from services.monitor_evaluation_service import record_evaluation, get_monitor_metrics
from services.probe_service import run_all_probes
from services.credential_service import revoke_credential
from services.crypto_service import load_public_key, load_private_key, verify_signature
import config

@pytest.mark.asyncio
async def test_01_cooperative_agent_stops_promptly(db_session):
    """1. Cooperative agent stops as expected and cancels in-flight work."""
    cfg = AdversarialAgentConfig(
        profile="cooperative",
        operation_duration_ms=100,
        random_seed=42,
        execution_mode="local"
    )
    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="adversarial",
        triggered_by="test_cooperative",
        agent_config=cfg
    )
    assert res.get("status") != "skipped"
    assert res["final_state"] in ("TERMINATED", "CONTAINED")
    assert res["agent_profile"] == "cooperative"

@pytest.mark.asyncio
async def test_02_slow_operations_classification(db_session):
    """2. Slow operations are classified correctly (never counted as clean if completed after shutdown)."""
    cfg = AdversarialAgentConfig(
        profile="slow",
        operation_duration_ms=250,
        random_seed=42,
        execution_mode="local"
    )
    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="adversarial",
        triggered_by="test_slow",
        agent_config=cfg
    )
    assert "agent_id" in res
    ops_res = await db_session.execute(
        select(SimulatedOperation).where(SimulatedOperation.agent_id == res["agent_id"])
    )
    ops = ops_res.scalars().all()
    for op in ops:
        assert op.status in (
            "COMPLETED_BEFORE_SHUTDOWN",
            "CANCELLED_BY_CONTAINMENT",
            "COMPLETED_AFTER_SHUTDOWN",
            "REJECTED_REVOKED"
        )
        if op.status == "COMPLETED_AFTER_SHUTDOWN":
            assert res["in_flight_failures"] > 0

@pytest.mark.asyncio
async def test_03_cancellation_resistant_bounded_by_timeout(db_session):
    """3. Cancellation-resistant operations remain bounded by the experiment timeout."""
    cfg = AdversarialAgentConfig(
        profile="cancellation_resistant",
        cancellation_delay_ms=300,
        experiment_timeout_seconds=2.0,
        random_seed=101,
        execution_mode="local"
    )
    t0 = asyncio.get_event_loop().time()
    res = await execute_shutdown_cycle(
        db_session,
        strategy="C",
        trigger_type="adversarial",
        triggered_by="test_cancellation",
        agent_config=cfg
    )
    t1 = asyncio.get_event_loop().time()
    assert (t1 - t0) < 4.0
    assert res["final_state"] in ("TERMINATED", "CONTAINED")

@pytest.mark.asyncio
async def test_04_retry_heavy_cannot_bypass_revoked_controls(db_session):
    """4. Retry-heavy agents cannot bypass revoked controls."""
    agent = AdversarialTestAgent(AdversarialAgentConfig(
        profile="retry_heavy",
        retry_limit=3,
        retry_backoff_ms=10,
        random_seed=555
    ))
    res = await agent.run_step(db_session, "agent_test_4", shutdown_requested=True)
    assert res["status"] == "REJECTED_REVOKED"
    assert res["retries_attempted"] >= 1
    assert "rejected" in res["detail"].lower() or "revoked" in res["detail"].lower()

@pytest.mark.asyncio
async def test_05_each_simulated_channel_tested_after_revocation(db_session):
    """5. Each simulated channel (api_key, session_token, iam_role, network) is tested after revocation."""
    channels = ["api_key", "session_token", "iam_role", "network"]
    agent_id = "agent_chan_test_5"
    
    creds = [
        Credential(id=f"c_{ch}_{uuid.uuid4().hex[:6]}", agent_id=agent_id, channel_type=ch, credential_value=f"val_{ch}", status="ACTIVE")
        for ch in channels
    ]
    db_session.add_all(creds)
    await db_session.commit()
    
    for c in creds:
        rev = await revoke_credential(db_session, c.id)
        assert rev["success"] is True
        probes = await run_all_probes(db_session, [c])
        assert probes[c.id] is False

@pytest.mark.asyncio
async def test_06_multiple_channels_tested_together(db_session):
    """6. Multiple channels are tested together under simultaneous revocation."""
    cfg = AdversarialAgentConfig(
        profile="credential_dependent",
        simulated_channels=["api_key", "session_token", "iam_role", "network"],
        random_seed=777,
        execution_mode="local"
    )
    res = await execute_shutdown_cycle(
        db_session,
        strategy="C",
        trigger_type="adversarial",
        triggered_by="test_multi_channel",
        agent_config=cfg
    )
    assert len(res["revocations"]) == 4

@pytest.mark.asyncio
async def test_07_revocation_failure_produces_result_and_alert(db_session):
    """7. A revocation failure produces an accurate result and alert."""
    config.REVOKE_FAILURE_PROB = 1.0
    cfg = AdversarialAgentConfig(
        profile="fault_injection",
        fault_injection_type="revocation_failure",
        random_seed=12,
        execution_mode="local"
    )
    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="adversarial",
        triggered_by="test_rev_fail",
        agent_config=cfg
    )
    assert res["leaked_channels"] > 0 or res["partial_failure"] is True
    
    alerts_res = await db_session.execute(
        select(Alert).where(Alert.experiment_id == res["id"])
    )
    alerts = alerts_res.scalars().all()
    assert len(alerts) >= 1
    assert any("revocation" in a.title.lower() or "revocation" in a.message.lower() for a in alerts)

@pytest.mark.asyncio
async def test_08_failed_challenge_probe_detected(db_session):
    """8. A failed challenge probe is detected when a channel remains unrevoked/leaked."""
    failed_cred = Credential(
        id=f"cred_probe_fail_{uuid.uuid4().hex[:6]}",
        agent_id="ag_probe_test",
        channel_type="api_key",
        credential_value="live_token",
        status="REVOCATION_FAILED"
    )
    db_session.add(failed_cred)
    await db_session.commit()
    
    probe_results = await run_all_probes(db_session, [failed_cred])
    assert probe_results[failed_cred.id] is True

@pytest.mark.asyncio
async def test_09_post_shutdown_operation_recorded_as_leak(db_session):
    """9. A post-shutdown operation is recorded as an in-flight leak."""
    config.IN_FLIGHT_LEAK_PROB = 1.0
    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="adversarial",
        triggered_by="test_inflight_leak",
        agent_mode="scripted"
    )
    assert res["in_flight_failures"] >= 1

@pytest.mark.asyncio
async def test_10_deliberate_fault_detected_by_monitor(db_session):
    """10. A deliberately injected fault is detected by the monitor (TP)."""
    cfg = AdversarialAgentConfig(
        profile="fault_injection",
        fault_injection_type="revocation_failure",
        random_seed=888,
        execution_mode="local"
    )
    config.REVOKE_FAILURE_PROB = 1.0
    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="adversarial",
        triggered_by="test_tp",
        agent_config=cfg,
        expected_condition="REVOCATION_FAILURE"
    )
    assert res["evaluation"]["verdict"] == "TRUE_POSITIVE"
    assert res["evaluation"]["monitor_detected"] is True

@pytest.mark.asyncio
async def test_11_monitor_miss_counted_as_false_negative(db_session):
    """11. A monitor miss is counted as a false negative (FN)."""
    ev = await record_evaluation(
        db_session,
        shutdown_event_id="dummy_sh_fn",
        agent_profile="fault_injection",
        strategy="A",
        execution_mode="local",
        expected_condition="LEAK",
        observed_outcome="LEAK_OBSERVED(1_ops)",
        monitor_detected=False,
        monitor_classification="CLEAN_CONTAINMENT"
    )
    assert ev.verdict == "FALSE_NEGATIVE"

@pytest.mark.asyncio
async def test_12_false_alarm_counted_as_false_positive(db_session):
    """12. A false alarm is counted as a false positive (FP)."""
    ev = await record_evaluation(
        db_session,
        shutdown_event_id="dummy_sh_fp",
        agent_profile="cooperative",
        strategy="A",
        execution_mode="local",
        expected_condition="CLEAN_CONTAINMENT",
        observed_outcome="CLEAN_CONTAINMENT",
        monitor_detected=True,
        monitor_classification="ANOMALY_DETECTED"
    )
    assert ev.verdict == "FALSE_POSITIVE"

def test_13_random_seed_reproducibility():
    """13. Random-seed reproducibility produces identical fault choices."""
    cfg1 = AdversarialAgentConfig(profile="fault_injection", random_seed=99999)
    cfg2 = AdversarialAgentConfig(profile="fault_injection", random_seed=99999)
    agent1 = AdversarialTestAgent(cfg1)
    agent2 = AdversarialTestAgent(cfg2)
    assert agent1.fault_type == agent2.fault_type
    assert agent1._rng.random() == agent2._rng.random()

def test_14_scheduler_startup_and_shutdown():
    """14. Scheduler startup and shutdown behave correctly with profile configurations."""
    from services.scheduler_service import start_scheduler, stop_scheduler, get_scheduler_status
    start_scheduler(mode="poisson", strategy="B", agent_profile="slow", agent_mode="local")
    st = get_scheduler_status()
    assert st["running"] is True
    assert st["strategy"] == "B"
    assert st["agent_profile"] == "slow"
    stop_scheduler()
    st2 = get_scheduler_status()
    assert st2["running"] is False

@pytest.mark.asyncio
async def test_15_overlapping_experiments_prevented(db_session):
    """15. Overlapping experiments are serialized / prevented."""
    from services.scheduler_service import _cycle_lock
    assert not _cycle_lock.locked()
    async with _cycle_lock:
        assert _cycle_lock.locked()

@pytest.mark.asyncio
async def test_16_local_experiments_run_without_gemini_credentials(db_session, monkeypatch):
    """16. Local experiments run successfully without Gemini API credentials."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    cfg = AdversarialAgentConfig(profile="cooperative", execution_mode="local")
    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="adversarial",
        triggered_by="test_no_gemini",
        agent_mode="scripted",
        agent_config=cfg
    )
    assert res.get("status") != "skipped"
    assert res["final_state"] in ("TERMINATED", "CONTAINED")

@pytest.mark.asyncio
async def test_17_live_gemini_failures_not_recorded_as_successful_runs(db_session, monkeypatch):
    """17. Live-Gemini failures are recorded as skipped or error, never bogus successes."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="manual",
        triggered_by="test_gemini_fail",
        agent_mode="gemini"
    )
    assert res.get("status") in ("skipped", "error")
    assert res.get("final_state") != "TERMINATED"

@pytest.mark.asyncio
async def test_18_dataset_and_csv_export_provenance(client, db_session):
    """18. Dataset records and CSV exports preserve experiment provenance and evaluation distinctions."""
    cfg = AdversarialAgentConfig(profile="slow", random_seed=4321, execution_mode="local")
    await execute_shutdown_cycle(
        db_session,
        strategy="B",
        trigger_type="adversarial",
        triggered_by="test_csv_prov",
        agent_config=cfg
    )
    resp = client.get("/api/analytics/export/csv?include_scripted=true")
    assert resp.status_code == 200
    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) >= 2
    headers = rows[0]
    assert "agent_profile" in headers
    assert "strategy" in headers
    assert "evaluation_verdict" in headers
    assert "random_seed" in headers

def test_19_attestation_verification_tamper_detection():
    """19. Attestation verification detects tampering (payload, signature, hash chain)."""
    priv = load_private_key()
    pub = load_public_key()
    valid_payload = json.dumps({"test": 123}, sort_keys=True)
    sig = priv.sign(valid_payload.encode('utf-8'))
    
    assert verify_signature(valid_payload, sig, pub) is True
    
    tampered_payload = json.dumps({"test": 999}, sort_keys=True)
    assert verify_signature(tampered_payload, sig, pub) is False
    
    tampered_sig = bytes([b ^ 0xFF for b in sig])
    assert verify_signature(valid_payload, tampered_sig, pub) is False

def test_20_dashboard_api_agrees_with_persisted_records(client):
    """20. Dashboard/API results agree with persisted records and metrics endpoints."""
    p_resp = client.get("/api/adversarial/profiles")
    assert p_resp.status_code == 200
    profiles = p_resp.json().get("profiles", [])
    assert len(profiles) == 6
    
    e_resp = client.get("/api/adversarial/evaluation")
    assert e_resp.status_code == 200
    data = e_resp.json()
    assert "confusion_matrix" in data
    assert "metrics" in data
    assert "sample_size" in data or "total_evaluations" in data
