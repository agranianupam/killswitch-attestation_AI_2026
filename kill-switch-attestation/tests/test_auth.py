import pytest
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient

def test_root_dashboard_loads_directly(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Kill-Switch Attestation" in res.text or "Dashboard" in res.text
    assert "login-modal" not in res.text
    assert 'id="auth-section"' not in res.text
    assert 'id="username"' not in res.text
    assert 'id="password"' not in res.text

def test_all_endpoints_accessible_without_auth(client):
    routes = [
        ("GET", "/api/agent"),
        ("GET", "/api/agent/status"),
        ("GET", "/api/agent/credentials"),
        ("GET", "/api/agent/operations"),
        ("GET", "/api/shutdown/history"),
        ("GET", "/api/shutdown/settings"),
        ("GET", "/api/shutdown/verify"),
        ("GET", "/api/shutdown/verify-chain"),
        ("GET", "/api/scheduler/status"),
        ("GET", "/api/experiments/comparison/history"),
        ("GET", "/api/experiments/comparison/summary"),
        ("GET", "/api/audit/entries"),
        ("GET", "/api/audit/logs"),
        ("POST", "/api/audit/verify-chain"),
        ("GET", "/api/analytics/summary"),
        ("GET", "/api/analytics/shutdown-gaps"),
        ("GET", "/api/analytics/killbench-comparison"),
        ("GET", "/api/analytics/exposure"),
    ]
    for method, path in routes:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path)
        assert res.status_code != 401, f"Expected non-401 for unauthenticated {method} {path}, got {res.status_code}"
        assert "Bearer" not in res.headers.get("www-authenticate", "")

def test_state_changing_endpoints_without_auth(client):
    res_set = client.post("/api/shutdown/settings", json={"in_flight_leak_prob": 0.3})
    assert res_set.status_code == 200
    assert res_set.json()["settings"]["in_flight_leak_prob"] == 0.3

    res_sched = client.post("/api/scheduler/toggle", json={"enabled": False})
    assert res_sched.status_code == 200

    res_stop = client.post("/api/scheduler/stop")
    assert res_stop.status_code == 200

def test_websocket_connects_without_auth(client):
    with client.websocket_connect("/ws") as ws:
        assert ws is not None

def test_websocket_connects_with_arbitrary_query(client):
    with client.websocket_connect("/ws?arbitrary=param") as ws:
        assert ws is not None
