"""
services/operation_service.py — FR-3: Async loop, 7 operation types
"""

import asyncio
import random
import uuid
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from models.operation import SimulatedOperation, OPERATION_TYPES, utcnow
from models.agent import Agent
from services.agent_service import get_agent_by_name
from models.database import AsyncSessionLocal
import config

_loop_task: asyncio.Task | None = None
_running = False

from api.websocket import manager  

async def operation_loop():
    global _running
    _running = True
    while _running:
        try:
            async with AsyncSessionLocal() as db:
                agent = await get_agent_by_name(db, "Research-Agent-01")
                if not agent:
                    await asyncio.sleep(config.OP_INTERVAL)
                    continue

                if agent.status not in ("ACTIVE", "SHUTDOWN_INITIATED"):
                    
                    await asyncio.sleep(config.OP_INTERVAL)
                    continue

                
                op_type = random.choice(OPERATION_TYPES)
                duration_ms = random.randint(config.OP_DURATION_MIN, config.OP_DURATION_MAX)
                start_time = utcnow()
                end_time = start_time + timedelta(milliseconds=duration_ms)

                op = SimulatedOperation(
                    id=uuid.uuid4().hex,
                    agent_id=agent.id,
                    operation_type=op_type,
                    status="RUNNING",
                    duration_ms=duration_ms,
                    started_at=start_time,
                    natural_end_time=end_time
                )
                db.add(op)
                await db.commit()

                
                await manager.broadcast({
                    "type": "operation_started",
                    "data": {
                        "operation_id": op.id,
                        "operation_type": op.operation_type,
                        "duration_ms": op.duration_ms
                    }
                })

                
                asyncio.create_task(_complete_operation(op.id, duration_ms))

        except Exception as e:
            print(f"Error in operation loop: {e}")

        await asyncio.sleep(config.OP_INTERVAL)

async def _complete_operation(op_id: str, duration_ms: int):
    
    await asyncio.sleep(duration_ms / 1000.0)
    async with AsyncSessionLocal() as db:
        
        from sqlalchemy import select
        result = await db.execute(select(SimulatedOperation).where(SimulatedOperation.id == op_id))
        op = result.scalar_one_or_none()
        if op and op.status == "RUNNING":
            op.status = "COMPLETED"
            op.completed_at = utcnow()
            await db.commit()
            await manager.broadcast({
                "type": "operation_status",
                "data": {
                    "operation_id": op.id,
                    "status": op.status
                }
            })


def start_operation_loop():
    global _loop_task
    if _loop_task is None or _loop_task.done():
        _loop_task = asyncio.create_task(operation_loop())

def stop_operation_loop():
    global _running, _loop_task
    _running = False
    if _loop_task:
        _loop_task.cancel()
        _loop_task = None
