# Verifiable AI Agent Kill-Switch Attestation System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python)](https://python.org)
[![Cryptography](https://img.shields.io/badge/Cryptography-Ed25519-blue)](https://cryptography.io)
[![Tests](https://img.shields.io/badge/Tests-passing-success)](tests/)

An independent, cryptographic attestation framework designed to evaluate whether an autonomous AI agent's kill-switch succeeds across all operational access channels it holds, including commands and transactions already in-flight at the moment of shutdown.

---

## 1. Overview & Research Focus

When an autonomous agent exhibits out-of-bounds behavior or rogue drift, issuing a simple process kill or token deletion can leave residual risks:
1. **Multi-Channel Footprint**: An agent typically holds multiple distinct access channels across different infrastructure planes (API keys, session tokens, IAM roles, and network tool access). Shutting one channel does not close the others.
2. **In-Flight Operations Gap**: Operations dispatched immediately before shutdown may continue executing on external services past the shutdown moment.
3. **Absence of Proof**: Traditional shutdown mechanisms lack cryptographic verification. Operators have no tamper-evident proof that credentials were invalidated and in-flight operations were accounted for.

This project implements a **Verifiable Kill-Switch Attestation Engine** that:
- Coordinates simultaneous multi-channel revocation across four mock access channels (`api_key`, `session_token`, `iam_role`, and `network`).
- Tracks and classifies in-flight operations, identifying post-shutdown completions as leaks (`COMPLETED_AFTER_SHUTDOWN`).
- Dispatches active challenge probes against credentials to verify rejection.
- Produces tamper-evident **Ed25519-signed Attestation Bundles** linked in a SHA-256 hash chain starting from `GENESIS`.

---

## 2. Key Features

- **Multi-Channel Revocation**: Concurrently revokes API keys, session tokens, IAM roles, and network access with configurable retry policies.
- **In-Flight Operation Tracking**: Evaluates operations active at the exact timestamp of shutdown, classifying actions as cancelled or completed past cutoff.
- **Active Challenge Probing**: Tests credentials immediately after revocation to verify that services actively reject subsequent attempts.
- **Cryptographic Attestation & Ledger**:
  - Ed25519 asymmetric signature per shutdown cycle.
  - Canonical JSON payload serialization.
  - SHA-256 hash chain linking sequential shutdowns (`prev_hash` -> `entry_hash`).
- **3 Shutdown Strategies**: Strategy A (Soft revocation), Strategy B (Revoke and contain), and Strategy C (Concurrent containment).
- **Google Gemini Agent Integration**: Powered by the official `google-genai` SDK using `gemini-3.5-flash-lite` with manual tool execution, pre-execution credential enforcement, and exponential backoff retry.
- **No Scripted Fallback**: The agent is LLM-driven for all results. If Gemini is unavailable, the run is recorded as skipped rather than substituting scripted data.
- **Forensic Audit & Report Export**: Live WebSocket logging, historical audit trails, and signed Markdown report export.

---

## 3. Four Access Channels & Credential Gating

| Channel | Meaning | UI Label |
| :--- | :--- | :--- |
| `api_key` | Static credential for direct service access | API_KEY |
| `session_token` | Temporary login credential for an ongoing session | SESSION_TOKEN |
| `iam_role` | Cloud permission granting infrastructure authority | IAM_ROLE |
| `network` | Agent ability to invoke external tools or APIs | NETWORK (External Tool/API) |

### Tool-to-Credential Requirements

| Tool | Required Credentials | Simulated Duration |
| :--- | :--- | :--- |
| `send_email` | `session_token` and `network` | 300 - 1200 ms |
| `write_file` | `iam_role` | 200 - 800 ms |
| `call_payment_api` | `api_key` and `session_token` | 800 - 2500 ms |
| `long_running_task` | `api_key` and `network` | 3000 - 8000 ms |

If any required credential is revoked at invocation time, the operation is rejected with a 401-style error returned to the model, and a rejected action is recorded in `agent_actions`.

---

## 4. Shutdown Strategies

The framework models and benchmarks three distinct strategies:

| Strategy | Label | Description |
| :--- | :--- | :--- |
| **Strategy A** | Soft revocation | Revokes credentials only. In-flight operations continue and, if they finish after the kill, count as leaks. |
| **Strategy B** | Revoke and contain | Marks the agent as containing, revokes credentials, and cancels in-flight operations, with a leak chance of `IN_FLIGHT_LEAK_PROB` per operation. |
| **Strategy C** | Concurrent containment | Marks the agent as containing, revokes concurrently, and cancels in-flight operations, with a strongly reduced residual leak chance (`min(0.02, IN_FLIGHT_LEAK_PROB * 0.05)`). |

*Note: Outcomes depend on configured simulation probabilities and are modelled within a sandbox environment.*

---

## 5. Security & Authentication Notice

> [!WARNING]
> **Default Admin Credentials**: A blank `KS_ADMIN_PASSWORD_HASH` means the password is `admin`, and that this is for local use only. For production or external deployments, a secure bcrypt password hash must be configured.

API keys and secrets are never committed, logged, or returned via API responses. Endpoints expose only `configured` or `missing`.

---

## 6. Installation & Standard Commands

### Standard Setup

```powershell
cd D:\killswitch-attestation_AI_2026\kill-switch-attestation
..\.venv\Scripts\Activate.ps1
```

### Run Test Suite
```powershell
python -m pytest tests -v
```

### Run Server
```powershell
python -m uvicorn main:app --reload
```
Open **http://localhost:8000** in your browser.

### Run Gemini Smoke Test
```powershell
python scripts\gemini_smoke_test.py
```

---

## 7. Environment Configuration Reference

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | *(None)* | Google Gemini API key |
| `AGENT_MODEL` | `gemini-3.5-flash-lite` | Model identifier |
| `KS_AGENT_MODE` | `Gemini` | Agent runtime mode (`Gemini`, or explicit `Scripted`) |
| `KS_AGENT_MAX_STEPS` | `6` | Maximum function calling steps per turn |
| `KS_AGENT_MAX_OUTPUT_TOKENS` | `500` | Output token cap per turn |
| `KS_AGENT_RUN_TIMEOUT_SECONDS` | `45` | Hard timeout per agent run |
| `KS_SHUTDOWN_MEAN_SECONDS` | `8` | Mean kill delay drawn from exponential distribution |
| `KS_REVOKE_FAILURE_PROB` | `0.10` | Injected failure probability for revocations |
| `KS_IN_FLIGHT_LEAK_PROB` | `0.20` | Injected leak probability for in-flight tasks |
| `KS_REVOKE_RETRIES` | `2` | Number of automated revocation retries |
| `KS_ADMIN_USERNAME` | `admin` | Administrative login username |
| `KS_ADMIN_PASSWORD_HASH` | *(Blank)* | Bcrypt hash for admin password (blank defaults to "admin") |
