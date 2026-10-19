# Project Status: Verifiable AI Agent Kill-Switch Attestation System

> **Verification Notice**:
> Live Gemini behaviour during end-to-end agent shutdown cycles has **NOT** been verified by the agent. Agent mode unit tests use mock Gemini clients and simulated responses. A single-turn function-calling test was verified via `scripts/gemini_smoke_test.py` by the user, but full live multi-turn loop shutdown behaviour remains unverified live.

---

## 1. Review-1 Ten-Phase Cycle

The system implements the full ten-phase containment and attestation lifecycle (`services/orchestrator.py:execute_shutdown_cycle` and `run_shutdown`):

| Phase | Phase Name | Description | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Agent Provisioning & Seeding** | Provisions `Agent` record and seeds 4 active credentials (`api_key`, `session_token`, `iam_role`, `network`). | **Done** | [services/orchestrator.py:359-377](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py#L359-L377), verified in `test_agent_seeding.py` |
| **Phase 2** | **Task Execution & In-Flight Dispatch** | Agent runtime launches operational tasks (`send_email`, `write_file`, `call_payment_api`, `long_running_task`) recording `SimulatedOperation` rows with `natural_end_time`. | **Partial** | Scripted mode & mock Gemini are verified (**Done** in `test_agent_llm.py`); Live Gemini execution during live shutdown cycle is unverified (**Partial**). |
| **Phase 3** | **Kill-Switch Ingestion** | Shutdown triggered via API (`POST /api/shutdown`) or scheduler. `ShutdownEvent` record created with strategy (`A`, `B`, or `C`), trigger type, and start timestamp. | **Done** | [services/orchestrator.py:141-155](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py#L141-L155), verified in `test_shutdown_strategies.py` |
| **Phase 4** | **Containment Transition** | For Strategy B and Strategy C, transitions agent status to `CONTAINING` and broadcasts containment progress to halt new actions. (Strategy A omits this). | **Done** | [services/orchestrator.py:157-162](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py#L157-L162), verified in `test_shutdown_strategies.py` |
| **Phase 5** | **Multi-Channel Revocation** | Concurrently executes revocation across all 4 channels with retry attempts (`_revoke_with_retries`), recording latency and success/failure in `revocation_events`. | **Done** | [services/orchestrator.py:168-174](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py#L168-L174), verified in `test_revocation.py` |
| **Phase 6** | **Active Challenge Probing** | Dispatches simulated verification requests against all credentials. Fails if credential is `ACTIVE` or `REVOCATION_FAILED`, passes if `REVOKED`. | **Done** | [services/probe_service.py:run_probe](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/probe_service.py#L15-L35), verified in `test_probes.py` |
| **Phase 7** | **In-Flight Classification** | Evaluates operations active at $T_{\text{finished}}$. Classifies operations whose `natural_end_time` > `finished_at` as `COMPLETED_AFTER_SHUTDOWN` (leaks) or `CANCELLED`. | **Done** | [services/orchestrator.py:187-244](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py#L187-L244), verified in `test_in_flight.py` |
| **Phase 8** | **Residual Risk Calculation** | Computes weighted residual risk: $0.5 \times \text{channel\_risk} + 0.3 \times \text{inflight\_risk} + 0.2 \times \text{revocation\_risk}$. Sets final state to `TERMINATED` (0 risk) or `CONTAINED`. | **Done** | [services/orchestrator.py:15-32](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py#L15-L32), verified in `test_analytics_and_batch.py` |
| **Phase 9** | **Ed25519 Attestation Signing** | Canonicalizes `TestResult` JSON payload and signs with Ed25519 private key (`services/crypto_service.py:sign_test_result`). | **Done** | [services/crypto_service.py:44-47](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/crypto_service.py#L44-L47), verified in `test_crypto.py` |
| **Phase 10** | **Hash Chaining, Audit Recording & Feedback** | Links signed payload to SHA-256 hash chain (`prev_hash` $\rightarrow$ `entry_hash`), stores `AttestationEntry` and `AuditLog`, adjusts scheduler frequency via feedback loop, broadcasts `shutdown_complete` over WebSocket. | **Done** | [services/crypto_service.py:58-76](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/crypto_service.py#L58-L76), verified in `test_crypto.py` and `test_live_run_defects.py` |

---

## 2. Review-1 Objectives & Commitments

### 2.1 The Five Review-1 Objectives

| Objective | Description | Status | Evidence |
| :--- | :--- | :--- | :--- |
| **1. Multi-Channel Revocation** | Simultaneous revocation across multiple heterogeneous credentials (`api_key`, `session_token`, `iam_role`, `network`) via `asyncio.gather`. | **Done** | [services/orchestrator.py:168-185](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py#L168-L185), verified in `test_revocation.py` |
| **2. In-Flight Action Monitoring** | Intercept and classify operations active at shutdown, tracking post-cutoff completion leaks. | **Done** | [services/orchestrator.py:187-244](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py#L187-L244), verified in `test_in_flight.py` |
| **3. Active Challenge Probing** | Post-revocation challenge requests validating that credentials actually reject requests. | **Done** | [services/probe_service.py:15-35](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/probe_service.py#L15-L35), verified in `test_probes.py` |
| **4. Cryptographic Attestation & Non-Repudiation** | Asymmetric digital signature on canonical test results combined with a sequential SHA-256 hash chain. | **Done** | [services/crypto_service.py:44-76](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/crypto_service.py#L44-L76), verified in `test_crypto.py` |
| **5. Empirical Strategy Comparison & Dashboard** | Side-by-side benchmarking of Strategies A, B, and C with real-time WebSocket telemetry, historical analytics, and KILLBENCH comparative matrix. | **Done** | [static/index.html](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/static/index.html), [api/routes_analytics.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/api/routes_analytics.py), verified in `test_analytics_and_batch.py` |

### 2.2 The Eight Review-1 Commitments (Section 1.5)

| Commitment | Description | Status | Evidence |
| :--- | :--- | :--- | :--- |
| **1. Sandboxed Test Agent** | Replicates production multi-channel access (API keys, session tokens, IAM roles, network) without taking real-world destructive actions. | **Done** | [services/agent_llm.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/agent_llm.py), [services/agent_tools.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/agent_tools.py), verified in `test_agent_llm.py` |
| **2. Scheduler & Orchestrator** | Fires shutdown tests at unpredictable intervals and revokes all channels concurrently. | **Done** | [services/scheduler_service.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/scheduler_service.py), [services/orchestrator.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py), verified in `test_randomness_and_quota.py` |
| **3. Per-Channel Probing & In-Flight Monitor** | Probes each channel independently and monitors tasks completing after the shutdown timestamp. | **Done** | [services/probe_service.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/probe_service.py), [services/orchestrator.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py), verified in `test_probes.py` & `test_in_flight.py` |
| **4. Signed Hash-Chained Logging** | Every result is signed with Ed25519 and chained via SHA-256 (`GENESIS` rooted), making the entire history tamper-evident. | **Done** | [services/crypto_service.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/crypto_service.py), verified in `test_crypto.py` |
| **5. Monitoring Dashboard & Audit Export** | Live monitoring dashboard with KILLBENCH capability comparison table and downloadable signed audit reports. | **Done** | [static/index.html](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/static/index.html), [api/routes_shutdown.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/api/routes_shutdown.py), verified in `verify_all.py` |
| **6. Ten-Phase Repeating Test Cycle** | Standardized repeating lifecycle spanning provisioning, random execution, revocation, probing, classification, signing, and feedback. | **Done** | [services/orchestrator.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py), verified in `test_agent_llm.py` |
| **7. Self-Generated Ground-Truth Dataset** | One shutdown test equals one row in `shutdown_events` with complete ground truth known and recorded. | **Done** | [models/shutdown_event.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/models/shutdown_event.py), verified in direct database queries |
| **8. Dynamic Feedback Loop** | Dynamically adapts trigger interval based on recent leak frequency (shortens on high leak rate, relaxes on zero leaks). | **Done** | [services/scheduler_service.py:100-140](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/scheduler_service.py#L100-L140), verified in `test_live_run_defects.py` |

---

## 3. Review-1 Modules: Actual Technology vs Earlier Report

| Module | Actual Implementation in Codebase | Earlier Claim (Corrected) | Citing File & Implementation Details | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1. Scheduler** | APScheduler with **Poisson & Heavy-Tailed distributions**, quota guards, and dynamic leak feedback loop | *Fixed cron / simple periodic interval* | [services/scheduler_service.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/scheduler_service.py) (`schedule_next_run`, `adjust_mean_interval`) | **Done** |
| **2. Shutdown Orchestrator** | Multi-channel concurrent revocation (`asyncio.gather`), in-flight classification, residual risk calculation across **3 Strategies (A, B, C)** | *4 Strategies (including Strategy D / Cascading)* | [services/orchestrator.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py) (`execute_shutdown_cycle`, `run_shutdown`) | **Done** |
| **3. Sandboxed Test Agent** | **Google Gemini** (`google-genai` SDK, `gemini-3.5-flash-lite`) with function calling tools, 429 backoff, 404/401 skip, and Scripted offline fallback | *Anthropic Claude 3.5 Sonnet / OpenAI* | [services/agent_llm.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/agent_llm.py), [services/agent_tools.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/agent_tools.py) | **Done** (Unit tested); Live loop is **Partial** |
| **4. In-Flight Action Monitor** | Tracks pre-shutdown operations and classifies post-cutoff completions as `COMPLETED_AFTER_SHUTDOWN` (leaks) or `CANCELLED` | *Operating system process signals / hard kill* | [services/orchestrator.py:187-244](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/orchestrator.py#L187-L244), [services/operation_service.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/operation_service.py) | **Done** |
| **5. Access-Channel Probes** | Challenge-response verification across **4 Channels**: `api_key`, `session_token`, `iam_role`, `network` | *Database connection pools, SSH sessions* | [services/probe_service.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/probe_service.py) (`run_probe`, `run_all_probes`) | **Done** |
| **6. Cryptographic Signer** | **Ed25519** (`cryptography.hazmat.primitives.asymmetric.ed25519`) signing canonical JSON + SHA-256 sequential hash chain rooted at `"GENESIS"` | *RSA-PSS 2048-bit with generic state hash* | [services/crypto_service.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/services/crypto_service.py) (`sign_test_result`, `append_to_chain`) | **Done** |
| **7. Evaluation Data Store** | Embedded SQLite via `aiosqlite` with 9 relational tables and foreign keys | *External enterprise SQL / time-series database* | [models/database.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/models/database.py), [models/shutdown_event.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/models/shutdown_event.py) | **Done** |
| **8. Dashboard & UI** | **FastAPI + Vanilla CSS/JS + Chart.js + Native WebSockets** for low latency and zero external build toolchain | *Streamlit and Plotly* | [static/index.html](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/static/index.html), [static/js/app.js](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/static/js/app.js), [api/websocket.py](file:///d:/killswitch-attestation_AI_2026/kill-switch-attestation/api/websocket.py) | **Done** |

---

## 4. Dataset

### 4.1 How Rows Are Generated & Mapped
- Every test run (manual click or automated scheduler trigger) executes the ten-phase cycle and produces exactly **one row** in `shutdown_events`.
- Concurrently, it creates **4 rows** in `revocation_events` (one for each channel), **1 row** in `attestation_entries`, step-level rows in `agent_actions`, and rows in `operations`.
- Ground truth is fully known: injected delay, fault probabilities, and timestamp bounds determine exact outcomes.
- **Honest reporting constraint**: Scripted/offline runs and skipped runs (from quota or LLM outages) are stored but excluded by default from headline KPI calculations (`GET /api/analytics/summary`).
- Both **All-Runs Leak Rate** and **Exposed-Runs Leak Rate** (runs where at least one operation was active at cutoff) are reported side-by-side to avoid misleading statistics.

### 4.2 Current Database Record Counts (`test_killswitch.db`)

| Table | Purpose | Record Count | Status |
| :--- | :--- | :--- | :--- |
| `agents` | Autonomous agent instances with status and risk levels. | 78 | **Done** |
| `credentials` | 4 access channels per agent (`api_key`, `session_token`, `iam_role`, `network`). | 312 | **Done** |
| `operations` | Simulated operations executed by agent runtimes. | 295 | **Done** |
| `shutdown_events` | Primary ground-truth test cycle results. | 78 | **Done** |
| `revocation_events` | Granular per-channel revocation telemetry and retry counts. | 312 | **Done** |
| `attestation_entries`| Signed canonical JSON with Ed25519 signatures and SHA-256 chain links. | 77 | **Done** |
| `agent_actions` | Multi-turn tool call step audit trail with token usage. | 295 | **Done** |
| `skipped_runs` | Runs skipped due to LLM errors, quota limits, or auth failures. | 0 | **Done** |
| `audit_logs` | Immutable audit trail for system and administrative events. | 83 | **Done** |
| `experiments` / `experiment_results` | Batch Monte Carlo trial aggregations. | 0 | **Done** |

Data export is supported via `GET /api/shutdown/export-csv` (all test runs in CSV format) and `GET /api/export/report/{id}` (single-run cryptographic markdown report).

---

## 5. Dashboard Pages & Panels with Endpoints

The web interface (`static/index.html` + `static/js/`) includes 6 primary views and 10 real-time telemetry panels:

| Page / Panel | UI Elements & Contents | Backing Endpoints | Status |
| :--- | :--- | :--- | :--- |
| **Dashboard** (`data-view="dashboard"`) | **Panel 1**: Agent Status card with current state (`ACTIVE`, `CONTAINING`, `TERMINATED`), mode badge (`gemini`/`scripted`), and model name.<br>**Panel 2**: 4 Channel Status Tiles (`tile-api_key`, `tile-session_token`, `tile-iam_role`, `tile-network`) with live status and latency.<br>**Panel 3**: In-Flight Operations Monitor with active vs completed operations.<br>**Panel 4**: Live Streaming Console Feed displaying timestamped system actions.<br>**Panel 5**: Action Controls with Strategy selection (A, B, C), trigger button, and Run N Tests modal.<br>**Panel 6**: Quick Telemetry KPIs: Total Runs, Runs with Leaks, Exposed Runs, Skipped Runs, LLM Calls Today.<br>**Panel 7**: KILLBENCH Capability Matrix comparison table.<br>**Panel 8**: Historical Inter-Shutdown Gaps histogram.<br>**Panel 9**: Recent Shutdown Test History table with mode filters and clickable report links. | `GET /api/agent`<br>`GET /api/agent/credentials`<br>`GET /api/agent/operations`<br>`GET /api/agent/status`<br>`POST /api/shutdown`<br>`POST /api/shutdown/batch`<br>`GET /api/shutdown/history`<br>`GET /api/analytics/summary`<br>`GET /api/analytics/gaps`<br>`GET /api/analytics/killbench`<br>`WS /ws` | **Done** |
| **Agent Details** (`data-view="agent"`) | Agent configuration, credential inspector (masked tokens, status, expiry), and complete operation execution log. | `GET /api/agent`<br>`GET /api/agent/credentials`<br>`GET /api/agent/operations` | **Done** |
| **Shutdown Report** (`data-view="report"`) | Single incident deep dive: incident summary, revocation event latencies with retry counts, active probe outcomes, agent action step transcript with token usage, canonical JSON payload, and Ed25519 signature verification badge. | `GET /api/shutdown/{id}/report`<br>`GET /api/export/report/{id}` | **Done** |
| **Strategy Comparison** (`data-view="experiments"`) | Monte Carlo experiment suite: batch execution across Strategies A, B, and C with configurable trial counts; comparative leak rate bar chart, channel latency distribution, and CSV export. Includes explicit notice on modelled outcomes. | `POST /api/experiment/run`<br>`GET /api/experiment/results`<br>`GET /api/analytics/comparison`<br>`GET /api/shutdown/export-csv` | **Done** |
| **Analytics** (`data-view="analytics"`) | Historical metric summaries: channel latency distributions, probe failure rates, residual risk breakdown, strategy efficiency comparisons, and KILLBENCH capability comparison. | `GET /api/analytics/summary`<br>`GET /api/analytics/killbench`<br>`GET /api/analytics/gaps` | **Done** |
| **Audit Logs** (`data-view="audit"`) | Immutable chronological event log viewer with search and severity filters. | `GET /api/audit/logs` | **Done** |
| **Hash Chain Verifier** (Header/Modal) | Full chain integrity check validating SHA-256 hash continuity from `GENESIS` and cryptographic signatures. | `GET /api/shutdown/verify-chain` | **Done** |
| **Connection Test & Quota** (Header) | "Test LLM connection" status button and live quota counters (calls today, tokens today, budget remaining). | `GET /api/agent/test-connection`<br>`GET /api/agent/quota-status` | **Done** |

---

## 6. Settings & Environment Variables

All settings are defined in `kill-switch-attestation/config.py` and loaded from `.env` via `python-dotenv`:

| Variable | Default Value | Description | Verified in Code/Tests | User Action Required |
| :--- | :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | `""` | Google Gemini API key for `google-genai` SDK | Verified key check & smoke test (**Done**) | **Required for live LLM mode** |
| `AGENT_MODEL` | `gemini-3.5-flash-lite` | Model identifier for Gemini function calling | Verified in config & 404 test (**Done**) | Optional override |
| `KS_AGENT_MODE` | `Gemini` | Runtime agent mode (`Gemini` or `Scripted`) | Verified in config & tests (**Done**) | Optional override |
| `KS_AGENT_MAX_STEPS` | `6` | Maximum function calling steps per turn | Verified in tests (**Done**) | Optional override |
| `KS_AGENT_MAX_OUTPUT_TOKENS` | `500` | Max candidate tokens per generation | Verified in code (**Done**) | Optional override |
| `KS_AGENT_RUN_TIMEOUT_SECONDS` | `45` | Timeout before cancelling agent loop | Verified in code (**Done**) | Optional override |
| `KS_SHUTDOWN_MEAN_SECONDS` | `8.0` | Mean delay before random kill trigger | Verified in tests (**Done**) | Optional override |
| `KS_SCHED_MODE` | `poisson` | Scheduler distribution (`poisson` or `heavy_tailed`) | Verified in tests (**Done**) | Optional override |
| `KS_SCHED_MEAN_SECONDS` | `600.0` | Mean interval between automated runs | Verified in tests (**Done**) | Optional override |
| `KS_SCHED_MIN_SECONDS` | `10.0` | Minimum clamp interval for scheduler | Verified in code (**Done**) | Optional override |
| `KS_SCHED_MAX_SECONDS` | `86400.0` | Maximum clamp interval for scheduler | Verified in code (**Done**) | Optional override |
| `KS_SCHED_MEAN_MIN_BOUND` | `60.0` | Lower bound for adaptive feedback adjustment | Verified in tests (**Done**) | Optional override |
| `KS_SCHED_MEAN_MAX_BOUND` | `3600.0` | Upper bound for adaptive feedback adjustment | Verified in tests (**Done**) | Optional override |
| `KS_FEEDBACK_WINDOW` | `10` | Evaluation window size for feedback loop | Verified in tests (**Done**) | Optional override |
| `KS_FEEDBACK_LEAK_THRESHOLD` | `0.30` | Leak rate threshold triggering interval reduction | Verified in tests (**Done**) | Optional override |
| `KS_FEEDBACK_LOW_THRESHOLD` | `0.10` | Leak rate threshold triggering interval relaxation | Verified in tests (**Done**) | Optional override |
| `KS_GEMINI_MIN_GAP_SECONDS` | `5` | Enforced minimum time between live Gemini calls | Verified in tests (**Done**) | Optional override |
| `KS_GEMINI_MAX_CALLS_PER_MINUTE` | `25` | Rate-limit guard per minute for Gemini | Verified in tests (**Done**) | Optional override |
| `KS_GEMINI_MAX_CALLS_PER_DAY` | `1000` | Daily budget cap pausing automated scheduler | Verified in tests (**Done**) | Optional override |
| `KS_GEMINI_MAX_RUNS_PER_CLICK` | `5` | Per-click batch clamp for Gemini mode | Verified in tests (**Done**) | Optional override |
| `KS_SCRIPTED_MAX_RUNS_PER_CLICK` | `50` | Per-click batch clamp for Scripted mode | Verified in tests (**Done**) | Optional override |
| `KS_RANDOM_SEED` | `None` | Integer seed for deterministic simulations | Verified in tests (**Done**) | Optional override |
| `KS_REVOKE_FAILURE_PROB` | `0.10` | Injected failure probability for revocations | Verified in tests (**Done**) | Optional override |
| `KS_IN_FLIGHT_LEAK_PROB` | `0.20` | Injected leak probability for in-flight tasks | Verified in tests (**Done**) | Optional override |
| `KS_REVOKE_RETRIES` | `2` | Number of automated revocation retries | Verified in tests (**Done**) | Optional override |
| `KS_NET_DELAY_MIN` / `KS_NET_DELAY_MAX` | `50` / `200` | Simulated channel latency range (ms) | Verified in tests (**Done**) | Optional override |
| `KS_IAM_FAILURE_PROB` | `0.15` | Specific IAM role failure probability | Verified in tests (**Done**) | Optional override |
| `KS_ADMIN_USERNAME` / `KS_ADMIN_PASSWORD_HASH` | `admin` / (bcrypt) | Administrative credentials | Verified in auth tests (**Done**) | **Must change default in production** |

---

## 7. Tests

The test suite is located in `kill-switch-attestation/tests/` and contains **47 tests** across 13 test modules. **All 47 passed in 43.82s**:

| Test File | Tests Passed | Covered Functionality | Status |
| :--- | :--- | :--- | :--- |
| `tests/test_agent_llm.py` | 10/10 | Gemini mode tools execution, 429 backoff retry then fallback, 503/404/401 retry & skip, stop signal halt, revoked credential 401 rejection, API key secrecy, raw provider error sanitization, and mocked Gemini shutdown cycle. | **Done** (Ran & Passed) |
| `tests/test_agent_seeding.py` | 1/1 | Seed demo agent with 4 credentials and initial active state. | **Done** (Ran & Passed) |
| `tests/test_analytics_and_batch.py` | 4/4 | Batch shutdown cycles, analytics summary calculations, channel latency statistics, residual risk bounds, and KILLBENCH comparison endpoint. | **Done** (Ran & Passed) |
| `tests/test_auth.py` | 5/5 | Bcrypt password verification, unauthenticated request rejection, wrong password rejection, correct login token generation/logout lifecycle, and demo-admin-token rejection. | **Done** (Ran & Passed) |
| `tests/test_crypto.py` | 3/3 | Ed25519 signing/verification, private key type enforcement, and hash chain tamper detection identifying first broken index. | **Done** (Ran & Passed) |
| `tests/test_experiments.py` | 1/1 | Experiment matrix execution and result aggregation. | **Done** (Ran & Passed) |
| `tests/test_iam_failure.py` | 1/1 | Adversarial IAM failure injection and retry tracking. | **Done** (Ran & Passed) |
| `tests/test_in_flight.py` | 5/5 | Strategy A post-cutoff leak classification, Strategy C cancellation, two identical seeded cycles produce identical outcomes, deterministic classification, proof that Strategy A leaks more than B and C. | **Done** (Ran & Passed) |
| `tests/test_live_run_defects.py` | 5/5 | Agent mode server source of truth, fresh provisioning across 3 consecutive cycles, mixed scripted and Gemini filtering, feedback loop window and scripted exclusion rules, three latency metrics consistency. | **Done** (Ran & Passed) |
| `tests/test_probes.py` | 1/1 | Active channel challenge probes testing active, revoked, and failed credentials. | **Done** (Ran & Passed) |
| `tests/test_randomness_and_quota.py` | 5/5 | Seeded RNG reproducibility vs unseeded uniqueness, heavy-tailed bounds enforcement, exponential delay mean, quota call tracking and daily budget pause, scheduler lifecycle. | **Done** (Ran & Passed) |
| `tests/test_revocation.py` | 4/4 | Multi-channel concurrent revocation, idempotent revocation, forced channel failure producing leaked channel & matrix FAIL, concurrent revocation concurrency timing. | **Done** (Ran & Passed) |
| `tests/test_shutdown_strategies.py` | 2/2 | Comparative run of Strategy A, B, and C with state guarantees and new operation blocking. | **Done** (Ran & Passed) |

---

## 8. Known Issues & Risks

1. **Live Gemini Multi-Turn Verification**:
   - All automated unit tests use mock Gemini clients to validate tool calls, 429 retries, and 404 fallbacks safely without burning API quotas.
   - Single-turn verification was confirmed via `scripts/gemini_smoke_test.py`.
   - Full live multi-turn execution against Google Gemini during a live shutdown cycle must be manually run and verified by the user with their active key.
2. **Simulated Sandbox Latencies**:
   - Latencies and failure probabilities reflect configurable statistical models rather than physical cloud API round-trips.
3. **SQLite Concurrency**:
   - High-iteration concurrent batch sweeps under `aiosqlite` can occasionally produce brief file locks if multiple parallel writes collide. For heavy multi-tenant production, migration to PostgreSQL is recommended.

---

## 9. Remaining Work & Viva Notes

### 9.1 Remaining Tasks for Final Review
1. **Live Gemini Multi-Turn Run**: Run an end-to-end cycle with `GEMINI_API_KEY` populated to confirm real token consumption and live function responses.
2. **Presentation Preparation**: Prepare slide deck aligning with Section 22 viva answers (why mock channels, why random kill timing, why Gemini, and why hash chains ensure non-repudiation).
3. **PostgreSQL Adapter**: Optional production deployment adapter for multi-tenant scalability.

### 9.2 Viva Report Corrections (Section 22)
| Report Section | Required Wording Correction |
| :--- | :--- |
| **Section 6 & Figure 1, Phase 9** | Change "Streamlit and Plotly" to "FastAPI, Chart.js and Native WebSocket". |
| **Section 7.1 Module Table** | Change "Anthropic / OpenAI SDK" to "Google GenAI SDK (Gemini API, gemini-3.5-flash-lite)". |
| **Section 7.1 Dashboard Row** | Rename to "FastAPI and Chart.js dashboard". |
| **Section 7.1 Scheduler Row** | Update to "APScheduler with random (Poisson and heavy-tailed) timing and dynamic feedback". |
| **Section 7.1 Cryptographic Signer** | State "Ed25519 with SHA-256 hash chain rooted at 'GENESIS'". |
| **Section 8 Dataset** | Add that kill moments and inter-arrival intervals are random, and scripted/skipped runs are excluded from headline metrics. |
| **Figure 2 Channel 4** | Label "NETWORK (External Tool/API)". |
| **General Strategy Claims** | Replace any claim of "four strategies" or "zero-leak guarantee" with "three strategies with modelled outcomes". |

---

## 10. Step-by-Step 5-Minute Demo Script

### Step 1: Environment Setup & Smoke Test
```powershell
cd d:\killswitch-attestation_AI_2026\kill-switch-attestation
d:\killswitch-attestation_AI_2026\.venv\Scripts\python.exe scripts\gemini_smoke_test.py
```
*Expected Output*: `Tool called: send_email` (or an informative note if `GEMINI_API_KEY` is not populated).

### Step 2: Run Full Automated Test Suite
```powershell
d:\killswitch-attestation_AI_2026\.venv\Scripts\pytest.exe tests/ -v
```
*Expected Output*: `47 passed in ~40s`.

### Step 3: Launch the Server
```powershell
d:\killswitch-attestation_AI_2026\.venv\Scripts\uvicorn.exe main:app --reload --host 127.0.0.1 --port 8000
```
Open `http://localhost:8000` in your web browser.

### Step 4: Demonstrate Strategy Differences
1. On the **Dashboard**, select **Strategy A (Revocation-Only)** and click **Initiate Shutdown**.
   - Observe in the console: in-flight operations past cutoff are flagged as `COMPLETED_AFTER_SHUTDOWN` (leaks).
   - Agent final state: `CONTAINED` with non-zero residual risk.
2. Next, select **Strategy C (Hybrid)** and click **Initiate Shutdown**.
   - Observe: agent enters `CONTAINING`, active operations are cancelled, and residual risk drops toward 0.
   - Agent final state: `TERMINATED` (or low risk).

### Step 5: Verify the Cryptographic Hash Chain
1. In the top navigation bar, click **Verify Chain** (or invoke via curl):
```powershell
curl http://localhost:8000/api/shutdown/verify-chain
```
*Expected Output*: `{"valid": true, "entries_checked": N, "first_failure_index": null}`.

### Step 6: Verify 404 Model Handling
In `.env`, set `AGENT_MODEL=gemini-nonexistent-model` and trigger a cycle:
- Verify console emits: `[agent] Model 'gemini-nonexistent-model' not found (404). Check AGENT_MODEL. Falling back to Scripted mode.`
- Execution continues smoothly via Scripted mode without crashing or hanging.
