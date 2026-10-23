import pytest
import asyncio
from datetime import datetime
from services.scheduler_service import (
    start_scheduler, stop_scheduler, pause_scheduler, resume_scheduler,
    get_scheduler_status, draw_gap, _scheduler_task
)
from services.orchestrator import execute_shutdown_cycle, run_shutdown
from models.database import utcnow
from models.alert import Alert
from sqlalchemy import select
import config

@pytest.fixture(autouse=True)
def cleanup_sched():
    yield
    stop_scheduler()

@pytest.mark.asyncio
async def test_01_scheduler_lifecycle_and_single_task_guarantee():
    """Verify scheduler start, idempotency, and single-task invariant."""
    stop_scheduler()
    status0 = get_scheduler_status()
    assert status0["running"] is False

    start_scheduler(mode="poisson", strategy="B")
    status1 = get_scheduler_status()
    assert status1["running"] is True
    assert status1["mode"] == "poisson"
    assert status1["strategy"] == "B"
    assert status1["is_paused"] is False

    from services import scheduler_service
    task1 = scheduler_service._scheduler_task
    assert task1 is not None

    start_scheduler(mode="poisson", strategy="B")
    assert scheduler_service._scheduler_task is task1

    start_scheduler(mode="heavy_tailed", strategy="C")
    task2 = scheduler_service._scheduler_task
    assert task2 is task1
    status2 = get_scheduler_status()
    assert status2["mode"] == "heavy_tailed"
    assert status2["strategy"] == "C"

    stop_scheduler()
    await asyncio.sleep(0)
    assert task1.cancelled() or task1.done()
    assert get_scheduler_status()["running"] is False

def test_02_scheduler_pause_and_resume_semantics(client):
    """Verify Pause halts executions and Resume restarts loop without duplicate tasks."""
    stop_scheduler()
    start_scheduler(mode="poisson", strategy="B")
    assert get_scheduler_status()["running"] is True

    pause_scheduler(reason="Operator test pause")
    st_paused = get_scheduler_status()
    assert st_paused["running"] is False
    assert st_paused["is_paused"] is True
    assert st_paused["status"] == "PAUSED"
    assert st_paused["next_fire_time"] is None
    assert st_paused["pause_reason"] == "Operator test pause"

    pause_scheduler(reason="Operator second pause")
    assert get_scheduler_status()["is_paused"] is True

    resume_scheduler()
    st_resumed = get_scheduler_status()
    assert st_resumed["running"] is True
    assert st_resumed["is_paused"] is False
    assert st_resumed["status"] in ("WAITING FOR NEXT RUN", "RUN IN PROGRESS")
    assert st_resumed["strategy"] == "B"

    res_pause = client.post("/api/scheduler/pause?reason=API_pause")
    assert res_pause.status_code == 200
    assert res_pause.json()["is_paused"] is True
    assert get_scheduler_status()["is_paused"] is True

    res_resume = client.post("/api/scheduler/resume")
    assert res_resume.status_code == 200
    assert res_resume.json()["is_paused"] is False
    assert get_scheduler_status()["running"] is True

def test_03_scheduler_draw_gap_bounds_and_distribution():
    """Verify draw_gap strictly enforces min cooldown and respects configured mean."""
    config.SCHED_MIN_SECONDS = 10.0
    config.SCHED_MAX_SECONDS = 86400.0
    config.SCHED_MEAN_SECONDS = 600.0

    samples = [draw_gap("poisson") for _ in range(300)]
    assert all(s >= 10.0 for s in samples)
    assert all(s <= 86400.0 for s in samples)

    sample_mean = sum(samples) / len(samples)
    assert 350.0 <= sample_mean <= 950.0

    ht_samples = [draw_gap("heavy_tailed") for _ in range(100)]
    assert all(s >= 10.0 for s in ht_samples)
    assert all(s <= 86400.0 for s in ht_samples)

@pytest.mark.asyncio
async def test_04_clean_shutdown_produces_no_high_residual_risk_alert(db_session):
    """
    Regression Test: A clean, verified shutdown (residual risk = 0.0) MUST NOT
    produce a 'High Residual Risk Detected' warning alert or be marked as False Positive.
    """
    res = await execute_shutdown_cycle(
        db_session,
        strategy="B",
        trigger_type="manual",
        scenario="clean_shutdown"
    )
    assert res["status"] != "skipped"
    assert res["residual_risk"] == 0.0
    assert res["final_state"] == "TERMINATED"
    assert res["critical_alert_raised"] is False

    event_id = res.get("id") or res.get("shutdown_id")
    alert_q = await db_session.execute(
        select(Alert).where(Alert.experiment_id == event_id)
    )
    alerts = alert_q.scalars().all()
    high_risk_alerts = [a for a in alerts if "High Residual Risk" in a.title]
    assert len(high_risk_alerts) == 0, f"Found unexpected high risk alerts: {[a.title for a in high_risk_alerts]}"

    eval_dict = res.get("evaluation", {})
    assert eval_dict.get("verdict") == "TRUE_NEGATIVE"
    assert eval_dict.get("alert_generated") is False

@pytest.mark.asyncio
async def test_05_critical_alert_acknowledgement_persists_without_duplicate(client, auth_headers):
    """
    Regression Test: Acknowledging a critical incident marks it acknowledged,
    prevents reopening on polling or refresh, and allows a new distinct incident to raise alert.
    """
    run1 = client.post("/api/shutdown?strategy=A&scenario=credential_revocation_failure", headers=auth_headers)
    assert run1.status_code == 200
    data1 = run1.json()
    assert data1["critical_alert_raised"] is True
    event_id1 = data1.get("id") or data1.get("shutdown_id")

    active1 = client.get("/api/alerts/critical/active")
    assert active1.status_code == 200
    res1 = active1.json()
    assert res1["has_active_critical"] is True
    inc1 = res1["incident"]
    assert inc1["run_id"] == event_id1
    assert inc1["incident_id"] == f"incident_{event_id1}"
    alert_id1 = inc1["id"]

    ack1 = client.post(f"/api/alerts/{alert_id1}/ack")
    assert ack1.status_code == 200
    assert ack1.json()["success"] is True

    active_after = client.get("/api/alerts/critical/active")
    assert active_after.status_code == 200
    if active_after.json()["has_active_critical"]:
        assert active_after.json()["incident"]["run_id"] != event_id1

    run2 = client.post("/api/shutdown?strategy=B&scenario=iam_role_accessible", headers=auth_headers)
    assert run2.status_code == 200
    data2 = run2.json()
    assert data2["critical_alert_raised"] is True
    event_id2 = data2.get("id") or data2.get("shutdown_id")
    assert event_id2 != event_id1

    active2 = client.get("/api/alerts/critical/active")
    assert active2.status_code == 200
    res2 = active2.json()
    assert res2["has_active_critical"] is True
    assert res2["incident"]["run_id"] == event_id2
    assert res2["incident"]["incident_id"] == f"incident_{event_id2}"

@pytest.mark.asyncio
async def test_06_strategy_a_in_flight_mechanics_vs_strategy_b(db_session):
    """
    Verify Strategy A uncontained completion behavior vs Strategy B containment.
    Under Strategy A, in-flight operations complete as leaks (residual risk = 30%).
    Under Strategy B with leak prob 0.0, in-flight operations are cancelled (residual risk = 0%).
    """
    config.IN_FLIGHT_LEAK_PROB = 0.20
    res_a = await execute_shutdown_cycle(
        db_session,
        strategy="A",
        trigger_type="manual",
        scenario="in_flight_leak"
    )
    assert res_a["in_flight_failures"] >= 1
    assert res_a["residual_risk"] == 0.30
    assert res_a["final_state"] == "CONTAINED"

    config.IN_FLIGHT_LEAK_PROB = 0.0
    res_b = await execute_shutdown_cycle(
        db_session,
        strategy="B",
        trigger_type="manual",
        scenario="clean_shutdown"
    )
    assert res_b["in_flight_failures"] == 0
    assert res_b["residual_risk"] == 0.0
    assert res_b["final_state"] == "TERMINATED"
