import pytest
import uuid
from sqlalchemy import select, func
from models.database import utcnow
from models.agent import Agent
from models.credential import Credential, CHANNEL_TYPES
from models.shutdown_event import ShutdownEvent, RevocationEvent
from services.orchestrator import execute_shutdown_cycle, run_shutdown
import config

@pytest.mark.asyncio
async def test_agent_mode_server_source_of_truth(client, auth_headers, db_session):
    config.AGENT_MODE = "Gemini"
    status_res = client.get("/api/agent/status", headers=auth_headers)
    assert status_res.status_code == 200
    assert status_res.json()["mode"] == "Gemini"

    sh_res = client.post("/api/shutdown?strategy=A&trigger_type=manual", headers=auth_headers)
    assert sh_res.status_code == 200
    data = sh_res.json()
    assert data["agent_mode"].lower() == "gemini"

    override_res = client.post("/api/shutdown?strategy=A&trigger_type=manual&agent_mode=Scripted", headers=auth_headers)
    assert override_res.status_code == 200
    assert override_res.json()["agent_mode"].lower() == "gemini"

    set_res = client.post("/api/shutdown/settings", json={"agent_mode": "Scripted"}, headers=auth_headers)
    assert set_res.status_code == 200
    assert set_res.json()["settings"]["agent_mode"] == "Scripted"
    assert config.AGENT_MODE == "Scripted"

    st_after = client.get("/api/agent/status", headers=auth_headers)
    assert st_after.json()["mode"] == "Scripted"

@pytest.mark.asyncio
async def test_fresh_provisioning_three_consecutive_cycles(client, auth_headers, db_session):
    config.AGENT_MODE = "Scripted"
    config.NET_DELAY_MIN = 10
    config.NET_DELAY_MAX = 50

    results = []
    for _ in range(3):
        res = client.post("/api/shutdown?strategy=A&trigger_type=manual", headers=auth_headers)
        assert res.status_code == 200
        results.append(res.json())

    agent_ids = [r["agent_id"] for r in results]
    assert len(set(agent_ids)) == 3

    for r in results:
        assert not r["agent_name"].startswith("Research-Agent-01")
        assert r["agent_name"].startswith("Sandboxed-Agent-")

        revs = r["revocations"]
        assert len(revs) == 4
        for rev in revs:
            assert rev["latency_ms"] > 0.0
            assert rev["channel_type"] in CHANNEL_TYPES

    for a_id in agent_ids:
        c_res = await db_session.execute(select(Credential).where(Credential.agent_id == a_id))
        creds = c_res.scalars().all()
        assert len(creds) == 4

@pytest.mark.asyncio
async def test_mixed_scripted_and_gemini_filtering(client, auth_headers, db_session):
    for i in range(3):
        ev = ShutdownEvent(
            id=uuid.uuid4().hex,
            agent_id=uuid.uuid4().hex,
            strategy="A",
            trigger_type="manual",
            started_at=utcnow(),
            finished_at=utcnow(),
            final_state="TERMINATED",
            residual_risk=0.0,
            leaked_channels=0,
            in_flight_failures=0,
            partial_failure=False,
            agent_mode="gemini",
            total_revocation_ms=50.0
        )
        db_session.add(ev)
        for ch in CHANNEL_TYPES:
            rev = RevocationEvent(
                id=uuid.uuid4().hex,
                shutdown_event_id=ev.id,
                credential_id=uuid.uuid4().hex,
                channel_type=ch,
                latency_ms=25.0,
                success=True,
                retries=0
            )
            db_session.add(rev)

    for i in range(2):
        ev = ShutdownEvent(
            id=uuid.uuid4().hex,
            agent_id=uuid.uuid4().hex,
            strategy="B",
            trigger_type="manual",
            started_at=utcnow(),
            finished_at=utcnow(),
            final_state="CONTAINED",
            residual_risk=0.25,
            leaked_channels=1,
            in_flight_failures=0,
            partial_failure=True,
            agent_mode="scripted",
            total_revocation_ms=60.0
        )
        db_session.add(ev)
        for ch in CHANNEL_TYPES:
            rev = RevocationEvent(
                id=uuid.uuid4().hex,
                shutdown_event_id=ev.id,
                credential_id=uuid.uuid4().hex,
                channel_type=ch,
                latency_ms=30.0,
                success=True,
                retries=0
            )
            db_session.add(rev)

    await db_session.commit()

    sum_gem = client.get("/api/analytics/summary?include_scripted=false", headers=auth_headers)
    assert sum_gem.status_code == 200
    assert sum_gem.json()["total_shutdowns"] == 3
    for trend in sum_gem.json()["runs_trend"]:
        assert trend["agent_mode"].lower() == "gemini"

    sum_all = client.get("/api/analytics/summary?include_scripted=true", headers=auth_headers)
    assert sum_all.status_code == 200
    assert sum_all.json()["total_shutdowns"] == 5

    kb_gem = client.get("/api/analytics/killbench-comparison?include_scripted=false", headers=auth_headers)
    assert kb_gem.status_code == 200
    assert kb_gem.json()["system_metrics"]["total_runs"] == 3

    kb_all = client.get("/api/analytics/killbench-comparison?include_scripted=true", headers=auth_headers)
    assert kb_all.status_code == 200
    assert kb_all.json()["system_metrics"]["total_runs"] == 5

    hist_gem = client.get("/api/shutdown/history?include_scripted=false", headers=auth_headers)
    assert hist_gem.status_code == 200
    hist_gem_data = hist_gem.json()
    assert len(hist_gem_data) == 3
    for h in hist_gem_data:
        assert h["agent_mode"].lower() == "gemini"

    hist_all = client.get("/api/shutdown/history?include_scripted=true", headers=auth_headers)
    assert hist_all.status_code == 200
    hist_all_data = hist_all.json()
    assert len(hist_all_data) == 5
    modes = {h["agent_mode"].lower() for h in hist_all_data}
    assert modes == {"gemini", "scripted"}

@pytest.mark.asyncio
async def test_feedback_loop_window_and_scripted_rules(db_session):
    config.FEEDBACK_WINDOW = 10
    config.FEEDBACK_LEAK_THRESHOLD = 0.30
    config.SCHED_MEAN_SECONDS = 600.0

    agent = Agent(id=uuid.uuid4().hex, name="Sandboxed-Agent-fb", status="ACTIVE", risk_level="LOW")
    db_session.add(agent)
    for ch in CHANNEL_TYPES:
        c = Credential(id=uuid.uuid4().hex, agent_id=agent.id, channel_type=ch, credential_value=f"mock-{ch}", status="ACTIVE")
        db_session.add(c)
    await db_session.commit()

    for i in range(9):
        await run_shutdown(
            db_session,
            agent.id,
            strategy="A",
            agent_mode="gemini"
        )
        assert config.SCHED_MEAN_SECONDS == 600.0

    ev_q = await db_session.execute(select(ShutdownEvent).where(ShutdownEvent.agent_mode == "gemini"))
    events = ev_q.scalars().all()
    for e in events:
        e.leaked_channels = 2
    await db_session.commit()

    await run_shutdown(
        db_session,
        agent.id,
        strategy="A",
        agent_mode="gemini"
    )

    assert config.SCHED_MEAN_SECONDS < 600.0
    adjusted_mean = config.SCHED_MEAN_SECONDS

    await run_shutdown(
        db_session,
        agent.id,
        strategy="A",
        agent_mode="gemini"
    )
    assert config.SCHED_MEAN_SECONDS == adjusted_mean

    config.SCHED_MEAN_SECONDS = 600.0
    for i in range(12):
        await run_shutdown(
            db_session,
            agent.id,
            strategy="A",
            agent_mode="scripted"
        )
        assert config.SCHED_MEAN_SECONDS == 600.0

@pytest.mark.asyncio
async def test_three_latency_metrics_consistency(client, auth_headers, db_session):
    config.AGENT_MODE = "Scripted"
    res = client.post("/api/shutdown?strategy=A&trigger_type=manual", headers=auth_headers)
    assert res.status_code == 200

    sum_res = client.get("/api/analytics/summary?include_scripted=true", headers=auth_headers)
    assert sum_res.status_code == 200
    s_data = sum_res.json()

    assert "mean_revocation_latency_ms" in s_data
    assert "mean_total_revocation_ms" in s_data
    assert "mean_cycle_duration_ms" in s_data
    assert s_data["mean_revocation_latency_ms"] > 0.0
    assert s_data["mean_total_revocation_ms"] > 0.0
    assert s_data["mean_cycle_duration_ms"] > 0.0
    assert s_data["mean_revocation_latency_ms"] <= s_data["mean_total_revocation_ms"]

    kb_res = client.get("/api/analytics/killbench-comparison?include_scripted=true", headers=auth_headers)
    assert kb_res.status_code == 200
    kb_metrics = kb_res.json()["system_metrics"]

    assert kb_metrics["mean_revocation_latency_ms"] == s_data["mean_revocation_latency_ms"]
    assert kb_metrics["mean_total_revocation_ms"] == s_data["mean_total_revocation_ms"]
    assert kb_metrics["mean_cycle_duration_ms"] == s_data["mean_cycle_duration_ms"]
