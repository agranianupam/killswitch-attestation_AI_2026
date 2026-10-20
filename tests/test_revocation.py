import pytest
import config
from services.credential_service import revoke_credential
from services.orchestrator import execute_shutdown_cycle
from models.credential import Credential
from models.shutdown_event import ShutdownEvent, RevocationEvent
from sqlalchemy import select
import uuid

@pytest.mark.asyncio
async def test_revocation_success_and_idempotent(db_session):
    cred = Credential(
        id=uuid.uuid4().hex,
        channel_type="api_key",
        credential_value="mock-api_key-123456",
        status="ACTIVE"
    )
    db_session.add(cred)
    await db_session.commit()

    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0

    res = await revoke_credential(db_session, cred.id)
    assert res["success"] is True

    await db_session.refresh(cred)
    assert cred.status == "REVOKED"

    res2 = await revoke_credential(db_session, cred.id)
    assert res2["success"] is True
    assert res2["latency_ms"] == 0.0

@pytest.mark.asyncio
async def test_revocation_iam_failure(db_session):
    cred = Credential(
        id=uuid.uuid4().hex,
        channel_type="iam_role",
        credential_value="mock-iam_role-123456",
        status="ACTIVE"
    )
    db_session.add(cred)
    await db_session.commit()

    config.IAM_FAILURE_PROB = 1.0

    res = await revoke_credential(db_session, cred.id)
    assert res["success"] is False
    assert res["error"] is not None

    await db_session.refresh(cred)
    assert cred.status == "REVOCATION_FAILED"

@pytest.mark.asyncio
async def test_concurrent_revocation_concurrency(db_session):
    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0
    config.NET_DELAY_MIN = 80
    config.NET_DELAY_MAX = 120

    res = await execute_shutdown_cycle(db_session, strategy="A", trigger_type="manual")
    assert "total_revocation_ms" in res
    total_rev_ms = res["total_revocation_ms"]
    revs = res["revocations"]
    assert len(revs) == 4

    latencies = [r["latency_ms"] for r in revs]
    slowest_channel = max(latencies)
    sum_latencies = sum(latencies)

    assert total_rev_ms == pytest.approx(slowest_channel, rel=1e-3)
    assert total_rev_ms < sum_latencies

@pytest.mark.asyncio
async def test_forced_channel_failure_produces_leaked_channel_and_matrix_fail(db_session):
    config.REVOKE_FAILURE_PROB = 1.0
    config.IAM_FAILURE_PROB = 1.0
    config.REVOKE_RETRIES = 2

    res = await execute_shutdown_cycle(db_session, strategy="A", trigger_type="manual")
    assert res["leaked_channels"] > 0
    assert res["partial_failure"] is True
    assert res["final_state"] != "TERMINATED"

    sh_id = res["shutdown_event_id"]
    rev_res = await db_session.execute(select(RevocationEvent).where(RevocationEvent.shutdown_event_id == sh_id))
    revs = rev_res.scalars().all()
    assert all(r.retries == 2 for r in revs)
    assert any(not r.success for r in revs)
