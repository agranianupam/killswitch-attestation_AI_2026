import pytest
from sqlalchemy import select
from models.shutdown_event import ShutdownEvent
import config

def test_empty_analytics_summary(client):
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_shutdowns"] == 0
    assert data["success_rate"] == 0.0
    assert data["outcome_matrix_2x2"]["pass_no_leak"] == 0

def test_settings_endpoint(client, auth_headers):
    res = client.post("/api/shutdown/settings", json={
        "net_delay_min": 10,
        "net_delay_max": 20,
        "in_flight_leak_prob": 0.45
    }, headers=auth_headers)
    assert res.status_code == 200
    assert config.NET_DELAY_MIN == 10
    assert config.NET_DELAY_MAX == 20
    assert config.IN_FLIGHT_LEAK_PROB == 0.45

    res_get = client.get("/api/shutdown/settings")
    assert res_get.status_code == 200
    assert res_get.json()["in_flight_leak_prob"] == 0.45

def test_scheduler_toggle_endpoint(client, auth_headers):
    res_start = client.post("/api/scheduler/toggle", json={
        "enabled": True,
        "mode": "poisson",
        "strategy": "A"
    }, headers=auth_headers)
    assert res_start.status_code == 200
    assert res_start.json()["running"] is True

    status_res = client.get("/api/scheduler/status")
    assert status_res.status_code == 200
    assert status_res.json()["running"] is True

    res_stop = client.post("/api/scheduler/toggle", json={
        "enabled": False
    }, headers=auth_headers)
    assert res_stop.status_code == 200
    assert res_stop.json()["running"] is False

def test_shutdown_cycle_and_batch(client, auth_headers):
    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Scripted"
    try:
        res = client.post("/api/shutdown/batch?count=2&strategy=A", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 2
        assert data["completed"] == 2
        assert len(data["results"]) == 2

        hist_res = client.get("/api/shutdown/history?include_scripted=true")
        assert hist_res.status_code == 200
        events = hist_res.json()
        assert len(events) >= 2
        assert "triggered_by" in events[0]
        assert "trigger_timestamp" in events[0]

        sum_res = client.get("/api/analytics/summary?include_scripted=true")
        assert sum_res.status_code == 200
        summary = sum_res.json()
        assert summary["total_shutdowns"] >= 2
        assert len(summary["runs_trend"]) >= 2
        assert "outcome_matrix_2x2" in summary
        assert "channel_latencies" in summary
        assert "runs_with_leaks" in summary
        assert "exposed_runs" in summary
        assert "runs_needing_retries" in summary
        assert "mean_total_revocation_time" in summary
        assert "leaked_operations" in summary

        verify_res = client.get("/api/shutdown/verify")
        assert verify_res.status_code == 200
        assert verify_res.json()["status"] == "valid"

        kb_res = client.get("/api/analytics/killbench-comparison?include_scripted=true")
        assert kb_res.status_code == 200
        assert kb_res.json()["status"] == "evaluated"
        assert "capability_table" in kb_res.json()
        assert len(kb_res.json()["capability_table"]) == 6

        first_id = events[0]["id"]
        rep_res = client.get(f"/api/shutdown/{first_id}/report")
        assert rep_res.status_code == 200
        rep_data = rep_res.json()
        assert "total_revocation_ms" in rep_data
        assert "retries_total" in rep_data
        assert "agent_actions" in rep_data

        act_res = client.get(f"/api/shutdown/{first_id}/agent-actions")
        assert act_res.status_code == 200
        assert isinstance(act_res.json(), list)
    finally:
        config.AGENT_MODE = old_mode
