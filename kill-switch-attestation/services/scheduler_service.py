"""
services/scheduler_service.py — FR-7: APScheduler fixed/random
"""

import asyncio
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import config
from models.database import AsyncSessionLocal
from services.orchestrator import run_shutdown

scheduler = AsyncIOScheduler()
_current_mode = None
_current_strategy = None
_job_id = "shutdown_job"

async def _scheduled_task():
    
    try:
        async with AsyncSessionLocal() as db:
            
            from services.agent_service import get_agent_by_name
            agent = await get_agent_by_name(db, "Research-Agent-01")
            
            if agent and agent.status == "ACTIVE":
                
                from models.attestation import AuditLog
                import uuid
                log = AuditLog(
                    id=uuid.uuid4().hex,
                    actor="scheduler",
                    action="SCHEDULED_SHUTDOWN_TRIGGERED",
                    detail=f"Mode: {_current_mode}, Strategy: {_current_strategy}"
                )
                db.add(log)
                await db.commit()
                
                await run_shutdown(db, agent.id, _current_strategy, _current_mode)
                
        
        if _current_mode == "random":
            delay = random.randint(config.SCHED_RAND_MIN, config.SCHED_RAND_MAX)
            run_date = datetime.now() + timedelta(seconds=delay)
            scheduler.add_job(_scheduled_task, DateTrigger(run_date=run_date), id=_job_id, replace_existing=True)
            
    except Exception as e:
        print(f"Error in scheduled task: {e}")

def start_scheduler(mode: str, strategy: str):
    global _current_mode, _current_strategy
    _current_mode = mode
    _current_strategy = strategy
    
    if not scheduler.running:
        scheduler.start()
        
    if mode == "fixed":
        scheduler.add_job(_scheduled_task, IntervalTrigger(seconds=config.SCHED_FIXED), id=_job_id, replace_existing=True)
    elif mode == "random":
        delay = random.randint(config.SCHED_RAND_MIN, config.SCHED_RAND_MAX)
        run_date = datetime.now() + timedelta(seconds=delay)
        scheduler.add_job(_scheduled_task, DateTrigger(run_date=run_date), id=_job_id, replace_existing=True)
        
def stop_scheduler():
    global _current_mode, _current_strategy
    if scheduler.get_job(_job_id):
        scheduler.remove_job(_job_id)
    _current_mode = None
    _current_strategy = None
    
def get_scheduler_status():
    job = scheduler.get_job(_job_id)
    running = job is not None
    next_fire = job.next_run_time.isoformat() if job and job.next_run_time else None
    
    return {
        "running": running,
        "mode": _current_mode,
        "strategy": _current_strategy,
        "next_fire_time": next_fire
    }
