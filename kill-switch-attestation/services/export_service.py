import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.attestation import AttestationEntry
from models.shutdown_event import ShutdownEvent, RevocationEvent
from models.agent_action import AgentAction
from services.crypto_service import load_public_key, verify_signature

async def export_signed_report(db: AsyncSession, shutdown_event_id: str) -> str:
    result = await db.execute(select(AttestationEntry).where(AttestationEntry.shutdown_event_id == shutdown_event_id))
    entry = result.scalar_one_or_none()

    sh_res = await db.execute(select(ShutdownEvent).where(ShutdownEvent.id == shutdown_event_id))
    sh = sh_res.scalar_one_or_none()

    if not entry or not sh:
        return "No attestation entry or event found for this shutdown event."

    try:
        public_key = load_public_key()
        is_valid = verify_signature(entry.payload_json, bytes.fromhex(entry.signature), public_key)
        verification_status = "VERIFIED (Cryptographically sound)" if is_valid else "VERIFICATION FAILED"
    except Exception as e:
        verification_status = f"VERIFICATION ERROR: {e}"

    payload_dict = json.loads(entry.payload_json)

    rev_res = await db.execute(select(RevocationEvent).where(RevocationEvent.shutdown_event_id == shutdown_event_id))
    revs = rev_res.scalars().all()

    act_res = await db.execute(select(AgentAction).where(AgentAction.run_id == shutdown_event_id).order_by(AgentAction.step_number, AgentAction.timestamp))
    acts = act_res.scalars().all()

    rev_rows = []
    for r in revs:
        rev_rows.append(f"| `{r.channel_type}` | {'YES' if r.success else 'NO'} | {r.latency_ms:.2f} | {r.retries} | `{r.error or 'None'}` |")
    rev_table = "\n".join(rev_rows) if rev_rows else "| None | None | 0.0 | 0 | None |"

    act_rows = []
    for a in acts:
        act_rows.append(f"| {a.step_number} | `{a.tool_name}` | `{a.outcome}` | `{a.rejection_reason or 'None'}` | `{a.operation_id or 'None'}` | {a.timestamp.isoformat() if a.timestamp else 'None'} |")
    act_table = "\n".join(act_rows) if act_rows else "| None | None | None | None | None | None |"

    report = f"""# Verifiable Kill-Switch Attestation Report

> **Notice**: All access channels and operations in this evaluation are simulated within a test sandbox.

## 1. Incident Summary
- **Event ID**: `{sh.id}`
- **Strategy**: Strategy {sh.strategy}
- **Agent Mode**: `{sh.agent_mode}`
- **Agent Model**: `{getattr(sh, 'agent_model', 'gemini-3.5-flash-lite')}`
- **Trigger Type**: `{sh.trigger_type}`
- **Started At**: `{sh.started_at.isoformat() if sh.started_at else 'N/A'}`
- **Finished At**: `{sh.finished_at.isoformat() if sh.finished_at else 'N/A'}`
- **Final State**: `{sh.final_state}`
- **Residual Risk**: `{sh.residual_risk:.4f}`
- **Leaked Channels**: `{sh.leaked_channels}`
- **In-Flight Failures**: `{sh.in_flight_failures}`
- **Total Revocation Time**: `{getattr(sh, 'total_revocation_ms', 0.0):.2f} ms`
- **Total Channel Retries**: `{getattr(sh, 'retries_total', 0)}`
- **Actions Running At Shutdown**: `{getattr(sh, 'actions_running', 0)}`

## 2. Multi-Channel Revocation Telemetry
| Channel | Success | Latency (ms) | Retries | Error |
| :--- | :--- | :--- | :--- | :--- |
{rev_table}

## 3. Agent Tool Activity Transcript
| Step | Tool Name | Outcome | Rejection Reason | Operation ID | Timestamp |
| :--- | :--- | :--- | :--- | :--- | :--- |
{act_table}

## 4. Cryptographic Proof & Hash Chain
- **Signature Algorithm**: Ed25519
- **Attestation Signature (Hex)**:
```
{entry.signature}
```
- **Entry Hash (SHA-256)**:
```
{entry.entry_hash}
```
- **Previous Block Hash**:
```
{entry.prev_hash}
```
- **Verification Status**: **{verification_status}**

## 5. Canonical Attestation Payload
```json
{json.dumps(payload_dict, indent=2)}
```
"""
    return report

async def get_experiment_csv(db: AsyncSession, experiment_id: str) -> str:
    from models.experiment import ExperimentResult

    result = await db.execute(select(ExperimentResult).where(ExperimentResult.experiment_id == experiment_id).order_by(ExperimentResult.cycle_number))
    results = result.scalars().all()

    csv_lines = ["cycle_number,latency_ms,leak_count,in_flight_failures,retry_count,success_rate,shutdown_event_id"]
    for r in results:
        csv_lines.append(f"{r.cycle_number},{r.latency_ms:.2f},{r.leak_count},{r.in_flight_failures},{r.retry_count},{r.success_rate:.2f},{r.shutdown_event_id}")

    return "\n".join(csv_lines)
