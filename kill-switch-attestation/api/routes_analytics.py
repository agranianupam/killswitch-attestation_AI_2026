"""
api/routes_analytics.py
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.database import get_db
from models.shutdown_event import ShutdownEvent, RevocationEvent

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/summary")
async def get_analytics_summary(db: AsyncSession = Depends(get_db)):
    
    result = await db.execute(select(func.count()).select_from(ShutdownEvent))
    total_shutdowns = result.scalar()
    
    if total_shutdowns == 0:
         return {"total_shutdowns": 0}
         
    
    leaks = await db.execute(
        select(ShutdownEvent.strategy, func.sum(ShutdownEvent.leaked_channels), func.sum(ShutdownEvent.in_flight_failures))
        .group_by(ShutdownEvent.strategy)
    )
    strategy_leaks = {row[0]: {"channel_leaks": row[1], "in_flight_leaks": row[2]} for row in leaks.all()}
    
    
    latencies = await db.execute(
        select(RevocationEvent.channel_type, func.avg(RevocationEvent.latency_ms), func.max(RevocationEvent.latency_ms))
        .group_by(RevocationEvent.channel_type)
    )
    latency_stats = {row[0]: {"avg": row[1], "max": row[2]} for row in latencies.all()}
    
    
    timeline = await db.execute(select(ShutdownEvent).order_by(ShutdownEvent.started_at.desc()).limit(10))
    time_data = [{"time": e.started_at.isoformat(), "risk": e.residual_risk, "strategy": e.strategy} for e in timeline.scalars().all()]
    
    return {
        "total_shutdowns": total_shutdowns,
        "strategy_stats": strategy_leaks,
        "latency_stats": latency_stats,
        "timeline": time_data[::-1] 
    }

@router.get("/killbench-comparison")
async def get_killbench_comparison():
    
    
    return {
        "status": "unverified",
        "message": "KILLBENCH figures: unverified / not loaded",
        "data": None
    }
