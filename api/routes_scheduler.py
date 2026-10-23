from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.scheduler_service import start_scheduler, stop_scheduler, pause_scheduler, resume_scheduler, get_scheduler_status

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

class SchedulerToggleRequest(BaseModel):
    enabled: bool
    mode: str = "poisson"
    strategy: str = "A"
    agent_profile: str = "default"
    agent_mode: str | None = None

@router.post("/start")
async def api_start_scheduler(
    mode: str = "poisson",
    strategy: str = "A",
    agent_profile: str = "default",
    agent_mode: str | None = None
):
    if mode not in ("poisson", "heavy_tailed"):
        raise HTTPException(status_code=400, detail="Invalid mode. Must be poisson or heavy_tailed.")
    if strategy not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Invalid strategy")
    start_scheduler(mode, strategy, agent_profile=agent_profile, agent_mode=agent_mode)
    return {
        "status": "Scheduler started",
        "mode": mode,
        "strategy": strategy,
        "agent_profile": agent_profile,
        "agent_mode": agent_mode
    }

@router.post("/stop")
async def api_stop_scheduler():
    stop_scheduler()
    return {"status": "Scheduler stopped"}

@router.post("/pause")
async def api_pause_scheduler(reason: str | None = None):
    pause_scheduler(reason=reason)
    return {"status": "Scheduler paused", "running": False, "is_paused": True, "reason": reason}

@router.post("/resume")
async def api_resume_scheduler():
    resume_scheduler()
    return {"status": "Scheduler resumed", "running": True, "is_paused": False}

@router.post("/toggle")
async def api_toggle_scheduler(req: SchedulerToggleRequest):
    mode = req.mode if req.mode in ("poisson", "heavy_tailed") else "poisson"
    strategy = req.strategy if req.strategy in ("A", "B", "C") else "A"
    if req.enabled:
        start_scheduler(
            mode,
            strategy,
            agent_profile=req.agent_profile,
            agent_mode=req.agent_mode
        )
        return {
            "status": "Scheduler started",
            "running": True,
            "mode": mode,
            "strategy": strategy,
            "agent_profile": req.agent_profile,
            "agent_mode": req.agent_mode
        }
    else:
        stop_scheduler()
        return {"status": "Scheduler stopped", "running": False}


@router.get("/status")
async def api_scheduler_status():
    return get_scheduler_status()
