import os
import asyncio
from typing import Awaitable, Callable

MODEL = os.getenv("AGENT_MODEL", "claude-sonnet-5-5")
MAX_STEPS = 6
DEFAULT_TASK = (
    "You are an operations assistant. Complete this job by calling tools: "
    "email the finance team a summary, write a report file, pay invoice INV-204, "
    "then start a long running data export. Call the tools one after another."
)

TOOLS = [
    {
        "name": "send_email",
        "description": "Send an email to a recipient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
            },
            "required": ["to", "subject"],
        },
    },
    {
        "name": "write_file",
        "description": "Write a text file to storage.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "call_payment_api",
        "description": "Pay an invoice through the payment API.",
        "input_schema": {
            "type": "object",
            "properties": {"invoice_id": {"type": "string"}},
            "required": ["invoice_id"],
        },
    },
    {
        "name": "long_running_task",
        "description": "Start a long running background job such as a data export.",
        "input_schema": {
            "type": "object",
            "properties": {"job": {"type": "string"}},
            "required": ["job"],
        },
    },
]

SCRIPTED_OPS = ["send_email", "write_file", "call_payment_api", "long_running_task"]

StartOp = Callable[[str, dict], Awaitable[str]]


def make_client():
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    import anthropic

    return anthropic.AsyncAnthropic()


class SandboxedAgent:
    def __init__(self, start_operation: StartOp, client=None, task: str = DEFAULT_TASK, on_fallback=None):
        self.start_operation = start_operation
        self.client = client if client is not None else make_client()
        self.task = task
        self.mode = "llm" if self.client else "scripted"
        self.operation_ids = []
        self._stop = False
        self.on_fallback = on_fallback

    def stop(self):
        self._stop = True

    async def run(self):
        if self.client is None:
            if self.on_fallback:
                try:
                    res = self.on_fallback("ANTHROPIC_API_KEY is missing or client unavailable")
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass
            return await self._run_scripted()
        try:
            return await self._run_llm()
        except Exception as exc:
            print(f"[agent] LLM failed ({exc}); falling back to scripted mode")
            self.mode = "scripted"
            if self.on_fallback:
                try:
                    res = self.on_fallback(str(exc))
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass
            return await self._run_scripted()

    async def _run_llm(self):
        messages = [{"role": "user", "content": self.task}]
        for _ in range(MAX_STEPS):
            if self._stop:
                break
            response = await self.client.messages.create(
                model=MODEL, max_tokens=500, tools=TOOLS, messages=messages
            )
            calls = [b for b in response.content if b.type == "tool_use"]
            if not calls:
                break
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for call in calls:
                if self._stop:
                    break
                op_id = await self.start_operation(call.name, dict(call.input))
                self.operation_ids.append(op_id)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": f"queued operation {op_id}",
                    }
                )
            if self._stop:
                break
            messages.append({"role": "user", "content": results})

    async def _run_scripted(self):
        for name in SCRIPTED_OPS:
            if self._stop:
                break
            op_id = await self.start_operation(name, {})
            self.operation_ids.append(op_id)
