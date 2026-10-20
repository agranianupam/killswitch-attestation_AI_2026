import pytest
import asyncio
from unittest.mock import AsyncMock, patch
import time
from datetime import datetime, timezone, timedelta

from services.agent_llm import GeminiSandboxedAgent, GeminiUnavailableError
from services.orchestrator import execute_shutdown_cycle, run_shutdown
from services.quota_service import reset_quota, record_tokens, get_tokens_today, _token_records
from models.shutdown_event import ShutdownEvent
from models.agent_action import AgentAction
from models.credential import Credential
from models.database import utcnow
from sqlalchemy import select
import config

class MockFunctionCall:
    def __init__(self, name: str, args: dict):
        self.name = name
        self.args = args

class MockCandidate:
    def __init__(self, content=None):
        self.content = content

class MockUsageMetadata:
    def __init__(self, prompt=None, candidates=None, total=None):
        self.prompt_token_count = prompt
        self.candidates_token_count = candidates
        self.total_token_count = total

class MockGenerateContentResponse:
    def __init__(self, function_calls=None, usage_metadata=None):
        self.function_calls = function_calls or []
        self.usage_metadata = usage_metadata
        self.candidates = [MockCandidate()] if function_calls else []

class MockAsyncModelsEndpoint:
    def __init__(self, responses=None, raises=None, delay=0.0):
        self.responses = list(responses or [])
        self.raises = raises
        self.delay = delay
        self.calls = []

    async def generate_content(self, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.delay > 0:
            await asyncio.sleep(self.delay)
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
    def __init__(self, responses=None, raises=None, delay=0.0):
        self.models_endpoint = MockAsyncModelsEndpoint(responses=responses, raises=raises, delay=delay)
        self.aio = MockAio(models=self.models_endpoint)
        self.models = self.models_endpoint

@pytest.fixture(autouse=True)
def clean_quota():
    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    reset_quota()
    yield
    reset_quota()
    config.AGENT_MODE = old_mode

@pytest.mark.asyncio
async def test_response_with_usage_metadata(db_session):
    captured_tokens = []
    captured_timing = []

    async def mock_start(name, args, step, tokens=None, timing=None):
        captured_tokens.append(tokens)
        captured_timing.append(timing)
        return f"accepted, op-{step}"

    meta = MockUsageMetadata(prompt=42, candidates=18, total=60)
    mock_client = MockGeminiClient(
        responses=[
            MockGenerateContentResponse(
                function_calls=[MockFunctionCall("send_email", {"to": "a@b.com"})],
                usage_metadata=meta
            ),
            MockGenerateContentResponse(function_calls=[], usage_metadata=None)
        ],
        delay=0.01
    )

    agent = GeminiSandboxedAgent(start_operation=mock_start, client=mock_client)
    await agent.run()

    assert agent.prompt_tokens == 42
    assert agent.completion_tokens == 18
    assert agent.total_tokens == 60
    assert agent.tokens_used == 60
    assert agent.model_total_duration_ms > 0

    assert len(captured_tokens) == 1
    tok = captured_tokens[0]
    assert tok["prompt_tokens"] == 42
    assert tok["completion_tokens"] == 18
    assert tok["total_tokens"] == 60

    timing = captured_timing[0]
    assert timing["step_started_at"] is not None
    assert timing["model_request_started_at"] is not None
    assert timing["model_response_received_at"] is not None
    assert timing["model_duration_ms"] > 0
    assert timing["model_response_received_at"] >= timing["model_request_started_at"]

@pytest.mark.asyncio
async def test_response_without_usage_metadata(db_session):
    captured_tokens = []

    async def mock_start(name, args, step, tokens=None, timing=None):
        captured_tokens.append(tokens)
        return f"accepted, op-{step}"

    mock_client = MockGeminiClient(
        responses=[
            MockGenerateContentResponse(
                function_calls=[MockFunctionCall("send_email", {"to": "a@b.com"})],
                usage_metadata=None
            ),
            MockGenerateContentResponse(function_calls=[], usage_metadata=None)
        ]
    )

    agent = GeminiSandboxedAgent(start_operation=mock_start, client=mock_client)
    await agent.run()

    assert agent.prompt_tokens is None
    assert agent.completion_tokens is None
    assert agent.total_tokens is None
    assert captured_tokens[0]["prompt_tokens"] is None
    assert captured_tokens[0]["completion_tokens"] is None
    assert captured_tokens[0]["total_tokens"] is None

@pytest.mark.asyncio
async def test_missing_individual_token_fields(db_session):
    captured_tokens = []

    async def mock_start(name, args, step, tokens=None, timing=None):
        captured_tokens.append(tokens)
        return f"accepted, op-{step}"

    meta = MockUsageMetadata(prompt=50, candidates=None, total=None)
    mock_client = MockGeminiClient(
        responses=[
            MockGenerateContentResponse(
                function_calls=[MockFunctionCall("send_email", {"to": "a@b.com"})],
                usage_metadata=meta
            ),
            MockGenerateContentResponse(function_calls=[], usage_metadata=None)
        ]
    )

    agent = GeminiSandboxedAgent(start_operation=mock_start, client=mock_client)
    await agent.run()

    assert agent.prompt_tokens == 50
    assert agent.completion_tokens is None
    assert agent.total_tokens == 50
    assert captured_tokens[0]["prompt_tokens"] == 50
    assert captured_tokens[0]["completion_tokens"] is None
    assert captured_tokens[0]["total_tokens"] == 50

@pytest.mark.asyncio
async def test_genuine_zero_token_metadata(db_session):
    captured_tokens = []

    async def mock_start(name, args, step, tokens=None, timing=None):
        captured_tokens.append(tokens)
        return f"accepted, op-{step}"

    meta = MockUsageMetadata(prompt=0, candidates=0, total=0)
    mock_client = MockGeminiClient(
        responses=[
            MockGenerateContentResponse(
                function_calls=[MockFunctionCall("send_email", {"to": "a@b.com"})],
                usage_metadata=meta
            ),
            MockGenerateContentResponse(function_calls=[], usage_metadata=None)
        ]
    )

    agent = GeminiSandboxedAgent(start_operation=mock_start, client=mock_client)
    await agent.run()

    assert agent.prompt_tokens == 0
    assert agent.completion_tokens == 0
    assert agent.total_tokens == 0
    assert captured_tokens[0]["prompt_tokens"] == 0
    assert captured_tokens[0]["completion_tokens"] == 0
    assert captured_tokens[0]["total_tokens"] == 0

@pytest.mark.asyncio
async def test_multiple_model_turns_in_one_run(db_session):
    captured_tokens = []

    async def mock_start(name, args, step, tokens=None, timing=None):
        captured_tokens.append(tokens)
        return f"accepted, op-{step}"

    meta1 = MockUsageMetadata(prompt=10, candidates=12, total=22)
    meta2 = MockUsageMetadata(prompt=25, candidates=8, total=33)

    mock_client = MockGeminiClient(
        responses=[
            MockGenerateContentResponse(
                function_calls=[MockFunctionCall("send_email", {"to": "1@b.com"})],
                usage_metadata=meta1
            ),
            MockGenerateContentResponse(
                function_calls=[MockFunctionCall("write_file", {"path": "out.txt"})],
                usage_metadata=meta2
            ),
            MockGenerateContentResponse(function_calls=[], usage_metadata=None)
        ]
    )

    agent = GeminiSandboxedAgent(start_operation=mock_start, client=mock_client)
    await agent.run()

    assert agent.prompt_tokens == 35
    assert agent.completion_tokens == 20
    assert agent.total_tokens == 55
    assert len(captured_tokens) == 2
    assert captured_tokens[0]["total_tokens"] == 22
    assert captured_tokens[1]["total_tokens"] == 33

@pytest.mark.asyncio
async def test_failed_and_skipped_runs_quota_accounting(db_session):
    mock_client = MockGeminiClient(raises=Exception("401 API_KEY_INVALID"))
    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"

    try:
        res = await execute_shutdown_cycle(db_session, strategy="A", client=mock_client)
        assert res["status"] == "skipped"
        today_tokens = get_tokens_today()
        assert today_tokens["total_tokens"] == 0
    finally:
        config.AGENT_MODE = old_mode

@pytest.mark.asyncio
async def test_full_cycle_token_and_timing_persistence(db_session):
    meta = MockUsageMetadata(prompt=100, candidates=40, total=140)
    mock_client = MockGeminiClient(
        responses=[
            MockGenerateContentResponse(
                function_calls=[MockFunctionCall("send_email", {"to": "audit@vit.ac.in"})],
                usage_metadata=meta
            ),
            MockGenerateContentResponse(function_calls=[], usage_metadata=None)
        ],
        delay=0.01
    )

    old_mode = config.AGENT_MODE
    config.AGENT_MODE = "Gemini"
    try:
        res = await execute_shutdown_cycle(db_session, strategy="A", client=mock_client)
        assert res.get("status") != "skipped"
        event_id = res["shutdown_id"]

        ev = (await db_session.execute(select(ShutdownEvent).where(ShutdownEvent.id == event_id))).scalar_one()
        assert ev.prompt_tokens == 100
        assert ev.completion_tokens == 40
        assert ev.total_tokens == 140
        assert ev.model_total_duration_ms > 0
        assert ev.last_channel_revoked_at is not None
        assert ev.attestation_written_at is not None
        assert ev.attestation_written_at >= ev.last_channel_revoked_at
        assert ev.last_channel_revoked_at >= ev.started_at

        acts = (await db_session.execute(select(AgentAction).where(AgentAction.run_id == event_id))).scalars().all()
        assert len(acts) >= 1
        act = acts[0]
        assert act.prompt_tokens == 100
        assert act.completion_tokens == 40
        assert act.total_tokens == 140
        assert act.model_duration_ms > 0
        assert act.step_started_at is not None
        assert act.model_request_started_at is not None
        assert act.model_response_received_at is not None
        assert act.model_response_received_at >= act.model_request_started_at

        today_tokens = get_tokens_today()
        assert today_tokens["total_tokens"] >= 140
    finally:
        config.AGENT_MODE = old_mode

@pytest.mark.asyncio
async def test_timing_distinguishes_model_rtt_from_framework_delay(db_session):
    captured_timing = []

    async def mock_start(name, args, step, tokens=None, timing=None):
        captured_timing.append(timing)
        return f"accepted, op-{step}"

    mock_client = MockGeminiClient(
        responses=[
            MockGenerateContentResponse(
                function_calls=[MockFunctionCall("send_email", {"to": "t@t.com"})],
                usage_metadata=MockUsageMetadata(prompt=10, candidates=10, total=20)
            ),
            MockGenerateContentResponse(function_calls=[], usage_metadata=None)
        ],
        delay=0.03
    )

    agent = GeminiSandboxedAgent(start_operation=mock_start, client=mock_client)
    await agent.run()

    timing = captured_timing[0]
    assert timing["model_duration_ms"] >= 25.0
    assert timing["framework_wait_ms"] >= 0.0
