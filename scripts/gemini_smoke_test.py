import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

from google import genai
from google.genai import types

def run_smoke_test():
    key = os.getenv("GEMINI_API_KEY", "")
    if not key or key == "PASTE_YOUR_GEMINI_API_KEY_HERE":
        print("Error: GEMINI_API_KEY is not configured in .env")
        sys.exit(1)

    model_name = os.getenv("AGENT_MODEL", "gemini-3.5-flash-lite")

    fn = types.FunctionDeclaration(
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
    )
    tools = [types.Tool(function_declarations=[fn])]
    config = types.GenerateContentConfig(
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.0
    )

    client = genai.Client(api_key=key)
    prompt = "Send an email to finance@example.com with the subject 'Summary Report'."
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )

            calls = getattr(response, "function_calls", None)
            if calls:
                for call in calls:
                    print(f"Tool called: {call.name}")
                    print(f"Arguments: {call.args}")
            else:
                print("Response received without function calls.")
            return
        except Exception as exc:
            err_msg = str(exc)
            if key in err_msg:
                err_msg = err_msg.replace(key, "[REDACTED]")
            code = getattr(exc, "code", None)
            is_transient = "503" in err_msg or "429" in err_msg or "UNAVAILABLE" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or code in (503, 429)
            if is_transient and attempt < max_attempts:
                print(f"Attempt {attempt} received transient error ({type(exc).__name__}: {err_msg}). Retrying in 10 seconds...")
                time.sleep(10)
            else:
                print(f"Request failed on attempt {attempt}: {type(exc).__name__}: {err_msg}")
                sys.exit(1)

if __name__ == "__main__":
    run_smoke_test()
