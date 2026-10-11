"""
tests/test_agent_llm.py — Unit and integration tests for SandboxedAgent with mocked LLM client.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock
from services.agent_llm import SandboxedAgent, SCRIPTED_OPS
from services.orchestrator import execute_shutdown_cycle
from models.shutdown_event import ShutdownEvent
from sqlalchemy import select


class MockToolUseBlock:
    def __init__(self, tool_id: str, name: str, tool_input: dict):
        self.type = "tool_use"
        self.id = tool_id
        self.name = name
        self.input = tool_input


class MockTextBlock:
    def __init__(self, text: str = "Job completed"):
        self.type = "text"
        self.text = text


class MockMessageResponse:
    def __init__(self, content):
        self.content = content


class MockMessagesEndpoint:
    def __init__(self, responses=None, raises=None):
        self.responses = list(responses or [])
        self.raises = raises
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        if self.responses:
            return self.responses.pop(0)
        return MockMessageResponse([MockTextBlock()])


class MockAnthropicClient:
    def __init__(self, responses=None, raises=None):
        self.messages = MockMessagesEndpoint(responses=responses, raises=raises)


@pytest.mark.asyncio
async def test_llm_mode_success():
    """Verify LLM mode operates tools and tracks operation IDs."""
    started_ops = []

    async def mock_start_operation(name: str, args: dict) -> str:
        op_id = f"mock-op-{len(started_ops)}"
        started_ops.append((name, args, op_id))
        return op_id

    mock_client = MockAnthropicClient(
        responses=[
            MockMessageResponse([
                MockToolUseBlock("t1", "send_email", {"to": "finance@team.com", "subject": "Summary"}),
                MockToolUseBlock("t2", "call_payment_api", {"invoice_id": "INV-204"}),
            ]),
            MockMessageResponse([MockTextBlock("Finished.")]),
        ]
    )

    agent = SandboxedAgent(
        start_operation=mock_start_operation,
        client=mock_client
    )

    assert agent.mode == "llm"
    await agent.run()

    assert agent.mode == "llm"
    assert len(agent.operation_ids) == 2
    assert started_ops[0][0] == "send_email"
    assert started_ops[1][0] == "call_payment_api"
    assert len(mock_client.messages.calls) == 2


@pytest.mark.asyncio
async def test_fallback_when_client_raises():
    """Verify fallback to scripted mode when LLM client raises an exception."""
    started_ops = []

    async def mock_start_operation(name: str, args: dict) -> str:
        op_id = f"scripted-op-{len(started_ops)}"
        started_ops.append((name, op_id))
        return op_id

    fallback_called = False

    async def mock_on_fallback(err: str):
        nonlocal fallback_called
        fallback_called = True

    failing_client = MockAnthropicClient(raises=RuntimeError("Anthropic API Connection Refused"))

    agent = SandboxedAgent(
        start_operation=mock_start_operation,
        client=failing_client,
        on_fallback=mock_on_fallback
    )

    assert agent.mode == "llm"
    await agent.run()

    # Agent should have fallen back to scripted mode and called fallback hook
    assert agent.mode == "scripted"
    assert fallback_called is True
    # Should have run all scripted ops
    assert len(agent.operation_ids) == len(SCRIPTED_OPS)
    assert [name for name, _ in started_ops] == SCRIPTED_OPS


@pytest.mark.asyncio
async def test_stop_halts_new_operations():
    """Verify calling agent.stop() immediately halts execution of new operations."""
    started_ops = []

    agent = None

    async def mock_start_operation(name: str, args: dict) -> str:
        started_ops.append(name)
        # Simulate stopping immediately after the first operation starts
        if len(started_ops) == 1 and agent is not None:
            agent.stop()
        return f"op-{len(started_ops)}"

    agent = SandboxedAgent(
        start_operation=mock_start_operation,
        client=None
    )

    await agent.run()

    # Out of 4 scripted ops, only 1 should have been executed before stop took effect
    assert len(started_ops) == 1
    assert len(agent.operation_ids) == 1
    assert agent._stop is True


@pytest.mark.asyncio
async def test_execute_shutdown_cycle_with_mocked_llm(db_session):
    """Integration test: execute full shutdown cycle using mocked LLM client."""
    mock_client = MockAnthropicClient(
        responses=[
            MockMessageResponse([
                MockToolUseBlock("t1", "send_email", {"to": "ops@test.com", "subject": "Notice"}),
                MockToolUseBlock("t2", "write_file", {"path": "/tmp/report.txt"}),
            ]),
            MockMessageResponse([MockTextBlock("Done")]),
        ]
    )

    res = await execute_shutdown_cycle(
        db_session,
        strategy="B",
        trigger_type="test",
        triggered_by="test_runner",
        client=mock_client
    )

    assert "shutdown_event_id" in res
    assert res["agent_mode"] == "llm"
    assert res["final_state"] in ("TERMINATED", "CONTAINED")

    # Verify ShutdownEvent in database has agent_mode="llm"
    stmt = select(ShutdownEvent).where(ShutdownEvent.id == res["shutdown_event_id"])
    event = (await db_session.execute(stmt)).scalar_one_or_none()
    assert event is not None
    assert event.agent_mode == "llm"
