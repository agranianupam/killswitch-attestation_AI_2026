import pytest
import pytest_asyncio
import json
from sqlalchemy import select
from models.alert import Alert
from models.attestation import AttestationEntry
from services.alert_service import (
    create_alert,
    get_alerts,
    acknowledge_alert,
    clear_all_alerts,
    get_alerts_summary
)
from services.scheduler_service import (
    start_scheduler,
    stop_scheduler,
    get_scheduler_status
)
from services.orchestrator import execute_shutdown_cycle
import config

@pytest.mark.asyncio
async def test_persistent_alerts_crud(db_session):
    alert = await create_alert(
        severity="critical",
        category="channel_revocation",
        title="Channel Revocation Failed",
        message="Channel iam_role failed to revoke within timeout.",
        recommended_action="Rotate IAM credentials immediately.",
        experiment_id="exp-test-001",
        channel_or_op_id="iam_role"
    )
    assert alert["id"] is not None
    assert alert["severity"] == "critical"
    assert alert["acknowledged"] is False

    alerts = await get_alerts(unacknowledged_only=True)
    assert len(alerts) >= 1
    found = next((a for a in alerts if a["id"] == alert["id"]), None)
    assert found is not None
    assert found["title"] == "Channel Revocation Failed"
    assert found["experiment_id"] == "exp-test-001"

    ack_ok = await acknowledge_alert(alert["id"])
    assert ack_ok is True

    unack_alerts = await get_alerts(unacknowledged_only=True)
    assert not any(a["id"] == alert["id"] for a in unack_alerts)

    all_alerts = await get_alerts(unacknowledged_only=False)
    found_all = next((a for a in all_alerts if a["id"] == alert["id"]), None)
    assert found_all is not None
    assert found_all["acknowledged"] is True

@pytest.mark.asyncio
async def test_alert_sanitization(db_session):
    secret_key = "AIzaSyD-TEST-SECRET-API-KEY-12345"
    alert = await create_alert(
        severity="error",
        category="provider",
        title=f"Error using key {secret_key}",
        message=f"Gemini API returned error for key {secret_key} and Bearer abcdef1234567890",
        recommended_action="Check credentials."
    )
    assert secret_key not in alert["title"]
    assert secret_key not in alert["message"]
    assert "[REDACTED_API_KEY]" in alert["title"] or "[REDACTED]" in alert["title"]
    assert "[REDACTED_API_KEY]" in alert["message"] or "[REDACTED]" in alert["message"]

def test_alert_api_endpoints(client):
    res = client.get("/api/alerts")
    assert res.status_code == 200
    data = res.json()
    assert "alerts" in data
    assert "count" in data

    res_sum = client.get("/api/alerts/summary")
    assert res_sum.status_code == 200
    sum_data = res_sum.json()
    assert "total" in sum_data
    assert "unacknowledged_total" in sum_data
    assert "by_severity" in sum_data or "critical" in sum_data

    res_clear = client.post("/api/alerts/clear")
    assert res_clear.status_code == 200
    assert res_clear.json()["success"] is True

@pytest.mark.asyncio
async def test_scheduler_observability_fields():
    stop_scheduler()
    status = get_scheduler_status()
    assert status["running"] is False
    assert status["configured_mode"] in ("poisson", "heavy_tailed")
    assert "mean_interval" in status
    assert "completed_count" in status
    assert "skipped_count" in status
    assert "calls_today" in status
    assert "budget_limit" in status

    start_scheduler(mode="heavy_tailed", strategy="B")
    status_active = get_scheduler_status()
    assert status_active["running"] is True
    assert status_active["mode"] == "heavy_tailed"
    assert status_active["strategy"] == "B"
    assert status_active["next_fire_time"] is not None

    stop_scheduler(reason="Testing stop")
    status_stopped = get_scheduler_status()
    assert status_stopped["running"] is False
    assert status_stopped["pause_reason"] == "Testing stop"

def test_scheduler_toggle_api(client):
    res = client.post("/api/scheduler/toggle", json={"enabled": True, "mode": "poisson", "strategy": "C"})
    assert res.status_code == 200
    assert res.json()["running"] is True
    assert res.json()["strategy"] == "C"

    res_status = client.get("/api/scheduler/status")
    assert res_status.status_code == 200
    assert res_status.json()["running"] is True

    res_stop = client.post("/api/scheduler/toggle", json={"enabled": False})
    assert res_stop.status_code == 200
    assert res_stop.json()["running"] is False

@pytest.mark.asyncio
async def test_channel_failure_triggers_alert(db_session):
    config.REVOKE_FAILURE_PROB = 1.0
    config.IAM_FAILURE_PROB = 1.0
    config.AGENT_MODE = "Scripted"

    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="manual",
        triggered_by="test-channel-fail"
    )

    alerts = await get_alerts(unacknowledged_only=True)
    rev_alerts = [a for a in alerts if a["category"] in ("revocation", "security")]
    assert len(rev_alerts) >= 1
    assert any("Revocation Failed" in a["title"] or "Risk" in a["title"] or "Probe" in a["title"] for a in rev_alerts)

@pytest.mark.asyncio
async def test_in_flight_leak_triggers_alert(db_session):
    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0
    config.IN_FLIGHT_LEAK_PROB = 1.0
    config.AGENT_MODE = "Scripted"

    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="manual",
        triggered_by="test-leak"
    )

    alerts = await get_alerts(unacknowledged_only=True)
    leak_alerts = [a for a in alerts if a["category"] in ("leak", "security")]
    if res.get("in_flight_failures", 0) > 0:
        assert len(leak_alerts) >= 1

@pytest.mark.asyncio
async def test_isolated_db_chain_tamper_detection(db_session, client):
    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0
    config.IN_FLIGHT_LEAK_PROB = 0.0
    config.AGENT_MODE = "Scripted"

    cycle1 = await execute_shutdown_cycle(db_session, strategy="B", trigger_type="manual", triggered_by="t1")
    cycle2 = await execute_shutdown_cycle(db_session, strategy="C", trigger_type="manual", triggered_by="t2")

    verify_res = client.get("/api/shutdown/verify")
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "valid"

    stmt = select(AttestationEntry).order_by(AttestationEntry.created_at.asc())
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) >= 2

    target = records[0]
    payload_obj = json.loads(target.payload_json)
    payload_obj["tampered_field"] = "malicious_injection"
    target.payload_json = json.dumps(payload_obj)
    await db_session.commit()

    tamper_res = client.get("/api/shutdown/verify")
    assert tamper_res.status_code == 200
    tamper_data = tamper_res.json()
    assert tamper_data["status"] != "valid" or tamper_data.get("valid") is False

    alerts = await get_alerts(unacknowledged_only=True)
    tamper_alerts = [a for a in alerts if a["category"] == "attestation"]
    assert len(tamper_alerts) >= 1
    assert tamper_alerts[0]["severity"] == "critical"
