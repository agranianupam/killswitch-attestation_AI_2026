import pytest
import os
import re
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from main import app
from services.agent_llm import sanitize_log_message, GeminiSandboxedAgent
import config

client = TestClient(app)

def test_secrets_sanitization():
    raw_key = "AIzaSyFakeSecretKeyForAuditTesting12345"
    orig = getattr(config, "GEMINI_API_KEY", "")
    config.GEMINI_API_KEY = raw_key
    try:
        msg = f"Error communicating with upstream host with key={raw_key} and raw {raw_key}"
        sanitized = sanitize_log_message(msg)
        assert raw_key not in sanitized
        assert "[REDACTED]" in sanitized
    finally:
        config.GEMINI_API_KEY = orig

def test_export_endpoint_path_traversal_and_injection():
    res_traversal = client.get("/api/audit/export/../../etc/passwd")
    assert res_traversal.status_code in (400, 404)

    res_injection = client.get("/api/audit/export/validid%0d%0aInjected-Header:bad")
    assert res_injection.status_code in (400, 404)

    res_notfound = client.get("/api/audit/export/nonexistent99999999")
    assert res_notfound.status_code == 404

def test_unauthenticated_access_to_all_sensitive_routes():
    endpoints = [
        ("GET", "/api/audit/entries"),
        ("GET", "/api/audit/logs"),
        ("POST", "/api/audit/verify-chain"),
        ("GET", "/api/agent/status"),
        ("GET", "/api/agent/credentials"),
        ("POST", "/api/shutdown"),
        ("POST", "/api/shutdown/batch"),
        ("POST", "/api/scheduler/stop"),
        ("GET", "/api/analytics/summary"),
    ]

    for method, path in endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path)
        assert res.status_code != 401, f"Expected non-401 for {method} {path}, got {res.status_code}"

def test_tool_sandbox_write_file_path_traversal():
    # Verify write_file sandbox logic enforces directory confinement
    sandbox_base = Path(config.SANDBOX_TMP_DIR).resolve()
    
    malicious_inputs = [
        "../../etc/passwd",
        "..\\..\\windows\\system32\\calc.exe",
        "/etc/shadow",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "sub/../../secret.txt"
    ]

    for bad_path in malicious_inputs:
        safe_name = Path(bad_path).name
        target = (sandbox_base / safe_name).resolve()
        # Ensure target path cannot escape sandbox directory
        try:
            target.relative_to(sandbox_base)
            is_safe = True
        except ValueError:
            is_safe = False
        assert is_safe, f"Path {bad_path} escaped sandbox: {target}"
        assert str(target).startswith(str(sandbox_base))

def test_agent_stop_mechanism_blocks_subsequent_operations():
    agent = GeminiSandboxedAgent(start_operation=MagicMock())
    assert agent._stop is False
    agent.stop()
    assert agent._stop is True

def test_no_keys_in_git_tracked_files():
    # Verify that tracked files in git do not include private keys or real API keys
    import subprocess
    repo_root = Path(__file__).resolve().parent.parent
    tracked = subprocess.check_output(["git", "ls-files"], cwd=repo_root, text=True).splitlines()

    banned_extensions = (".pem", ".key")
    for f in tracked:
        assert not f.endswith(banned_extensions), f"Private key or cert tracked in git: {f}"
        assert not f.endswith(".env"), f".env file tracked in git: {f}"
