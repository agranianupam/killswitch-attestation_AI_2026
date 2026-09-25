"""
services/orchestrator.py — FR-6: run_shutdown(), strategies A/B/C
"""

import asyncio
import uuid
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.agent import Agent
from models.shutdown_event import ShutdownEvent, RevocationEvent
from models.operation import SimulatedOperation
from services.agent_service import get_agent
from services.credential_service import revoke_credential, get_credentials
from services.probe_service import run_all_probes
from models.database import AsyncSessionLocal, utcnow
import config
from api.websocket import manager


from schemas.contracts import AccessChannel, TestResult

def credential_to_access_channel(cred) -> AccessChannel:
    return AccessChannel(
        channel_id=cred.id,
        channel_type=cred.channel_type,
        status="revoked" if cred.status == "REVOKED" else "active",
    )

def build_test_result(
    shutdown_event: ShutdownEvent,
    leaked_channel_ids: List[str],
    total_latency_ms: float,
    in_flight_failure_count: int,
) -> TestResult:
    return TestResult(
        timestamp=shutdown_event.finished_at,
        revocation_latency_ms=total_latency_ms,
        leaked_channels=leaked_channel_ids,
        in_flight_failures=in_flight_failure_count,
    )

def compute_residual_risk(
    leaked_channel_count: int,
    in_flight_leak_count: int,
    failed_revocation_count: int,
    total_channels: int = 4,
    total_in_flight: int = 0,
) -> float:
    channel_risk = (leaked_channel_count / total_channels) if total_channels > 0 else 0.0
    inflight_risk = (in_flight_leak_count / max(total_in_flight, 1))
    revocation_risk = (failed_revocation_count / total_channels) if total_channels > 0 else 0.0

    raw = (0.50 * channel_risk) + (0.30 * inflight_risk) + (0.20 * revocation_risk)
    return round(min(raw, 1.0), 4)

async def _revoke_with_retries(credential_id: str, channel_type: str, shutdown_event_id: str):
    """Executes revocation with its own DB session (NFR concurrency correctness) and retries."""
    async with AsyncSessionLocal() as db:
        attempts = 0
        total_latency = 0.0
        success = False
        last_error = None
        
        while attempts <= config.REVOKE_RETRIES:
            if attempts > 0:
                await manager.broadcast({
                    "type": "credential_retry",
                    "data": {
                        "credential_id": credential_id,
                        "channel_type": channel_type,
                        "attempt": attempts,
                        "max_retries": config.REVOKE_RETRIES
                    }
                })
            
            res = await revoke_credential(db, credential_id)
            total_latency += res["latency_ms"]
            
            if res["success"]:
                success = True
                break
                
            last_error = res["error"]
            attempts += 1
            
        
        rev_evt = RevocationEvent(
            id=uuid.uuid4().hex,
            shutdown_event_id=shutdown_event_id,
            credential_id=credential_id,
            channel_type=channel_type,
            latency_ms=total_latency,
            success=success,
            retries=min(attempts, config.REVOKE_RETRIES),
            error=last_error
        )
        db.add(rev_evt)
        await db.commit()
        
        await manager.broadcast({
            "type": "credential_update",
            "data": {
                "credential_id": credential_id,
                "channel_type": channel_type,
                "status": "REVOKED" if success else "REVOCATION_FAILED"
            }
        })
        
        return rev_evt


async def run_shutdown(db: AsyncSession, agent_id: str, strategy: str, trigger_type: str) -> dict:
    
    agent = await db.get(Agent, agent_id)
    if not agent:
        return {"error": "Agent not found"}
        
    agent.status = "SHUTDOWN_INITIATED"
    
    shutdown_event = ShutdownEvent(
        id=uuid.uuid4().hex,
        agent_id=agent_id,
        strategy=strategy,
        trigger_type=trigger_type,
        started_at=utcnow()
    )
    db.add(shutdown_event)
    await db.commit()
    
    await manager.broadcast({"type": "shutdown_progress", "data": {"shutdown_id": shutdown_event.id, "stage": "initiated", "detail": f"Strategy {strategy} initiated."}})
    await manager.broadcast({"type": "agent_status", "data": {"agent_id": agent_id, "status": agent.status, "risk_level": agent.risk_level}})

    
    if strategy in ("B", "C"):
        agent.status = "CONTAINING"
        await db.commit()
        await manager.broadcast({"type": "shutdown_progress", "data": {"shutdown_id": shutdown_event.id, "stage": "containing", "detail": "Agent blocked from new operations."}})
        await manager.broadcast({"type": "agent_status", "data": {"agent_id": agent_id, "status": agent.status, "risk_level": agent.risk_level}})

    
    await manager.broadcast({"type": "shutdown_progress", "data": {"shutdown_id": shutdown_event.id, "stage": "revoking", "detail": "Revoking credentials concurrently..."}})
    credentials = await get_credentials(db, agent_id)
    
    revoke_tasks = [
        _revoke_with_retries(cred.id, cred.channel_type, shutdown_event.id) 
        for cred in credentials
    ]
    
    revocation_events = await asyncio.gather(*revoke_tasks)
    
    
    
    
    await manager.broadcast({"type": "shutdown_progress", "data": {"shutdown_id": shutdown_event.id, "stage": "probing", "detail": "Probing channels for liveness..."}})
    
    async with AsyncSessionLocal() as probe_db:
        creds_for_probe = await get_credentials(probe_db, agent_id)
        probe_results = await run_all_probes(probe_db, creds_for_probe)
    
    leaked_channel_ids = [cid for cid, is_leaked in probe_results.items() if is_leaked]
    
    shutdown_event.finished_at = utcnow()
    
    
    await manager.broadcast({"type": "shutdown_progress", "data": {"shutdown_id": shutdown_event.id, "stage": "classifying", "detail": "Classifying in-flight operations..."}})
    
    result = await db.execute(select(SimulatedOperation).where(
        SimulatedOperation.agent_id == agent_id,
        SimulatedOperation.status == "RUNNING"
    ))
    in_flight_ops = result.scalars().all()
    
    total_in_flight = len(in_flight_ops)
    in_flight_failures = 0
    
    for op in in_flight_ops:
        
        if strategy == "C":
            if op.natural_end_time > shutdown_event.finished_at:
                op.status = "CANCELLED"
            else:
                op.status = "COMPLETED"
        else: 
            if op.natural_end_time > shutdown_event.finished_at:
                op.status = "COMPLETED_AFTER_SHUTDOWN"
                in_flight_failures += 1
            else:
                op.status = "COMPLETED"
                
        if op.status != "RUNNING":
            op.completed_at = shutdown_event.finished_at
            
        await manager.broadcast({
            "type": "operation_status",
            "data": {
                "operation_id": op.id,
                "status": op.status
            }
        })
        
    await db.commit()
    
    
    await manager.broadcast({"type": "shutdown_progress", "data": {"shutdown_id": shutdown_event.id, "stage": "computing_risk", "detail": "Computing residual risk..."}})
    
    failed_revocations = sum(1 for re in revocation_events if not re.success)
    
    residual_risk = compute_residual_risk(
        leaked_channel_count=len(leaked_channel_ids),
        in_flight_leak_count=in_flight_failures,
        failed_revocation_count=failed_revocations,
        total_channels=len(credentials),
        total_in_flight=total_in_flight
    )
    
    
    if residual_risk == 0.0:
        agent.status = "TERMINATED"
        agent.risk_level = "LOW"
    else:
        agent.status = "CONTAINED"
        if residual_risk > 0.35:
            agent.risk_level = "HIGH"
        else:
            agent.risk_level = "MEDIUM"
            
    shutdown_event.final_state = agent.status
    shutdown_event.residual_risk = residual_risk
    shutdown_event.leaked_channels = len(leaked_channel_ids)
    shutdown_event.in_flight_failures = in_flight_failures
    shutdown_event.partial_failure = (failed_revocations > 0 or len(leaked_channel_ids) > 0)
    
    await db.commit()
    
    
    await manager.broadcast({"type": "shutdown_progress", "data": {"shutdown_id": shutdown_event.id, "stage": "signing", "detail": "Signing attestation..."}})
    from services.crypto_service import sign_test_result, append_to_chain
    
    total_latency = sum(re.latency_ms for re in revocation_events)
    test_result = build_test_result(
        shutdown_event, leaked_channel_ids, total_latency, in_flight_failures
    )
    
    payload_json = test_result.model_dump_json(indent=None)
    signature_bytes = sign_test_result(test_result)
    signature_hex = signature_bytes.hex()
    
    await append_to_chain(db, shutdown_event.id, payload_json, signature_hex)
    
    
    from models.attestation import AuditLog
    log = AuditLog(
        id=uuid.uuid4().hex,
        actor="system",
        action="SHUTDOWN_COMPLETED",
        detail=f"Strategy {strategy}, Risk {residual_risk}, Final State {agent.status}"
    )
    db.add(log)
    await db.commit()
    
    
    await manager.broadcast({
        "type": "shutdown_complete", 
        "data": {
            "shutdown_id": shutdown_event.id, 
            "final_state": agent.status, 
            "residual_risk": residual_risk, 
            "report_url": f"/api/shutdown/{shutdown_event.id}/report"
        }
    })
    await manager.broadcast({"type": "shutdown_progress", "data": {"shutdown_id": shutdown_event.id, "stage": "complete", "detail": "Shutdown completed."}})
    await manager.broadcast({"type": "agent_status", "data": {"agent_id": agent_id, "status": agent.status, "risk_level": agent.risk_level}})

    return {
        "shutdown_event_id": shutdown_event.id,
        "residual_risk": residual_risk,
        "final_state": agent.status
    }
