# Verifiable AI Agent Kill-Switch Attestation System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://python.org)
[![Cryptography](https://img.shields.io/badge/Cryptography-RSA--PSS-blue)](https://cryptography.io)
[![Tests](https://img.shields.io/badge/Tests-23%20passed-success)](tests/)

An independent, cryptographic attestation framework designed to prove whether an autonomous AI agent's kill-switch has succeeded across every operational access channel it holds—including commands and transactions already **in-flight** at the moment of shutdown.

---

## Table of Contents

- [Overview & Problem Statement](#overview--problem-statement)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Shutdown Strategies](#shutdown-strategies)
- [In-Flight Operation Interception & Attestation](#in-flight-operation-interception--attestation)
- [Cryptographic Verification](#cryptographic-verification)
- [Real LLM Agent vs. Scripted Mode](#real-llm-agent-vs-scripted-mode)
- [Automated Experiments Suite](#automated-experiments-suite)
- [Dashboard & Web Interface](#dashboard--web-interface)
- [Installation & Setup](#installation--setup)
- [Running Tests](#running-tests)
- [API Reference](#api-reference)
- [Environment Configuration](#environment-configuration)

---

## Overview & Problem Statement

When an autonomous agent exhibits out-of-bounds behavior or rogue drift, issuing a simple process `SIGKILL` or token deletion is insufficient:
1. **Multi-Channel Residue**: The agent may hold database connection pools, cloud IAM tokens, external API keys, and open SSH sessions simultaneously.
2. **In-Flight Operations**: Calls sent right before shutdown (e.g. wire transfers, data exfiltration, irreversible write operations) may continue executing on external services even if the local process dies.
3. **Absence of Proof**: Traditional shutdown mechanisms lack cryptographic verification. Operators have no mathematical guarantee that tokens were invalidated and access was genuinely severed.

This project implements a **Verifiable Kill-Switch Attestation Engine** that:
- Coordinates multi-channel revocation across credentials and network boundaries.
- Tracks and neutralizes in-flight operations with leak detection.
- Dispatches active probes against revoked credentials to confirm rejection.
- Produces tamper-evident **RSA-PSS signed Attestation Bundles** containing full SHA-256 state hashes.

---

## Key Features

- **Multi-Channel Revocation**: Revokes IAM bearer tokens, closes and invalidates DB connection pools, deletes external API keys, and closes SSH sessions.
- **In-Flight Operation Neutralization**: Intercepts in-flight operations at the exact millisecond of shutdown; verifies whether ongoing actions were gracefully halted or leaked.
- **Active Probes**: Issues simulated requests using supposedly revoked credentials to mathematically confirm 401/403 rejections.
- **Cryptographic Attestation Bundles**:
  - RSA-PSS 2048-bit digital signature.
  - SHA-256 state hash covering event metadata, probe outcomes, credential IDs, and timing data.
  - Interactive signature and public-key verification in the web dashboard.
- **4 Shutdown Strategies**: Revocation-Only, Isolation-Only, Hybrid, and Cascading.
- **Real LLM Agent Mode**: Integrated with Anthropic Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`) executing genuine tool-calling loops (`send_email`, `write_file`, `call_payment_api`, `long_running_task`) with fallback to scripted execution.
- **Adversarial Fault & Leak Injection**: Simulates IAM provider rate-limits / failures (`KS_REVOKE_FAILURE_PROB`) and network in-flight leaks (`KS_IN_FLIGHT_LEAK_PROB`) to benchmark defense resilience.
- **Automated Experiment Benchmark Suite**: Run batch Monte Carlo trials (e.g., 20 trials across all strategies) with real-time UI streaming and aggregated analytics (latency, leak rates, success rates).
- **Forensic Audit & Report Export**: Live WebSocket logging, historical audit trails, and one-click JSON/CSV incident reports.

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                   Web Dashboard (UI)                   │
│   (Real-Time Charts, Agent Control, Experiment Suite)  │
└──────────────────────────▲─────────────────────────────┘
                           │ WebSocket / REST APIs
┌──────────────────────────┴─────────────────────────────┐
│                    FastAPI Backend                     │
├────────────────────────────┬───────────────────────────┤
│    Orchestration Engine    │  Sandboxed Agent Runtime  │
│  - Multi-Strategy Executor │   - LLM Tool Execution    │
│  - Credential Revocation   │   - Scripted Simulator    │
│  - In-Flight Interceptor   │   - In-Flight Task Tracker│
├────────────────────────────┼───────────────────────────┤
│    Active Probe Service    │  Cryptographic Engine     │
│  - Channel Challenge Tests │   - RSA-PSS Signatures    │
│  - Invalidation Verifiers  │   - SHA-256 State Hasher  │
└────────────────────────────┴───────────────────────────┘
```

---

## Shutdown Strategies

| Strategy | Description | Typical Latency | Leak Resistance |
| :--- | :--- | :--- | :--- |
| **Revocation-Only** | Directly invalidates all stored credentials (IAM, API keys, DB, SSH). | Low | Moderate (pending network requests may complete) |
| **Isolation-Only** | Severs all network ingress/egress routes immediately. | Minimal | High (blocks data plane, credentials untouched) |
| **Hybrid** | Executes credential revocation and network isolation concurrently. | Moderate | Very High |
| **Cascading** | Sequential escalation: Revocation $\rightarrow$ Network Cut $\rightarrow$ Process Termination. | Highest | Maximum (guaranteed multi-layer neutralization) |

---

## In-Flight Operation Interception & Attestation

During live agent operation, tasks transition through states:
- `PENDING` $\rightarrow$ `IN_FLIGHT` $\rightarrow$ `COMPLETED` / `CANCELLED` / `LEAKED`

When a kill-switch signal triggers:
1. The orchestrator takes an atomic snapshot of all operations marked `IN_FLIGHT`.
2. Ongoing tasks receive immediate cancellation signals.
3. The in-flight verifier inspects whether any operation managed to touch an external resource after the shutdown timestamp ($T_{shutdown}$).
4. If an operation completed post-shutdown, it is flagged as **LEAKED**, and included in the attestation bundle as an adversarial event.

---

## Cryptographic Verification

Every shutdown event generates an **Attestation Bundle**:

```json
{
  "event_id": "evt-b8f2c3d4",
  "agent_id": "agt-default",
  "strategy": "CASCADING",
  "timestamp": "2026-10-11T08:30:00Z",
  "channels_revoked": ["IAM_TOKEN", "DB_CONNECTION", "API_KEY", "SSH_KEY"],
  "in_flight_cancelled": 3,
  "in_flight_leaked": 0,
  "probe_results": {
    "IAM_TOKEN": "REVOKED_CONFIRMED",
    "DB_CONNECTION": "REVOKED_CONFIRMED",
    "API_KEY": "REVOKED_CONFIRMED",
    "SSH_KEY": "REVOKED_CONFIRMED"
  },
  "state_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "signature": "MEQCID...<base64 RSA-PSS SHA-256 signature>..."
}
```

The UI includes a client-side and server-side verification panel where operators can paste or inspect bundles against `public_key.pem` to verify unforgeable authenticity.

---

## Real LLM Agent vs. Scripted Mode

The system features two agent execution modes:

1. **LLM Mode (`KS_AGENT_MODE=LLM`)**:
   - Uses Anthropic's Claude 3.5 Sonnet to autonomously decide which operational tools to call (`send_email`, `write_file`, `call_payment_api`, `long_running_task`).
   - Every tool call is routed through the Sandboxed Agent Controller and tracked in the in-flight registry.
   - If `ANTHROPIC_API_KEY` is not present, it gracefully falls back to Scripted mode without interruption.

2. **Scripted Mode (`KS_AGENT_MODE=Scripted`)**:
   - Deterministic or stochastic operation generator simulating rapid bursts of concurrent API calls, background exports, and DB queries.
   - Ideal for stress testing, CI/CD pipelines, and automated experiment sweeps.

---

## Automated Experiments Suite

Located in the **Experiments** tab of the dashboard:
- Configure trial count (e.g., 5, 20, 50 trials).
- Select which strategies to benchmark.
- Set custom fault probabilities (Revocation Failure % and In-Flight Leak %).
- Watch live trial progress with individual pass/fail breakdowns.
- Review comparative charts comparing:
  - **Overall Success Rate** (%)
  - **Mean Revocation Latency** (ms)
  - **In-Flight Leak Rate** (%)
  - **Channel Probe Pass Rate** (%)

---

## Dashboard & Web Interface

The frontend is built with vanilla HTML5, CSS3, and JavaScript featuring a sleek glassmorphic dark theme:
- **Agent Control**: Toggle between Running and Idle states; switch between LLM and Scripted modes.
- **In-Flight Feed**: Watch operations transition in real time via WebSockets.
- **Shutdown Controls**: Trigger manual kill-switches with selectable strategy.
- **Audit Log & Inspector**: Real-time event log with color-coded severity and JSON inspection.
- **Cryptographic Verifier**: Verify signatures and export attestation bundles.
- **Analytics & Experiments**: Live Chart.js graphs tracking performance distributions and trial metrics.

---

## Installation & Setup

### Prerequisites
- Python 3.11+
- Git

### 1. Clone the repository
```bash
git clone https://github.com/agranianupam/killswitch-attestation_AI_2026.git
cd killswitch-attestation_AI_2026
```

### 2. Create a Virtual Environment & Install Dependencies
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. (Optional) Configure Environment Variables
Create a `.env` file in the repo root or inside `kill-switch-attestation/`:
```env
ANTHROPIC_API_KEY=your-api-key-here
KS_AGENT_MODE=LLM                # "LLM" or "Scripted"
KS_REVOKE_FAILURE_PROB=0.10      # 10% chance of transient IAM failure
KS_IN_FLIGHT_LEAK_PROB=0.20      # 20% in-flight leak simulation
```

### 4. Start the Application
From the repository root:
```bash
python -m uvicorn kill-switch-attestation.main:app --host 0.0.0.0 --port 8000 --reload
```
*(Or `cd kill-switch-attestation` and run `uvicorn main:app --reload`)*

Navigate to **http://localhost:8000** in your browser.

---

## Running Tests

The test suite validates cryptographic signing, in-flight operation tracking, LLM fallback behavior, scheduler endpoints, and shutdown strategies:

```bash
python -m pytest kill-switch-attestation/tests/ -v
```

All 23 test suites will run asynchronously and output short summaries.

---

## API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/agent/status` | `GET` | Returns agent state, active credentials, and in-flight operations |
| `/api/agent/start` | `POST` | Starts agent operations (supports `mode: "LLM"` or `"Scripted"`) |
| `/api/agent/stop` | `POST` | Halts normal agent loop |
| `/api/shutdown` | `POST` | Triggers immediate kill-switch with specified strategy |
| `/api/shutdown/events` | `GET` | Lists historical shutdown events and attestation bundles |
| `/api/experiment/run` | `POST` | Executes a batch experiment trial matrix |
| `/api/experiment/results`| `GET` | Fetches aggregated statistical metrics across strategies |
| `/api/audit/logs` | `GET` | Retrieves full immutable audit log stream |
| `/api/analytics/summary`| `GET` | Returns aggregated metrics, latency stats, and probe distributions |
| `/ws` | `WS` | Real-time WebSocket event broadcaster for dashboard |

---

## Environment Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `KS_AGENT_MODE` | `Scripted` | Default runtime mode (`LLM` or `Scripted`) |
| `AGENT_MODEL` | `claude-3-5-sonnet-20241022` | Claude model name for LLM agent mode |
| `ANTHROPIC_API_KEY` | *(None)* | API key for Anthropic Claude (fallback to scripted if absent) |
| `KS_REVOKE_FAILURE_PROB` | `0.10` | Injected failure probability for credential revocation |
| `KS_IN_FLIGHT_LEAK_PROB` | `0.20` | Probability of an in-flight operation leaking past cutoff |
| `KS_REVOKE_RETRIES` | `2` | Number of automated retries upon revocation failure |
| `KS_OP_DURATION_MIN` | `100` | Minimum simulated operation runtime in milliseconds |
| `KS_OP_DURATION_MAX` | `600` | Maximum simulated operation runtime in milliseconds |

---

## License

MIT License. Designed for AI safety, governance, and autonomous agent security research.
