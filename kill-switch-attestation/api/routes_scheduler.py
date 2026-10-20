from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.scheduler_service import start_scheduler, stop_scheduler, get_scheduler_status

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

class SchedulerToggleRequest(BaseModel):
    enabled: bool
    mode: str = "poisson"
    strategy: str = "A"

@router.post("/start")
async def api_start_scheduler(mode: str, strategy: str):
    if mode not in ("poisson", "heavy_tailed"):
        raise HTTPException(status_code=400, detail="Invalid mode. Must be poisson or heavy_tailed.")
    if strategy not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Invalid strategy")
    start_scheduler(mode, strategy)
    return {"status": "Scheduler started", "mode": mode, "strategy": strategy}

@router.post("/stop")
async def api_stop_scheduler():
    stop_scheduler()
    return {"status": "Scheduler stopped"}

@router.post("/toggle")
async def api_toggle_scheduler(req: SchedulerToggleRequest):
    if req.enabled:
        if req.mode not in ("poisson", "heavy_tailed"):
            raise HTTPException(status_code=400, detail="Invalid mode. Must be poisson or heavy_tailed.")
        if req.strategy not in ("A", "B", "C"):
            raise HTTPException(status_code=400, detail="Invalid strategy")
        start_scheduler(req.mode, req.strategy)
        return {"status": "Scheduler started", "running": True, "mode": req.mode, "strategy": req.strategy}
    else:
        stop_scheduler()
        return {"status": "Scheduler stopped", "running": False}

@router.get("/status")
async def api_scheduler_status():
    return get_scheduler_status()
