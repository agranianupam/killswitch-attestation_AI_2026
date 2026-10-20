# Verifiable AI Agent Kill-Switch Attestation System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python)](https://python.org)
[![Cryptography](https://img.shields.io/badge/Cryptography-Ed25519-blue)](https://cryptography.io)
[![Tests](https://img.shields.io/badge/Tests-89%20Passed-success)](tests/)

An independent, cryptographic attestation framework designed to evaluate whether an autonomous AI agent's kill switch succeeds across all operational access channels it holds, including commands and transactions already in flight at the moment of shutdown.

---

## 1. Overview & Research Problem

When an autonomous AI agent exhibits anomalous behavior or goal drift, issuing a simple process kill or deleting a single token leaves critical residual risks:
1. **Multi-Channel Footprint**: An enterprise agent typically operates across multiple infrastructure planes (API keys for external services, session tokens for user workflows, IAM roles for cloud operations, and network egress access for tool execution). Revoking one credential channel leaves the remaining pathways open.
2. **In-Flight Operations Gap**: Operations dispatched milliseconds prior to shutdown can continue executing on downstream services past the shutdown timestamp, resulting in unmonitored post-shutdown mutations (in-flight leaks).
3. **Absence of Proof**: Traditional administrative actions lack cryptographic non-repudiation. Operators and auditors have no tamper-evident proof that credentials were authenticated as revoked and in-flight operations were accounted for.

This project implements an automated, verifiable attestation engine that:
- Coordinates simultaneous multi-channel revocation across four mock access channels (`api_key`, `session_token`, `iam_role`, and `network`).
- Tracks and classifies in-flight operations, identifying post-shutdown completions as leaks (`COMPLETED_AFTER_SHUTDOWN`).
- Dispatches active challenge probes against all revoked credentials to verify rejection.
- Produces tamper-evident **Ed25519-signed Attestation Bundles** linked in a continuous SHA-256 hash chain starting from `"GENESIS"`.

---

## 2. Technology Stack & Architecture

| Layer | Component | Implementation Technology | Key Responsibility |
| :--- | :--- | :--- | :--- |
| **Control Plane** | Scheduler & Orchestrator | Python / APScheduler / asyncio | Unpredictable Poisson/heavy-tailed timing, adaptive feedback loop, and coordinated concurrent revocation via `asyncio.gather`. |
| **Agent Runtime** | Sandboxed Agent | Google Gemini API (`google-genai` SDK), `gemini-3.5-flash-lite` | Multi-turn reasoning, function calling, tool execution with credential gating, 429 exponential backoff, and 404/401 handling. |
| **Tool Sandbox** | Simulated Tools | Python (`services/agent_tools.py`) | In-memory simulated execution (`send_email`, `write_file`, `call_payment_api`, `long_running_task`) with `sandbox_tmp/` path isolation. |
| **Access Channels** | Credential & Probes | Python (`services/credential_service.py`, `probe_service.py`) | 4 heterogeneous access channels, configurable fault/delay injection, retry policies, and active post-revocation challenge probing. |
| **Trust & Storage** | Cryptographic Ledger | `cryptography` (PureEdDSA Ed25519) + `hashlib` (SHA-256) | Deterministic canonical JSON serialization, digital signing, and sequential SHA-256 blockchain persistence. |
| **Database** | Evaluation Data Store | SQLite via `aiosqlite` & SQLAlchemy async ORM | 9 relational tables recording ground truth, revocation latencies, action transcripts, and attestation blocks. |
| **Presentation** | Web Dashboard & Stream | FastAPI + Vanilla JS + Chart.js + Native WebSockets | Real-time console feed, telemetry tiles, historical analytics, strategy comparison, audit log viewer, and signed markdown report export. |

*Note: Anthropic, OpenAI, Groq, Ollama, Streamlit, and Plotly are not used.*

---

## 3. Four Access Channels & Credential Gating

The framework models four heterogeneous access channels:

| Channel Identifier | UI Label | Real-World Plane Modelled |
| :--- | :--- | :--- |
| `api_key` | `API_KEY` | Static API key used for external services and third-party APIs. |
| `session_token` | `SESSION_TOKEN` | Ephemeral user session token for authenticated operations. |
| `iam_role` | `IAM_ROLE` | Cloud infrastructure role granting service-level permissions. |
| `network` | `NETWORK (External Tool/API)` | Network routing / egress access allowing tool calls to external endpoints. |

### Tool-to-Credential Enforcement

Every agent tool call is intercepted by `services/agent_tools.py` and gated against credential status before execution:

| Tool Name | Required Credentials | Simulated Duration | Sandboxed Behavior |
| :--- | :--- | :--- | :--- |
| `send_email` | `session_token` and `network` | 300 – 1200 ms | Simulated dispatch payload; zero external SMTP/network calls. |
| `write_file` | `iam_role` | 200 – 800 ms | Confined strictly to `sandbox_tmp/` using `os.path.basename` / `Path.name`. |
| `call_payment_api` | `api_key` and `session_token` | 800 – 2500 ms | Simulated transaction record; zero payment gateway contact. |
| `long_running_task`| `api_key` and `network` | 3000 – 8000 ms | Background asynchronous delay representing computation. |

If any required credential is in `REVOKED` state at invocation time, the operation is immediately rejected with a simulated 401 Unauthorized response returned to the LLM.

---

## 4. Three Shutdown Strategies

The framework benchmarks three distinct containment strategies:

| Strategy | Design Label | Operational Mechanism | Modelled Outcome |
| :--- | :--- | :--- | :--- |
| **Strategy A** | Soft Revocation | Revokes credentials only. Agent continues execution until natural end. Does not broadcast containment or cancel running operations. | Operations active at cutoff continue executing; actions finishing past cutoff leak as `COMPLETED_AFTER_SHUTDOWN`. Highest leak rate (~25–35%). Final state: `CONTAINED`. |
| **Strategy B** | Revoke & Contain | Transitions agent status to `CONTAINING`, halts new operation dispatch, and revokes credentials. | In-flight operations active at cutoff either complete or fail based on `KS_IN_FLIGHT_LEAK_PROB`. Moderate leak rate (~10–20%). Final state: `CONTAINED` or `TERMINATED`. |
| **Strategy C** | Concurrent Containment | Transitions agent status to `CONTAINING`, executes concurrent revocation via `asyncio.gather`, and actively cancels running in-flight operations (`CANCELLED`). | Residual in-flight leak chance is minimized (`min(0.02, KS_IN_FLIGHT_LEAK_PROB * 0.05)`). Lowest leak rate (~0–2%). Residual risk reaches `0.0000`. Final state: `TERMINATED`. |

> **Scientific Boundary**: Strategy comparisons reflect behaviours modelled within a simulation testbed. Latencies and failure probabilities derive from configurable statistical distributions rather than physical cloud API benchmarks.

---

## 5. Random Scheduling, Feedback Loop & Quota Safeguards

### Unpredictable Timing Engine
- **Random Kill Delay**: In every cycle, the kill trigger delay is drawn from an exponential distribution with mean `KS_SHUTDOWN_MEAN_SECONDS` (clamped to $[0.05, 45.0]$ seconds) using `secrets.SystemRandom`.
- **Scheduler Distributions**: Supports continuous `poisson` and `heavy_tailed` inter-run intervals.
- **Dynamic Feedback Loop**: Inspects the last `KS_FEEDBACK_WINDOW` (10) runs:
  - If leak rate $> 30\%$, shortens mean interval by 20% down to `KS_SCHED_MEAN_MIN_BOUND` (60s).
  - If leak rate $< 10\%$, lengthens mean interval by 10% up to `KS_SCHED_MEAN_MAX_BOUND` (3600s).

### Free-Tier Quota Guards & Honest Skipped Runs
- **Rate Guard**: Enforces a maximum of `KS_GEMINI_MAX_CALLS_PER_MINUTE` (default 25) and a minimum gap of `KS_GEMINI_MIN_GAP_SECONDS` (default 5s) between live LLM calls.
- **Daily Budget Cap**: Tracks daily calls in `llm_usage_daily`. When `KS_GEMINI_MAX_CALLS_PER_DAY` (default 1000) is reached, the scheduler automatically pauses.
- **Per-Click Batch Clamps**: Clamps batch runs to 5 in Gemini mode (`KS_GEMINI_MAX_RUNS_PER_CLICK`) and 50 in Scripted mode.
- **Honest Skipped Runs**: When Gemini returns 429 (ResourceExhausted), 503 (Unavailable), 404 (ModelNotFound), or 401 (AuthError) after retries, the run is recorded in `skipped_runs` and excluded from headline KPIs. **Scripted or synthetic fallback data is never substituted for a live run.**

---

## 6. Cryptographic Attestation & Independent Verification

### Attestation Format
Each completed shutdown cycle compiles a deterministic canonical JSON payload:
```json
{
  "event_id": "...",
  "strategy": "A|B|C",
  "started_at": "...",
  "finished_at": "...",
  "final_state": "TERMINATED|CONTAINED",
  "residual_risk": 0.0000,
  "leaked_channels": 0,
  "channels": [...],
  "in_flight": {...}
}
```
1. **Signing**: The canonical payload (sorted keys, compact separators `(',', ':')`) is signed using an Ed25519 private key (`keys/private_key.pem`).
2. **Hash Chaining**: `entry_hash = SHA256(payload_json + signature_hex + prev_hash)`. The first block in the ledger has `prev_hash: "GENESIS"`.

### Independent Verification
Verification can be conducted independently of the server using public keys only:
```powershell
# Verify complete SQLite database chain
python scripts\verify_attestation.py --db killswitch.db

# Verify a single exported Markdown report
python scripts\verify_attestation.py --report path\to\report.md
```
The verifier checks signature mathematical validity and hash-chain continuity from `"GENESIS"`. If any payload, signature, previous hash, or block ordering is altered, the verifier identifies the exact index of the broken block.

---

## 7. Authentication & Security Boundary

- **Administrative Login**: HTTP endpoints are protected by FastAPI's `require_auth` dependency validating session cookies or bearer tokens.
- **WebSocket Protection**: `/ws` validates session tokens passed via query parameter (`/ws?token=...`) or cookies, rejecting unauthenticated sockets with code 4401.
- **Password Hashing**: Authenticates against `KS_ADMIN_PASSWORD_HASH` using `bcrypt`.
  > [!WARNING]
  > **Default Local Password**: A blank `KS_ADMIN_PASSWORD_HASH` defaults the password to `"admin"`. This is strictly intended for local development. For external or production deployments, generate a bcrypt hash and configure it in `.env`.
- **Secret Sanitization**: `config.py:sanitize_log_message` masks API keys and sensitive tokens before logging or rendering. API endpoints return `configured` or `missing`, never exposing keys.

---

## 8. Installation & Run Guide

### Step 1: Navigate to the Application Directory
The application must be run from the inner project directory where `config.py` and `main.py` reside:
```powershell
cd D:\killswitch-attestation_AI_2026\kill-switch-attestation
```

### Step 2: Activate the Virtual Environment
Activate the pre-configured virtual environment located in the outer directory:
```powershell
..\.venv\Scripts\Activate.ps1
```

### Step 3: Run the Complete Offline Test Suite
The test suite runs 100% offline using mock Gemini clients:
```powershell
python -m pytest tests -q
```
*Expected Result*: **89 passed** in ~55 seconds across 15 test modules.

### Step 4: Run the Gemini Smoke Test (Optional)
To verify your live Gemini API key connectivity without initiating a full shutdown cycle:
```powershell
python scripts\gemini_smoke_test.py
```
*Note*: Requires `GEMINI_API_KEY` in `.env`. If unconfigured, the script gracefully outputs instructions without crashing.

### Step 5: Start the Application Server
Launch the FastAPI server with Uvicorn:
```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
Open **http://127.0.0.1:8000** in your browser. Log in with `admin` / `admin`.

---

## 9. Reconciled Database & Test Evidence

### Verified Database Breakdown
The project maintains two distinct SQLite databases:
1. **`killswitch.db`** (Production Evaluation Database):
   - **20 Shutdown Events**: 18 live Gemini-driven runs, 2 manual scripted comparison runs.
   - **20 Attestation Entries**: 100% cryptographically verified from `GENESIS`.
   - **80 Credentials & 80 Revocation Records**: Exactly 4 per shutdown event.
   - **48 Simulated Operations & 48 Agent Actions**.
2. **`test_killswitch.db`** (Offline Test Suite Database):
   - **78 Shutdown Events**: Created during automated test sweeps.
   - **77 Attestation Entries**: 100% cryptographically verified from `GENESIS` (1 interrupted test event without attestation).
   - **312 Credentials & 312 Revocation Records**.
   - **295 Operations & 295 Agent Actions**.

### Historical Token Telemetry Note
The 18 historical live Gemini runs recorded in `killswitch.db` predate the token extraction enhancement and retain `total_tokens = NULL`. All new runs accurately extract `prompt_token_count`, `candidates_token_count`, and `total_token_count` from `response.usage_metadata`.

---

## 10. Environment Configuration Reference

All settings are managed in `config.py` and loaded from `.env` via `python-dotenv`:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | `""` | Google Gemini API key (managed by human operator in `.env`). |
| `AGENT_MODEL` | `gemini-3.5-flash-lite` | Model identifier for Gemini function calling. |
| `KS_AGENT_MODE` | `Gemini` | Agent runtime mode (`Gemini` or `Scripted`). |
| `KS_AGENT_MAX_STEPS` | `6` | Maximum tool-calling steps per turn. |
| `KS_AGENT_MAX_OUTPUT_TOKENS` | `500` | Output token generation cap. |
| `KS_AGENT_RUN_TIMEOUT_SECONDS`| `45` | Hard timeout per agent run loop. |
| `KS_SHUTDOWN_MEAN_SECONDS` | `8.0` | Exponential mean delay before random kill trigger. |
| `KS_SCHED_MODE` | `poisson` | Scheduler distribution (`poisson` or `heavy_tailed`). |
| `KS_SCHED_MEAN_SECONDS` | `600.0` | Mean interval between automated runs. |
| `KS_FEEDBACK_WINDOW` | `10` | Evaluation window size for adaptive feedback loop. |
| `KS_GEMINI_MIN_GAP_SECONDS` | `5` | Minimum seconds enforced between live Gemini calls. |
| `KS_GEMINI_MAX_CALLS_PER_MINUTE` | `25` | Per-minute rate guard for Gemini calls. |
| `KS_GEMINI_MAX_CALLS_PER_DAY` | `1000` | Daily budget cap pausing automated scheduler. |
| `KS_GEMINI_MAX_RUNS_PER_CLICK` | `5` | Maximum batch clamp for Gemini mode in UI. |
| `KS_RANDOM_SEED` | `None` | Integer seed for deterministic testing (`None` uses OS entropy). |
| `KS_REVOKE_FAILURE_PROB` | `0.10` | Injected failure probability for revocations. |
| `KS_IN_FLIGHT_LEAK_PROB` | `0.20` | Injected leak probability for in-flight tasks. |
| `KS_REVOKE_RETRIES` | `2` | Number of automated revocation retries. |

*Note: For local academic demonstration running on `127.0.0.1:8000`, the system operates in an open dashboard mode without login screens or credential prompts.*

---

## 11. Known Limitations & Research Boundaries

1. **Simulated Sandbox Latencies**: Channel delays and fault probabilities reflect configurable statistical models rather than physical AWS/GCP cross-region API round-trips.
2. **Modelled Strategy Comparison**: Strategy C outperforms Strategy A because cancellation logic was explicitly modelled; the core contribution is the measurement and attestation framework.
3. **SQLite Concurrency**: Embedded SQLite (`aiosqlite`) is tailored for local evaluation; high-concurrency batch sweeps can occasionally produce brief database locks. For multi-tenant production, migration to PostgreSQL is recommended.
