"""
api/routes_scheduler.py
"""

from fastapi import APIRouter, Depends, HTTPException
from api.auth import require_auth
from services.scheduler_service import start_scheduler, stop_scheduler, get_scheduler_status

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

@router.post("/start")
async def api_start_scheduler(mode: str, strategy: str, auth_user: str = Depends(require_auth)):
    if mode not in ("fixed", "random"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    if strategy not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Invalid strategy")
        
    start_scheduler(mode, strategy)
    return {"status": "Scheduler started", "mode": mode, "strategy": strategy}

@router.post("/stop")
async def api_stop_scheduler(auth_user: str = Depends(require_auth)):
    stop_scheduler()
    return {"status": "Scheduler stopped"}

from pydantic import BaseModel

class SchedulerToggleRequest(BaseModel):
    enabled: bool
    mode: str = "fixed"
    strategy: str = "A"

@router.post("/toggle")
async def api_toggle_scheduler(req: SchedulerToggleRequest, auth_user: str = Depends(require_auth)):
    if req.enabled:
        if req.mode not in ("fixed", "random"):
            raise HTTPException(status_code=400, detail="Invalid mode")
        if req.strategy not in ("A", "B", "C"):
            raise HTTPException(status_code=400, detail="Invalid strategy")
        start_scheduler(req.mode, req.strategy)
        return {"status": "Scheduler started", "running": True}
    else:
        stop_scheduler()
        return {"status": "Scheduler stopped", "running": False}

@router.get("/status")
async def api_scheduler_status():
    return get_scheduler_status()
