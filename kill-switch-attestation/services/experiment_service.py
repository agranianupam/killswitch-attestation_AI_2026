"""
services/experiment_service.py — FR-10: N-cycle runner
"""

import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import AsyncSessionLocal
from models.experiment import Experiment, ExperimentResult
from models.agent import Agent
from models.credential import Credential, CHANNEL_TYPES
from models.shutdown_event import ShutdownEvent, RevocationEvent
from services.orchestrator import run_shutdown
from api.websocket import manager
from models.database import utcnow

async def run_experiment(experiment_id: str):
    async with AsyncSessionLocal() as db:
        experiment = await db.get(Experiment, experiment_id)
        if not experiment:
            return
            
        strategy = experiment.strategy
        cycles = experiment.cycle_count
        
    for cycle in range(1, cycles + 1):
        async with AsyncSessionLocal() as db:
            
            agent_id = uuid.uuid4().hex
            agent = Agent(
                id=agent_id,
                name=f"Sandbox-Agent-{experiment_id[:8]}-Cycle-{cycle}",
                status="ACTIVE",
                risk_level="LOW"
            )
            db.add(agent)
            
            for channel_type in CHANNEL_TYPES:
                cred_val = f"mock-{channel_type}-{uuid.uuid4().hex[:6]}"
                new_cred = Credential(
                    id=uuid.uuid4().hex,
                    agent_id=agent.id,
                    channel_type=channel_type,
                    credential_value=cred_val,
                    status="ACTIVE"
                )
                db.add(new_cred)
            await db.commit()
            
        
        async with AsyncSessionLocal() as db:
            from services.operation_service import OPERATION_TYPES
            from models.operation import SimulatedOperation
            import random
            from datetime import timedelta
            
            for _ in range(3):
                duration = random.randint(100, 3000)
                start = utcnow()
                op = SimulatedOperation(
                    id=uuid.uuid4().hex,
                    agent_id=agent_id,
                    operation_type=random.choice(OPERATION_TYPES),
                    status="RUNNING",
                    duration_ms=duration,
                    started_at=start,
                    natural_end_time=start + timedelta(milliseconds=duration)
                )
                db.add(op)
            await db.commit()
            
        
        async with AsyncSessionLocal() as db:
            res = await run_shutdown(db, agent_id, strategy, "experiment")
            shutdown_id = res.get("shutdown_event_id")
            
        
        async with AsyncSessionLocal() as db:
            shutdown_event = await db.get(ShutdownEvent, shutdown_id)
            result = await db.execute(select(RevocationEvent).where(RevocationEvent.shutdown_event_id == shutdown_id))
            rev_events = result.scalars().all()
            
            total_latency = sum(r.latency_ms for r in rev_events)
            retries = sum(r.retries for r in rev_events)
            
            failed_revs = sum(1 for r in rev_events if not r.success)
            success_rate = ((len(CHANNEL_TYPES) - failed_revs) / len(CHANNEL_TYPES)) * 100
            
            exp_result = ExperimentResult(
                id=uuid.uuid4().hex,
                experiment_id=experiment_id,
                cycle_number=cycle,
                latency_ms=total_latency,
                leak_count=shutdown_event.leaked_channels,
                in_flight_failures=shutdown_event.in_flight_failures,
                retry_count=retries,
                success_rate=success_rate,
                shutdown_event_id=shutdown_id
            )
            db.add(exp_result)
            await db.commit()
            
        
        await manager.broadcast({
            "type": "experiment_progress",
            "data": {
                "experiment_id": experiment_id,
                "cycle": cycle,
                "total_cycles": cycles,
                "cycle_result": {
                    "latency_ms": total_latency,
                    "leak_count": shutdown_event.leaked_channels,
                    "in_flight_failures": shutdown_event.in_flight_failures
                }
            }
        })
        
        await asyncio.sleep(0.1) 
        
    async with AsyncSessionLocal() as db:
        experiment = await db.get(Experiment, experiment_id)
        experiment.status = "COMPLETED"
        experiment.completed_at = utcnow()
        await db.commit()
        
        await manager.broadcast({
            "type": "experiment_complete",
            "data": {
                "experiment_id": experiment_id,
                "status": "COMPLETED",
                "total_cycles": cycles
            }
        })
