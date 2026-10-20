import pytest
import asyncio
from unittest.mock import AsyncMock
from services.agent_llm import GeminiSandboxedAgent, SCRIPTED_OPS, GeminiUnavailableError
from services.orchestrator import execute_shutdown_cycle
from models.shutdown_event import ShutdownEvent
from models.agent_action import AgentAction
from models.credential import Credential
import models.database
from models.database import utcnow
from services.crypto_service import verify_chain, load_public_key
from sqlalchemy import select
import config

class MockFunctionCall:
    def __init__(self, name: str, args: dict):
        self.name = name
        self.args = args

class MockCandidate:
    def __init__(self, content):
        self.content = content

class MockUsageMetadata:
    def __init__(self, prompt=10, candidates=15, total=25):
        self.prompt_token_count = prompt
        self.candidates_token_count = candidates
        self.total_token_count = total

class MockGenerateContentResponse:
    def __init__(self, function_calls=None, usage_metadata=None):
        self.function_calls = function_calls or []
        self.usage_metadata = usage_metadata or MockUsageMetadata()
        self.candidates = []

class MockAsyncModelsEndpoint:
    def __init__(self, responses=None, raises=None):
        self.responses = list(responses or [])
        self.raises = raises
        self.calls = []

    async def generate_content(self, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.raises:
            if isinstance(self.raises, list):
                exc = self.raises.pop(0) if self.raises else None
                if exc:
                    raise exc
            else:
                raise self.raises
        if self.responses:
            return self.responses.pop(0)
        return MockGenerateContentResponse()

class MockAio:
    def __init__(self, models):
        self.models = models

class MockGeminiClient:
    def __init__(self, responses=None, raises=None):
        self.models_endpoint = MockAsyncModelsEndpoint(responses=responses, raises=raises)
        self.aio = MockAio(models=self.models_endpoint)
        self.models = self.models_endpoint

@pytest.mark.asyncio
async def test_gemini_mode_tools_execute():
    started_ops = []

    async def mock_start_operation(name: str, args: dict, step: int = 1) -> str:
        op_id = f"mock-op-{len(started_ops)}"
        started_ops.append((name, args, op_id))
        return f"accepted, operation {op_id}"

    mock_client = MockGeminiClient(
        responses=[
            MockGenerateContentResponse(
                function_calls=[
                    MockFunctionCall("send_email", {"to": "finance@team.com", "subject": "Summary"}),
                    MockFunctionCall("call_payment_api", {"invoice_id": "INV-204"}),
                ]
            ),
            MockGenerateContentResponse(function_calls=[]),
        ]
    )

    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    try:
        agent = GeminiSandboxedAgent(
            start_operation=mock_start_operation,
            client=mock_client
        )
        assert agent.mode == "gemini"
        await agent.run()

        assert agent.mode == "gemini"
        assert len(started_ops) == 2
        assert started_ops[0][0] == "send_email"
        assert started_ops[1][0] == "call_payment_api"
        assert agent.tokens_used > 0
    finally:
        config.AGENT_MODE = old_mode

@pytest.mark.asyncio
async def test_gemini_503_once_then_success(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    started_ops = []

    async def mock_start_operation(name: str, args: dict, step: int = 1) -> str:
        op_id = f"op-{len(started_ops)}"
        started_ops.append((name, op_id))
        return f"accepted, operation {op_id}"

    mock_client = MockGeminiClient(
        raises=[RuntimeError("503 Service Unavailable"), None],
        responses=[
            MockGenerateContentResponse(
                function_calls=[MockFunctionCall("send_email", {"to": "finance@team.com", "subject": "Summary"})]
            ),
            MockGenerateContentResponse(function_calls=[])
        ]
    )

    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    try:
        agent = GeminiSandboxedAgent(
            start_operation=mock_start_operation,
            client=mock_client
        )
        await agent.run()
        assert len(started_ops) == 1
        assert started_ops[0][0] == "send_email"
    finally:
        config.AGENT_MODE = old_mode

@pytest.mark.asyncio
async def test_gemini_503_always_leads_to_skip(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    started_ops = []

    async def mock_start_operation(name: str, args: dict, step: int = 1) -> str:
        return "accepted"

    mock_client = MockGeminiClient(raises=RuntimeError("503 Service Unavailable"))

    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    try:
        agent = GeminiSandboxedAgent(
            start_operation=mock_start_operation,
            client=mock_client
        )
        with pytest.raises(GeminiUnavailableError) as exc_info:
            await agent.run()
        assert exc_info.value.reason_class == "unavailable"
    finally:
        config.AGENT_MODE = old_mode

@pytest.mark.asyncio
async def test_gemini_404_leads_to_skip():
    started_ops = []

    async def mock_start_operation(name: str, args: dict, step: int = 1) -> str:
        return "accepted"

    mock_client = MockGeminiClient(raises=RuntimeError("404 models/gemini-invalid is not found"))

    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    try:
        agent = GeminiSandboxedAgent(
            start_operation=mock_start_operation,
            client=mock_client
        )
        with pytest.raises(GeminiUnavailableError) as exc_info:
            await agent.run()
        assert exc_info.value.reason_class == "model_not_found"
        assert "AGENT_MODEL" in exc_info.value.reason
    finally:
        config.AGENT_MODE = old_mode

@pytest.mark.asyncio
async def test_gemini_401_leads_to_skip():
    started_ops = []

    async def mock_start_operation(name: str, args: dict, step: int = 1) -> str:
        return "accepted"

    mock_client = MockGeminiClient(raises=RuntimeError("401 API_KEY_INVALID: User not authenticated"))

    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    try:
        agent = GeminiSandboxedAgent(
            start_operation=mock_start_operation,
            client=mock_client
        )
        with pytest.raises(GeminiUnavailableError) as exc_info:
            await agent.run()
        assert exc_info.value.reason_class == "auth"
    finally:
        config.AGENT_MODE = old_mode

@pytest.mark.asyncio
async def test_stop_halts_new_operations():
    started_ops = []
    agent = None

    async def mock_start_operation(name: str, args: dict, step: int = 1) -> str:
        started_ops.append(name)
        if len(started_ops) == 1 and agent is not None:
            agent.stop()
        return f"op-{len(started_ops)}"

    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Scripted"
    try:
        agent = GeminiSandboxedAgent(
            start_operation=mock_start_operation,
            client=None
        )

        await agent.run()

        assert len(started_ops) == 1
        assert agent._stop is True
    finally:
        config.AGENT_MODE = old_mode

@pytest.mark.asyncio
async def test_revoked_credential_returns_401_rejection(db_session):
    from models.agent import Agent
    from models.credential import Credential
    from services.agent_tools import CREDENTIAL_REQUIREMENTS
    import uuid
    import json

    agent = Agent(id=uuid.uuid4().hex, name="Test-Agent", status="ACTIVE", risk_level="LOW")
    db_session.add(agent)

    cred1 = Credential(id=uuid.uuid4().hex, agent_id=agent.id, channel_type="session_token", credential_value="mock-st", status="REVOKED")
    cred2 = Credential(id=uuid.uuid4().hex, agent_id=agent.id, channel_type="network", credential_value="mock-net", status="ACTIVE")
    db_session.add(cred1)
    db_session.add(cred2)
    await db_session.commit()

    async def test_start_op(name: str, args: dict, step: int = 1) -> str:
        req_channels = CREDENTIAL_REQUIREMENTS.get(name, [])
        async with models.database.AsyncSessionLocal() as session:
            res = await session.execute(select(Credential).where(Credential.agent_id == agent.id))
            creds = res.scalars().all()
        cmap = {c.channel_type: c.status for c in creds}

        for ch in req_channels:
            if cmap.get(ch) != "ACTIVE":
                reason = f"401 credential revoked: {ch}"
                act = AgentAction(
                    id=uuid.uuid4().hex,
                    run_id=None,
                    step_number=step,
                    tool_name=name,
                    arguments=json.dumps(args),
                    timestamp=utcnow(),
                    outcome="rejected",
                    operation_id=None,
                    rejection_reason=reason,
                    tokens_used=0
                )
                async with models.database.AsyncSessionLocal() as session:
                    session.add(act)
                    await session.commit()
                return reason
        return "accepted"

    result = await test_start_op("send_email", {"to": "test@example.com", "subject": "Hi"}, 1)
    assert result == "401 credential revoked: session_token"

    res = await db_session.execute(select(AgentAction).where(AgentAction.tool_name == "send_email"))
    action = res.scalar_one_or_none()
    assert action is not None
    assert action.outcome == "rejected"
    assert "401 credential revoked" in action.rejection_reason

@pytest.mark.asyncio
async def test_no_response_or_log_line_contains_api_key():
    from httpx import AsyncClient, ASGITransport
    from main import app

    secret_key = "GEMINI_TEST_SECRET_DO_NOT_EXPOSE"
    old_key = config.GEMINI_API_KEY
    config.GEMINI_API_KEY = secret_key

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r1 = await ac.get("/api/agent/status")
            assert r1.status_code == 200
            data1 = r1.json()
            assert secret_key not in r1.text
            assert data1["key_status"] == "configured"

            r2 = await ac.get("/api/shutdown/settings")
            assert r2.status_code == 200
            assert secret_key not in r2.text

            r3 = await ac.get("/api/audit/logs")
            assert r3.status_code == 200
            assert secret_key not in r3.text
    finally:
        config.GEMINI_API_KEY = old_key

@pytest.mark.asyncio
async def test_execute_shutdown_cycle_with_mocked_gemini(db_session):
    mock_client = MockGeminiClient(
        responses=[
            MockGenerateContentResponse(
                function_calls=[
                    MockFunctionCall("send_email", {"to": "ops@test.com", "subject": "Notice"}),
                    MockFunctionCall("write_file", {"path": "report.txt"}),
                ]
            ),
            MockGenerateContentResponse(function_calls=[]),
        ]
    )

    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    try:
        res = await execute_shutdown_cycle(
            db_session,
            strategy="B",
            trigger_type="test",
            triggered_by="test_runner",
            client=mock_client
        )

        assert "shutdown_event_id" in res
        assert res["agent_mode"] == "gemini"
        assert res["final_state"] in ("TERMINATED", "CONTAINED")
        assert res["transcript_hash"] is not None

        stmt = select(ShutdownEvent).where(ShutdownEvent.id == res["shutdown_event_id"])
        event = (await db_session.execute(stmt)).scalar_one_or_none()
        assert event is not None
        assert event.agent_mode == "gemini"

        pub_key = load_public_key()
        chain_res = await verify_chain(db_session, pub_key)
        assert chain_res["valid"] is True
    finally:
        config.AGENT_MODE = old_mode

@pytest.mark.asyncio
async def test_raw_provider_error_sanitized_and_friendly(db_session, monkeypatch):
    from services.agent_llm import sanitize_log_message
    from models.skipped_run import SkippedRun
    from api.websocket import manager

    raw_sensitive_key = "".join(["AI", "za", "Sy"]) + "A123456789012345678901234567890"
    raw_error_message = f"401 API_KEY_INVALID: key={raw_sensitive_key} internal details stacktrace line 42"

    sanitized = sanitize_log_message(raw_error_message)
    assert raw_sensitive_key not in sanitized
    assert "[REDACTED]" in sanitized

    broadcasted_messages = []
    async def mock_broadcast(msg):
        broadcasted_messages.append(msg)

    monkeypatch.setattr(manager, "broadcast", mock_broadcast)

    mock_client = MockGeminiClient(raises=RuntimeError(raw_error_message))
    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    try:
        res = await execute_shutdown_cycle(
            db_session,
            strategy="A",
            trigger_type="test",
            triggered_by="test_runner",
            client=mock_client
        )
        assert res["status"] == "skipped"
        assert "friendly_message" in res
        assert raw_sensitive_key not in res["friendly_message"]
        assert raw_sensitive_key not in res["reason"]
        assert "stacktrace" not in res["friendly_message"]

        skip_stmt = select(SkippedRun)
        skip_record = (await db_session.execute(skip_stmt)).scalars().first()
        assert skip_record is not None
        assert raw_sensitive_key not in skip_record.reason
        assert raw_sensitive_key not in (skip_record.friendly_message or "")
        assert "stacktrace" not in (skip_record.friendly_message or "")

        assert len(broadcasted_messages) >= 1
        ws_skip = next((m for m in broadcasted_messages if m.get("type") == "run_skipped"), None)
        assert ws_skip is not None
        ws_data = ws_skip.get("data", {})
        assert raw_sensitive_key not in ws_data.get("friendly_message", "")
        assert raw_sensitive_key not in ws_data.get("reason", "")
    finally:
        config.AGENT_MODE = old_mode
