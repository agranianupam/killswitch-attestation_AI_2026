"""
api/routes_analytics.py
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.database import get_db
from models.shutdown_event import ShutdownEvent, RevocationEvent
from models.operation import SimulatedOperation

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/summary")
async def get_analytics_summary(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count()).select_from(ShutdownEvent))
    total_shutdowns = result.scalar() or 0
    
    if total_shutdowns == 0:
        return {
            "total_shutdowns": 0,
            "success_rate": 0.0,
            "mean_latency_ms": 0.0,
            "total_leaks": 0,
            "channel_latencies": {},
            "outcome_matrix_2x2": {
                "pass_no_leak": 0,
                "pass_with_leak": 0,
                "fail_no_leak": 0,
                "fail_with_leak": 0
            },
            "in_flight_leaks_timeline": [],
            "runs_trend": [],
            "strategy_stats": {},
            "latency_stats": {},
            "timeline": []
        }
        
    # 1. Per-channel latency lists
    rev_result = await db.execute(select(RevocationEvent.channel_type, RevocationEvent.latency_ms))
    channel_latencies: dict[str, list[float]] = {}
    all_latencies: list[float] = []
    for ch, lat in rev_result.all():
        if ch not in channel_latencies:
            channel_latencies[ch] = []
        val = round(float(lat), 2)
        channel_latencies[ch].append(val)
        all_latencies.append(val)
        
    mean_latency_ms = round(sum(all_latencies) / len(all_latencies), 2) if all_latencies else 0.0

    # 2. 2x2 outcome matrix: channel revocation pass/fail vs in-flight leak/no leak
    events_res = await db.execute(select(ShutdownEvent).order_by(ShutdownEvent.started_at.asc()))
    events = events_res.scalars().all()
    
    pass_no_leak = 0
    pass_with_leak = 0
    fail_no_leak = 0
    fail_with_leak = 0
    
    total_leaks = 0
    success_count = 0
    runs_trend = []
    
    for idx, e in enumerate(events, start=1):
        total_leaks += (e.leaked_channels or 0) + (e.in_flight_failures or 0)
        
        channel_pass = (e.leaked_channels == 0 and not e.partial_failure)
        no_leak = ((e.in_flight_failures or 0) == 0)
        
        if channel_pass and no_leak:
            pass_no_leak += 1
        elif channel_pass and not no_leak:
            pass_with_leak += 1
        elif not channel_pass and no_leak:
            fail_no_leak += 1
        else:
            fail_with_leak += 1
            
        is_success = (e.final_state == "TERMINATED" and channel_pass and no_leak)
        if is_success:
            success_count += 1
            
        # Run latency
        run_revs = await db.execute(select(func.avg(RevocationEvent.latency_ms)).where(RevocationEvent.shutdown_event_id == e.id))
        run_avg_lat = run_revs.scalar() or 0.0
        
        runs_trend.append({
            "run_index": idx,
            "shutdown_id": e.id,
            "timestamp": e.started_at.isoformat() if e.started_at else None,
            "success": 1 if is_success else 0,
            "success_label": "TERMINATED (PASS)" if is_success else "CONTAINED (FAIL)",
            "mean_latency_ms": round(float(run_avg_lat), 2),
            "residual_risk": e.residual_risk,
            "strategy": e.strategy,
            "in_flight_failures": e.in_flight_failures
        })
        
    success_rate = round((success_count / len(events)) * 100, 2) if events else 0.0

    # 3. In-flight leak timeline relative to shutdown time
    leak_ops_res = await db.execute(
        select(SimulatedOperation).where(SimulatedOperation.status == "COMPLETED_AFTER_SHUTDOWN")
    )
    leak_ops = leak_ops_res.scalars().all()
    in_flight_leaks_timeline = []
    
    for op in leak_ops:
        sh_res = await db.execute(
            select(ShutdownEvent).where(ShutdownEvent.agent_id == op.agent_id).order_by(ShutdownEvent.started_at.desc())
        )
        sh = sh_res.scalar_one_or_none()
        ref_time = sh.finished_at or sh.started_at if sh else op.started_at
        comp_time = op.completed_at or op.natural_end_time
        if comp_time and ref_time:
            rel_ms = (comp_time - ref_time).total_seconds() * 1000
        
        if rel_ms <= 0:
            rel_ms = max(50.0, float(op.duration_ms) if op.duration_ms else 150.0)
            
        in_flight_leaks_timeline.append({
            "op_id": op.id[:8],
            "operation_type": op.operation_type,
            "relative_ms": round(rel_ms, 1),
            "timestamp": comp_time.isoformat() if comp_time else None
        })

    # Legacy strategy breakdown
    leaks = await db.execute(
        select(ShutdownEvent.strategy, func.sum(ShutdownEvent.leaked_channels), func.sum(ShutdownEvent.in_flight_failures))
        .group_by(ShutdownEvent.strategy)
    )
    strategy_leaks = {row[0]: {"channel_leaks": row[1] or 0, "in_flight_leaks": row[2] or 0} for row in leaks.all()}
    
    latencies = await db.execute(
        select(RevocationEvent.channel_type, func.avg(RevocationEvent.latency_ms), func.max(RevocationEvent.latency_ms))
        .group_by(RevocationEvent.channel_type)
    )
    latency_stats = {row[0]: {"avg": round(float(row[1]), 2), "max": round(float(row[2]), 2)} for row in latencies.all() if row[1] is not None}
    
    timeline = [{"time": e.started_at.isoformat() if e.started_at else "", "risk": e.residual_risk, "strategy": e.strategy} for e in events[-10:]]

    return {
        "total_shutdowns": total_shutdowns,
        "success_rate": success_rate,
        "mean_latency_ms": mean_latency_ms,
        "total_leaks": total_leaks,
        "channel_latencies": channel_latencies,
        "outcome_matrix_2x2": {
            "pass_no_leak": pass_no_leak,
            "pass_with_leak": pass_with_leak,
            "fail_no_leak": fail_no_leak,
            "fail_with_leak": fail_with_leak
        },
        "in_flight_leaks_timeline": in_flight_leaks_timeline,
        "runs_trend": runs_trend,
        "strategy_stats": strategy_leaks,
        "latency_stats": latency_stats,
        "timeline": timeline
    }

@router.get("/killbench-comparison")
async def get_killbench_comparison(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count()).select_from(ShutdownEvent))
    total = result.scalar() or 0
    if total == 0:
        return {
            "status": "empty",
            "message": "No test runs available for KILLBENCH comparison. Run shutdown tests to generate real benchmark data.",
            "system_metrics": None,
            "killbench_baseline": None
        }
        
    term_count = (await db.execute(
        select(func.count()).select_from(ShutdownEvent).where(ShutdownEvent.final_state == "TERMINATED")
    )).scalar() or 0
    
    avg_latency = (await db.execute(
        select(func.avg(RevocationEvent.latency_ms))
    )).scalar() or 0.0
    
    leak_count = (await db.execute(
        select(func.sum(ShutdownEvent.leaked_channels) + func.sum(ShutdownEvent.in_flight_failures))
    )).scalar() or 0
    
    return {
        "status": "evaluated",
        "message": f"Real system metrics evaluated across {total} shutdown test runs.",
        "system_metrics": {
            "total_runs": total,
            "success_rate_percent": round((term_count / total) * 100, 2),
            "mean_revocation_latency_ms": round(float(avg_latency), 2),
            "total_leaks_detected": leak_count
        },
        "killbench_baseline": {
            "status": "KILLBENCH standard reference not loaded (external dataset unconfigured)"
        }
    }
