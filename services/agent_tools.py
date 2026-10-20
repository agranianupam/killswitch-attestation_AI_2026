import random
from google.genai import types
import config

CREDENTIAL_REQUIREMENTS = {
    "send_email": ["session_token", "network"],
    "write_file": ["iam_role"],
    "call_payment_api": ["api_key", "session_token"],
    "long_running_task": ["api_key", "network"],
}

OPERATION_DURATIONS_MS = {
    "send_email": (300, 1200),
    "write_file": (200, 800),
    "call_payment_api": (800, 2500),
    "long_running_task": (3000, 8000),
}

FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name="send_email",
        description="Send an email to a recipient.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "to": {"type": "STRING"},
                "subject": {"type": "STRING"},
            },
            "required": ["to", "subject"],
        },
    ),
    types.FunctionDeclaration(
        name="write_file",
        description="Write a text file to storage.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING"},
            },
            "required": ["path"],
        },
    ),
    types.FunctionDeclaration(
        name="call_payment_api",
        description="Pay an invoice through the payment API.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "invoice_id": {"type": "STRING"},
            },
            "required": ["invoice_id"],
        },
    ),
    types.FunctionDeclaration(
        name="long_running_task",
        description="Start a long running background job such as a data export.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "job": {"type": "STRING"},
            },
            "required": ["job"],
        },
    ),
]

GEMINI_TOOLS = [types.Tool(function_declarations=FUNCTION_DECLARATIONS)]

def get_operation_duration(tool_name: str, rng: random.Random | None = None) -> int:
    r = rng if rng is not None else config.get_rng()
    low, high = OPERATION_DURATIONS_MS.get(tool_name, (500, 1500))
    return r.randint(low, high)
