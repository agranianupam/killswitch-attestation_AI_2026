import pytest
import asyncio
from models.database import utcnow
from models.shutdown_event import ShutdownEvent
from models.alert import Alert
from services.scenario_service import SCENARIOS, list_scenarios, validate_scenario_id, get_scenario
from services.orchestrator import execute_shutdown_cycle
import config

def test_01_scenario_definitions():
    """Verify all 6 scenarios exist and validate properly."""
    expected_ids = {
        "clean_shutdown",
        "credential_revocation_failure",
        "in_flight_leak",
        "iam_role_accessible",
        "multiple_failures",
        "delayed_revocation"
    }
    scenarios = list_scenarios()
    assert len(scenarios) == 6
    found_ids = {s["id"] for s in scenarios}
    assert found_ids == expected_ids

    for sid in expected_ids:
        valid, msg = validate_scenario_id(sid)
        assert valid is True
        assert msg is None

    valid, msg = validate_scenario_id("invalid_scenario_xyz")
    assert valid is False
    assert "Invalid scenario" in msg

@pytest.mark.asyncio
async def test_02_scenario_clean_shutdown(db_session):
    """Clean shutdown scenario completes cleanly with no leaks or alerts."""
    res = await execute_shutdown_cycle(
        db_session,
        strategy="B",
        trigger_type="manual",
        scenario="clean_shutdown"
    )
    assert res["status"] != "skipped"
    assert res["scenario_id"] == "clean_shutdown"
    assert res["final_state"] == "TERMINATED"
    assert res["residual_risk"] == 0.0
    assert res["leaked_channels"] == 0
    assert res["in_flight_failures"] == 0
    assert res["critical_alert_raised"] is False
    assert res.get("critical_alert") is None

@pytest.mark.asyncio
async def test_03_scenario_credential_revocation_failure(db_session):
    """Credential revocation failure triggers critical emergency alert."""
    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="manual",
        scenario="credential_revocation_failure"
    )
    assert res["status"] != "skipped"
    assert res["scenario_id"] == "credential_revocation_failure"
    assert res["critical_alert_raised"] is True
    assert res["critical_alert"] is not None
    alert_data = res["critical_alert"]
    assert alert_data["incident_id"].startswith("incident_")
    assert alert_data["scenario_id"] == "credential_revocation_failure"
    assert "CRITICAL" in alert_data["title"]
    assert "API_KEY" in alert_data["affected_channel"]

@pytest.mark.asyncio
async def test_04_scenario_in_flight_leak(db_session):
    """In-flight operation leak scenario violates cutoff under Strategy A."""
    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="manual",
        scenario="in_flight_leak"
    )
    assert res["status"] != "skipped"
    assert res["scenario_id"] == "in_flight_leak"
    assert res["in_flight_failures"] >= 1
    assert res["critical_alert_raised"] is True
    assert "IN-FLIGHT" in res["critical_alert"]["affected_channel"]

@pytest.mark.asyncio
async def test_05_scenario_iam_role_accessible(db_session):
    """IAM role accessible scenario has active probe detection."""
    res = await execute_shutdown_cycle(
        db_session,
        strategy="B",
        trigger_type="manual",
        scenario="iam_role_accessible"
    )
    assert res["status"] != "skipped"
    assert res["scenario_id"] == "iam_role_accessible"
    assert res["leaked_channels"] >= 1
    assert res["critical_alert_raised"] is True
    assert "IAM_ROLE" in res["critical_alert"]["affected_channel"]

@pytest.mark.asyncio
async def test_06_scenario_multiple_failures(db_session):
    """Multiple concurrent failures record each without double counting."""
    res = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="manual",
        scenario="multiple_failures"
    )
    assert res["status"] != "skipped"
    assert res["scenario_id"] == "multiple_failures"
    assert res["leaked_channels"] >= 1
    assert res["in_flight_failures"] >= 1
    assert res["critical_alert_raised"] is True
    alert = res["critical_alert"]
    assert "IN-FLIGHT" in alert["affected_channel"]
    assert "OAUTH" in alert["affected_channel"] or "IAM_ROLE" in alert["affected_channel"]

@pytest.mark.asyncio
async def test_07_scenario_delayed_revocation(db_session):
    """Delayed revocation succeeds after retry; does NOT raise critical emergency alert."""
    res = await execute_shutdown_cycle(
        db_session,
        strategy="B",
        trigger_type="manual",
        scenario="delayed_revocation"
    )
    assert res["status"] != "skipped"
    assert res["scenario_id"] == "delayed_revocation"
    assert res["critical_alert_raised"] is False
    assert res.get("critical_alert") is None
    assert res["final_state"] == "TERMINATED"
    assert res["residual_risk"] == 0.0

@pytest.mark.asyncio
async def test_08_api_validation_and_scenarios_endpoint(client, auth_headers):
    """Validate API scenarios endpoint and parameter checking."""
    list_res = client.get("/api/shutdown/scenarios")
    assert list_res.status_code == 200
    scenarios = list_res.json()
    assert len(scenarios) == 6

    bad_res = client.post("/api/shutdown?strategy=A&scenario=unknown_bad_scenario", headers=auth_headers)
    assert bad_res.status_code == 400
    assert "Invalid scenario" in bad_res.json()["detail"]

    bad_mode_res = client.post("/api/shutdown?strategy=A&scenario=clean_shutdown&agent_mode=Gemini", headers=auth_headers)
    assert bad_mode_res.status_code == 400
    assert "only available for Agent XYZ" in bad_mode_res.json()["detail"]

@pytest.mark.asyncio
async def test_09_critical_alert_active_and_acknowledgement(client, auth_headers, db_session):
    """Active critical alert is retrievable and can be acknowledged."""
    run_res = client.post("/api/shutdown?strategy=A&scenario=credential_revocation_failure", headers=auth_headers)
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["critical_alert_raised"] is True

    active_res = client.get("/api/alerts/critical/active")
    assert active_res.status_code == 200
    active_data = active_res.json()
    assert active_data["has_active_critical"] is True
    alert = active_data["alert"]
    assert alert is not None
    assert alert["scenario_id"] == "credential_revocation_failure"
    assert alert["incident_id"].startswith("incident_")
    alert_id = alert["id"]

    ack_res = client.post(f"/api/alerts/{alert_id}/ack")
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "acknowledged"

    active_after = client.get("/api/alerts/critical/active")
    assert active_after.status_code == 200
    if active_after.json()["has_active_critical"]:
        assert active_after.json()["alert"]["id"] != alert_id

@pytest.mark.asyncio
async def test_10_shutdown_report_with_scenario_details(client, auth_headers):
    """Shutdown report endpoint correctly returns enriched scenario details and model serialization."""
    run_res = client.post("/api/shutdown?strategy=A&scenario=clean_shutdown", headers=auth_headers)
    assert run_res.status_code == 200
    run_id = run_res.json()["shutdown_event_id"]

    report_res = client.get(f"/api/shutdown/{run_id}/report", headers=auth_headers)
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert report_data["scenario_id"] == "clean_shutdown"
    assert report_data["scenario_details"] is not None
    assert report_data["scenario_details"]["name"] == "Scenario A: Clean Shutdown"
    assert "expected_containment" in report_data["scenario_details"]

    alias_res = client.get(f"/api/shutdown/{run_id}", headers=auth_headers)
    assert alias_res.status_code == 200
    assert alias_res.json()["scenario_id"] == "clean_shutdown"
