import pytest
from httpx import AsyncClient, ASGITransport
from main import app
import config

AUTH_HEADER = {"Authorization": f"Bearer {getattr(config, 'EXTERNAL_AGENT_AUTH_TOKEN', 'ks_shared_secret_token_2026')}"}

@pytest.mark.asyncio
async def test_external_agent_registration_and_heartbeat():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        reg_payload = {
            "agent_id": "ext-test-agent-01",
            "agent_name": "Autonomous External Worker",
            "agent_url": "http://127.0.0.1:8010",
            "mode": "Scripted",
            "channels": ["api_key", "session_token", "iam_role", "network"]
        }
        res = await ac.post("/api/external-agent/register", json=reg_payload, headers=AUTH_HEADER)
        assert res.status_code == 200
        assert res.json()["status"] == "registered"

        hb_payload = {
            "agent_id": "ext-test-agent-01",
            "status": "RUNNING",
            "containment_status": "NORMAL",
            "active_operations_count": 2,
            "completed_tasks_count": 10,
            "timestamp": "2026-10-22T05:00:00Z"
        }
        hb_res = await ac.post("/api/external-agent/heartbeat", json=hb_payload, headers=AUTH_HEADER)
        assert hb_res.status_code == 200
        assert hb_res.json()["status"] == "heartbeat_acknowledged"

        st_res = await ac.get("/api/external-agent/status")
        assert st_res.status_code == 200
        data = st_res.json()
        assert data["agent_id"] == "ext-test-agent-01"
        assert data["is_connected"] is True
        assert data["status"] == "RUNNING"
