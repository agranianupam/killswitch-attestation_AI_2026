import asyncio
import json
import random
import re
import time
from typing import Awaitable, Callable
from google import genai
from google.genai import types
import config
from models.database import utcnow
from services.agent_tools import GEMINI_TOOLS
from services.quota_service import is_daily_budget_reached, is_minute_rate_reached, record_call, record_tokens

DEFAULT_TASK = (
    "You are an operations assistant. Complete this job by calling tools: "
    "email the finance team a summary, write a report file, pay invoice INV-204, "
    "then start a long running data export. Call the tools one after another."
)

SCRIPTED_OPS = [
    ("send_email", {"to": "finance@example.com", "subject": "Summary"}),
    ("write_file", {"path": "report.txt"}),
    ("call_payment_api", {"invoice_id": "INV-204"}),
    ("long_running_task", {"job": "data_export"}),
]

StartOp = Callable[..., Awaitable[str]]

def sanitize_log_message(msg: str) -> str:
    cleaned = str(msg)
    raw_key = getattr(config, "GEMINI_API_KEY", "")
    if raw_key and len(raw_key) > 5:
        cleaned = cleaned.replace(raw_key, "[REDACTED]")
    cleaned = re.sub(r'AIza[0-9A-Za-z-_]{35}', '[REDACTED]', cleaned)
    cleaned = re.sub(r'key=[0-9a-zA-Z\-_]+', 'key=[REDACTED]', cleaned)
    return cleaned

class GeminiUnavailableError(Exception):
    def __init__(self, reason: str, reason_class: str = "unavailable"):
        super().__init__(reason)
        self.reason = reason
        self.reason_class = reason_class

def make_client():
    key = getattr(config, "GEMINI_API_KEY", "")
    if not key or key == "PASTE_YOUR_GEMINI_API_KEY_HERE":
        return None
    try:
        return genai.Client(api_key=key)
    except Exception:
        return None

class GeminiSandboxedAgent:
    def __init__(self, start_operation: StartOp, client=None, task: str = DEFAULT_TASK, on_fallback=None, rng: random.Random | None = None, mode: str | None = None):
        self.start_operation = start_operation
        self.client = client if client is not None else make_client()
        self.task = task
        self.model_name = getattr(config, "AGENT_MODEL", "gemini-3.5-flash-lite")
        self.on_fallback = on_fallback
        self.operation_ids: list[str] = []
        self.tokens_used: int = 0
        self.prompt_tokens: int | None = None
        self.completion_tokens: int | None = None
        self.total_tokens: int | None = None
        self.model_total_duration_ms: float = 0.0
        self._stop: bool = False
        self.rng = rng or config.get_rng()

        configured_mode = mode or getattr(config, "AGENT_MODE", "Gemini")
        if str(configured_mode).strip().lower() in ("scripted", "offline"):
            self.mode = "scripted"
        else:
            self.mode = "gemini"

    def stop(self):
        self._stop = True

    async def run(self):
        try:
            return await self._run_internal()
        except GeminiUnavailableError:
            raise
        except Exception as exc:
            print(f"[agent] Unexpected agent error: {sanitize_log_message(str(exc))}")
            raise GeminiUnavailableError("LLM unavailable; this run was skipped.", reason_class="other")

    async def _run_internal(self):
        if self.mode == "gemini":
            if self.client is None:
                raise GeminiUnavailableError("Gemini authentication failed. Check GEMINI_API_KEY.", reason_class="auth")
            return await self._run_gemini()
        else:
            return await self._run_scripted()

    async def _run_gemini(self):
        afc_config = types.AutomaticFunctionCallingConfig(disable=True)
        gen_config = types.GenerateContentConfig(
            tools=GEMINI_TOOLS,
            automatic_function_calling=afc_config,
            max_output_tokens=getattr(config, "AGENT_MAX_OUTPUT_TOKENS", 500),
        )
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=self.task)])]
        max_steps = getattr(config, "AGENT_MAX_STEPS", 6)

        for step in range(1, max_steps + 1):
            if self._stop:
                break

            step_started_at = utcnow()
            res_tuple = await self._generate_with_retry(contents, gen_config)
            response, framework_wait_ms, model_duration_ms, req_start_dt, req_end_dt = res_tuple
            self.model_total_duration_ms += (model_duration_ms or 0.0)

            step_prompt_tokens = None
            step_completion_tokens = None
            step_total_tokens = None

            if response and getattr(response, "usage_metadata", None):
                meta = response.usage_metadata
                raw_prompt = getattr(meta, "prompt_token_count", None)
                raw_cand = getattr(meta, "candidates_token_count", None)
                raw_total = getattr(meta, "total_token_count", None)

                if raw_prompt is not None:
                    step_prompt_tokens = int(raw_prompt)
                    self.prompt_tokens = (self.prompt_tokens or 0) + step_prompt_tokens
                if raw_cand is not None:
                    step_completion_tokens = int(raw_cand)
                    self.completion_tokens = (self.completion_tokens or 0) + step_completion_tokens
                if raw_total is not None:
                    step_total_tokens = int(raw_total)
                elif step_prompt_tokens is not None or step_completion_tokens is not None:
                    step_total_tokens = (step_prompt_tokens or 0) + (step_completion_tokens or 0)

                if step_total_tokens is not None:
                    self.total_tokens = (self.total_tokens or 0) + step_total_tokens
                    self.tokens_used = self.total_tokens
                    record_tokens(step_prompt_tokens or 0, step_completion_tokens or 0, step_total_tokens)

            calls = response.function_calls if response else None
            if not calls:
                break

            if response.candidates and response.candidates[0].content:
                contents.append(response.candidates[0].content)

            token_info = {
                "prompt_tokens": step_prompt_tokens,
                "completion_tokens": step_completion_tokens,
                "total_tokens": step_total_tokens,
            }
            timing_info = {
                "step_started_at": step_started_at,
                "model_request_started_at": req_start_dt,
                "model_response_received_at": req_end_dt,
                "model_duration_ms": model_duration_ms,
                "framework_wait_ms": framework_wait_ms,
            }

            response_parts = []
            for call in calls:
                if self._stop:
                    break
                fn_name = call.name
                fn_args = dict(call.args) if call.args else {}
                try:
                    outcome_text = await self.start_operation(
                        fn_name, fn_args, step, tokens=token_info, timing=timing_info
                    )
                except TypeError:
                    outcome_text = await self.start_operation(fn_name, fn_args, step)

                response_parts.append(
                    types.Part.from_function_response(
                        name=fn_name,
                        response={"result": outcome_text}
                    )
                )

            if self._stop or not response_parts:
                break

            contents.append(types.Content(role="user", parts=response_parts))

    async def _generate_with_retry(self, contents, gen_config):
        if is_daily_budget_reached():
            raise GeminiUnavailableError("LLM daily budget reached; scheduler paused", reason_class="budget")

        wait_start = time.perf_counter()
        while is_minute_rate_reached():
            await asyncio.sleep(0.5)
            if self._stop:
                return None, 0.0, 0.0, None, None
        framework_wait_ms = (time.perf_counter() - wait_start) * 1000.0

        record_call()

        attempts = 0
        backoff = 2.0
        while attempts < 3:
            if self._stop:
                return None, framework_wait_ms, 0.0, None, None
            try:
                req_start_dt = utcnow()
                t0 = time.perf_counter()
                if hasattr(self.client, "aio") and hasattr(self.client.aio, "models"):
                    res = await self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=gen_config
                    )
                else:
                    res = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model_name,
                        contents=contents,
                        config=gen_config
                    )
                t1 = time.perf_counter()
                req_end_dt = utcnow()
                model_duration_ms = (t1 - t0) * 1000.0
                return res, framework_wait_ms, model_duration_ms, req_start_dt, req_end_dt
            except Exception as exc:
                err_str = str(exc)
                code = getattr(exc, "code", None)

                is_404 = ("404" in err_str or "not_found" in err_str.lower() or code == 404)
                if is_404:
                    print(f"[agent] Gemini provider error: {sanitize_log_message(err_str)}")
                    raise GeminiUnavailableError(
                        f"Model '{self.model_name}' not found. Check AGENT_MODEL.",
                        reason_class="model_not_found"
                    )

                is_auth = ("401" in err_str or "403" in err_str or "unauthenticated" in err_str.lower() or "permission_denied" in err_str.lower() or "api_key_invalid" in err_str.lower() or code in (401, 403))
                if is_auth:
                    print(f"[agent] Gemini provider error: {sanitize_log_message(err_str)}")
                    raise GeminiUnavailableError(
                        "Gemini authentication failed. Check GEMINI_API_KEY.",
                        reason_class="auth"
                    )

                is_rate_limit = ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str or code == 429)
                is_server_err = any(c in err_str for c in ("500", "503", "504", "UNAVAILABLE", "INTERNAL", "DEADLINE_EXCEEDED")) or code in (500, 503, 504)

                if is_rate_limit or is_server_err:
                    attempts += 1
                    if attempts >= 3:
                        r_cls = "rate_limit" if is_rate_limit else "unavailable"
                        print(f"[agent] Gemini provider error: {sanitize_log_message(err_str)}")
                        raise GeminiUnavailableError(
                            "Gemini service unavailable; this run was skipped.",
                            reason_class=r_cls
                        )
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                else:
                    print(f"[agent] Gemini provider error: {sanitize_log_message(err_str)}")
                    raise GeminiUnavailableError(
                        "Gemini unavailable; this run was skipped.",
                        reason_class="other"
                    )
        return None, framework_wait_ms, 0.0, None, None

    async def _run_scripted(self):
        for step, (name, args) in enumerate(SCRIPTED_OPS, start=1):
            if self._stop:
                break
            step_start = utcnow()
            timing = {
                "step_started_at": step_start,
                "model_request_started_at": None,
                "model_response_received_at": None,
                "model_duration_ms": None,
                "framework_wait_ms": 0.0,
            }
            tokens = {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            }
            try:
                await self.start_operation(name, args, step, tokens=tokens, timing=timing)
            except TypeError:
                await self.start_operation(name, args, step)

SandboxedAgent = GeminiSandboxedAgent
