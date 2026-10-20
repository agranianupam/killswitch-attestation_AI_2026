import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
from sqlalchemy import select

from models.agent import Agent
from models.credential import Credential, CHANNEL_TYPES
from models.operation import SimulatedOperation
from models.shutdown_event import ShutdownEvent, RevocationEvent
from models.agent_action import AgentAction
from models.attestation import AttestationEntry
from models.skipped_run import SkippedRun

from services.agent_service import provision_fresh_agent
from services.orchestrator import execute_shutdown_cycle
from services.crypto_service import verify_chain, load_public_key
from services.export_service import export_signed_report
from services.agent_llm import GeminiUnavailableError
from scripts.verify_attestation import parse_markdown_report, verify_single_attestation
from api.websocket import manager
from main import app
from fastapi.testclient import TestClient
import config

client = TestClient(app)

class MockModelCall:
    def __init__(self, fn_name, fn_args, usage_metadata=None):
        call = MagicMock()
        call.name = fn_name
        call.args = fn_args
        self.function_calls = [call]
        self.candidates = [MagicMock(content=MagicMock())]
        self.usage_metadata = usage_metadata

@pytest.mark.asyncio
async def test_category_a_complete_offline_integration(db_session):

    agent = await provision_fresh_agent(db_session)
    assert agent.id is not None
    assert agent.status == "ACTIVE"

    creds_res = await db_session.execute(select(Credential).where(Credential.agent_id == agent.id))
    creds = creds_res.scalars().all()
    assert len(creds) == 4
    found_channels = {c.channel_type for c in creds}
    assert found_channels == set(CHANNEL_TYPES)

    mock_client = MagicMock()
    mock_meta = MagicMock(prompt_token_count=120, candidates_token_count=45, total_token_count=165)
    mock_call1 = MockModelCall("send_email", {"to": "audit@vit.ac.in", "subject": "Test"}, mock_meta)

    mock_client.aio.models.generate_content = AsyncMock(side_effect=[mock_call1, None])

    broadcast_messages = []
    orig_broadcast = manager.broadcast
    async def mock_broadcast(msg):
        broadcast_messages.append(msg)
    manager.broadcast = mock_broadcast

    orig_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    try:
        res = await execute_shutdown_cycle(
            db_session,
            strategy="C",
            trigger_type="manual",
            triggered_by="admin",
            client=mock_client
        )
    finally:
        config.AGENT_MODE = orig_mode
        manager.broadcast = orig_broadcast

    assert "shutdown_event_id" in res
    assert res.get("status") != "skipped"
    shutdown_id = res["shutdown_event_id"]
    assert shutdown_id is not None

    sh_event = await db_session.get(ShutdownEvent, shutdown_id)
    assert sh_event is not None
    assert sh_event.strategy == "C"
    assert sh_event.agent_mode == "gemini"
    assert sh_event.final_state in ("TERMINATED", "CONTAINED")

    revs_res = await db_session.execute(select(RevocationEvent).where(RevocationEvent.shutdown_event_id == shutdown_id))
    revs = revs_res.scalars().all()
    assert len(revs) == 4
    for r in revs:
        assert r.channel_type in CHANNEL_TYPES

    att_res = await db_session.execute(select(AttestationEntry).where(AttestationEntry.shutdown_event_id == shutdown_id))
    att = att_res.scalar_one_or_none()
    assert att is not None
    assert att.signature is not None
    assert att.entry_hash is not None
    assert att.prev_hash == "GENESIS"

    pub_key = load_public_key()
    chain_status = await verify_chain(db_session, pub_key)
    assert chain_status["valid"] is True
    assert chain_status["entries_checked"] >= 1

    api_res = client.get("/api/analytics/summary")
    assert api_res.status_code == 200

    audit_res = client.get("/api/audit/entries")
    assert audit_res.status_code == 200
    entries = audit_res.json()
    assert len(entries) >= 1

    msg_types = {m["type"] for m in broadcast_messages}
    assert "shutdown_progress" in msg_types
    assert "agent_action" in msg_types

    orig_key = getattr(config, "GEMINI_API_KEY", "")
    orig_mode2 = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    config.GEMINI_API_KEY = ""
    try:
        skip_res = await execute_shutdown_cycle(
            db_session,
            strategy="A",
            trigger_type="manual",
            triggered_by="admin",
            client=None
        )
        assert skip_res.get("status") == "skipped"
        assert "authentication" in skip_res["reason"].lower() or "gemini" in skip_res["reason"].lower()

        skip_records = (await db_session.execute(select(SkippedRun))).scalars().all()
        assert len(skip_records) >= 1
        assert "authentication" in skip_records[-1].reason.lower() or "gemini" in skip_records[-1].reason.lower()
    finally:
        config.AGENT_MODE = orig_mode2
        config.GEMINI_API_KEY = orig_key

    report_md = await export_signed_report(db_session, shutdown_id)
    assert "## 5. Canonical Attestation Payload" in report_md
    parsed = parse_markdown_report(report_md)
    single_res = verify_single_attestation(
        parsed["payload_json"],
        parsed["signature"],
        parsed["prev_hash"],
        parsed["entry_hash"],
        pub_key
    )
    assert single_res["hash_valid"] is True
    assert single_res["signature_valid"] is True
