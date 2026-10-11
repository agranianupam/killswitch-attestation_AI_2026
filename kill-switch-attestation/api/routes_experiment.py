"""
api/routes_experiment.py
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import get_db
from models.experiment import Experiment, ExperimentResult
from api.auth import require_auth
from services.experiment_service import run_experiment
from services.export_service import get_experiment_csv
import uuid
import asyncio

_comparison_history: list[dict] = []

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

@router.post("/compare")
async def run_strategy_comparison(cycles: int = 5, db: AsyncSession = Depends(get_db), auth_user: str = Depends(require_auth)):
    if cycles < 1 or cycles > 30:
        raise HTTPException(status_code=400, detail="Cycles per strategy must be between 1 and 30")
        
    from services.orchestrator import execute_shutdown_cycle
    from api.websocket import manager
    from models.database import utcnow
    
    comp_id = uuid.uuid4().hex
    overall_total = cycles * 3
    current_step = 0
    
    strategies_data = {
        "A": {"runs": 0, "success_count": 0, "leak_count": 0, "total_latencies": [], "total_risks": []},
        "B": {"runs": 0, "success_count": 0, "leak_count": 0, "total_latencies": [], "total_risks": []},
        "C": {"runs": 0, "success_count": 0, "leak_count": 0, "total_latencies": [], "total_risks": []},
    }
    
    for strat in ["A", "B", "C"]:
        for c in range(1, cycles + 1):
            current_step += 1
            await manager.broadcast({
                "type": "comparison_progress",
                "data": {
                    "strategy": strat,
                    "cycle": c,
                    "cycles_per_strategy": cycles,
                    "overall_cycle": current_step,
                    "total_cycles": overall_total,
                    "percent": round((current_step / overall_total) * 100, 1)
                }
            })
            
            res = await execute_shutdown_cycle(
                db, 
                strategy=strat, 
                trigger_type="comparison", 
                triggered_by="experiment"
            )
            
            is_success = (res.get("final_state") == "TERMINATED" and not res.get("partial_failure") and (res.get("in_flight_failures", 0) == 0))
            has_leak = ((res.get("leaked_channels", 0) > 0) or (res.get("in_flight_failures", 0) > 0))
            
            sd = strategies_data[strat]
            sd["runs"] += 1
            if is_success:
                sd["success_count"] += 1
            if has_leak:
                sd["leak_count"] += 1
            sd["total_risks"].append(float(res.get("residual_risk", 0.0)))
            
            revs = res.get("revocations", [])
            run_lat = sum(r.get("latency_ms", 0.0) for r in revs)
            sd["total_latencies"].append(run_lat)

    summary_results = {}
    for strat, data in strategies_data.items():
        n = data["runs"]
        success_rate = round((data["success_count"] / n) * 100, 1) if n > 0 else 0.0
        leak_rate = round((data["leak_count"] / n) * 100, 1) if n > 0 else 0.0
        mean_lat = round(sum(data["total_latencies"]) / len(data["total_latencies"]), 1) if data["total_latencies"] else 0.0
        mean_risk = round(sum(data["total_risks"]) / len(data["total_risks"]), 3) if data["total_risks"] else 0.0
        
        summary_results[strat] = {
            "strategy": strat,
            "runs": n,
            "success_rate": success_rate,
            "leak_rate": leak_rate,
            "mean_revocation_latency": mean_lat,
            "mean_residual_risk": mean_risk
        }
        
    comp_entry = {
        "id": comp_id,
        "cycles_per_strategy": cycles,
        "timestamp": utcnow().isoformat(),
        "strategies": summary_results
    }
    
    _comparison_history.insert(0, comp_entry)
    if len(_comparison_history) > 50:
        _comparison_history.pop()
        
    return comp_entry

@router.get("/comparison/history")
async def get_comparison_history():
    return _comparison_history


@router.post("")
async def create_experiment(strategy: str, cycles: int, db: AsyncSession = Depends(get_db), auth_user: str = Depends(require_auth)):
    if strategy not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Invalid strategy")
    if cycles < 1 or cycles > 100:
        raise HTTPException(status_code=400, detail="Cycles must be between 1 and 100")
        
    exp = Experiment(
        id=uuid.uuid4().hex,
        strategy=strategy,
        cycle_count=cycles
    )
    db.add(exp)
    await db.commit()
    
    
    asyncio.create_task(run_experiment(exp.id))
    
    return {"experiment_id": exp.id, "status": exp.status}

@router.get("")
async def list_experiments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Experiment).order_by(Experiment.created_at.desc()))
    exps = result.scalars().all()
    return [
        {
            "id": e.id,
            "strategy": e.strategy,
            "cycle_count": e.cycle_count,
            "status": e.status,
            "created_at": e.created_at,
            "completed_at": e.completed_at
        } for e in exps
    ]

@router.get("/{id}/results")
async def get_experiment_results(id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExperimentResult).where(ExperimentResult.experiment_id == id).order_by(ExperimentResult.cycle_number))
    res = result.scalars().all()
    return [
        {
            "cycle_number": r.cycle_number,
            "latency_ms": r.latency_ms,
            "leak_count": r.leak_count,
            "in_flight_failures": r.in_flight_failures,
            "retry_count": r.retry_count,
            "success_rate": r.success_rate
        } for r in res
    ]

@router.get("/{id}/csv", response_class=PlainTextResponse)
async def download_experiment_csv(id: str, db: AsyncSession = Depends(get_db)):
    csv_content = await get_experiment_csv(db, id)
    return PlainTextResponse(
        content=csv_content, 
        headers={"Content-Disposition": f'attachment; filename="experiment_{id}.csv"'}
    )
