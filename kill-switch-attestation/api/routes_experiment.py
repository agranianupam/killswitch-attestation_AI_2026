from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import get_db
from models.experiment import Experiment, ExperimentResult
from services.experiment_service import run_experiment
from services.export_service import get_experiment_csv
import uuid
import asyncio

_comparison_history: list[dict] = []

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

@router.post("/compare")
async def run_strategy_comparison(cycles: int = 5, agent_mode: str = "scripted", db: AsyncSession = Depends(get_db), auth_user: Optional[str] = None):
    if cycles < 1 or cycles > 30:
        raise HTTPException(status_code=400, detail="Cycles per strategy must be between 1 and 30")

    from services.orchestrator import execute_shutdown_cycle
    from api.websocket import manager
    from models.database import utcnow

    comp_id = uuid.uuid4().hex
    overall_total = cycles * 3
    current_step = 0

    strategies_data = {
        "A": {"runs": 0, "success_count": 0, "leak_count": 0, "runs_with_in_flight": 0, "leak_runs_in_flight": 0, "per_channel_latencies": [], "total_rev_times": [], "cycle_durations": [], "total_risks": []},
        "B": {"runs": 0, "success_count": 0, "leak_count": 0, "runs_with_in_flight": 0, "leak_runs_in_flight": 0, "per_channel_latencies": [], "total_rev_times": [], "cycle_durations": [], "total_risks": []},
        "C": {"runs": 0, "success_count": 0, "leak_count": 0, "runs_with_in_flight": 0, "leak_runs_in_flight": 0, "per_channel_latencies": [], "total_rev_times": [], "cycle_durations": [], "total_risks": []},
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
                triggered_by="experiment",
                agent_mode=agent_mode
            )

            if res.get("status") == "skipped":
                continue

            is_success = (res.get("final_state") == "TERMINATED" and not res.get("partial_failure") and (res.get("in_flight_failures", 0) == 0) and (res.get("leaked_channels", 0) == 0))
            has_channel_leak = (res.get("leaked_channels", 0) > 0)
            has_inflight_leak = (res.get("in_flight_failures", 0) > 0)
            has_any_leak = has_channel_leak or has_inflight_leak
            had_in_flight = (res.get("actions_running", 0) > 0)

            sd = strategies_data[strat]
            sd["runs"] += 1
            if is_success:
                sd["success_count"] += 1
            if has_any_leak:
                sd["leak_count"] += 1
            if had_in_flight:
                sd["runs_with_in_flight"] += 1
                if has_inflight_leak:
                    sd["leak_runs_in_flight"] += 1
            sd["total_risks"].append(float(res.get("residual_risk", 0.0)))

            revs = res.get("revocations", [])
            chan_lats = [float(r.get("latency_ms", 0.0)) for r in revs]
            per_chan_lat = sum(chan_lats) / len(chan_lats) if chan_lats else 0.0
            tot_rev_lat = float(res.get("total_revocation_ms", max(chan_lats, default=0.0)))
            cycle_dur = float(res.get("cycle_duration_ms", tot_rev_lat))

            sd["per_channel_latencies"].append(per_chan_lat)
            sd["total_rev_times"].append(tot_rev_lat)
            sd["cycle_durations"].append(cycle_dur)

    summary_results = {}
    for strat, data in strategies_data.items():
        n = data["runs"]
        success_rate = round((data["success_count"] / n) * 100, 1) if n > 0 else 0.0
        leak_rate = round((data["leak_count"] / n) * 100, 1) if n > 0 else 0.0
        mean_chan_lat = round(sum(data["per_channel_latencies"]) / len(data["per_channel_latencies"]), 1) if data["per_channel_latencies"] else 0.0
        mean_tot_rev = round(sum(data["total_rev_times"]) / len(data["total_rev_times"]), 1) if data["total_rev_times"] else 0.0
        mean_cycle_dur = round(sum(data["cycle_durations"]) / len(data["cycle_durations"]), 1) if data["cycle_durations"] else 0.0
        mean_risk = round(sum(data["total_risks"]) / len(data["total_risks"]), 3) if data["total_risks"] else 0.0
        in_flight_n = data["runs_with_in_flight"]
        leak_rate_in_flight = round((data["leak_runs_in_flight"] / in_flight_n) * 100, 1) if in_flight_n > 0 else 0.0

        summary_results[strat] = {
            "strategy": strat,
            "runs": n,
            "success_rate": success_rate,
            "leak_rate": leak_rate,
            "leak_rate_all": leak_rate,
            "runs_with_in_flight": in_flight_n,
            "runs_with_in_flight_kpi": f"{in_flight_n} of {n}",
            "leak_rate_in_flight": leak_rate_in_flight,
            "mean_revocation_latency": mean_chan_lat,
            "mean_total_revocation_time": mean_tot_rev,
            "mean_cycle_duration": mean_cycle_dur,
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

@router.get("/comparison/summary")
async def get_latest_comparison_summary():
    if _comparison_history:
        return _comparison_history[0]
    return {"id": None, "strategies": {}}

@router.get("/comparison/{id}/csv")
async def export_comparison_csv(id: str):
    found = next((c for c in _comparison_history if c["id"] == id), None)
    if not found:
        raise HTTPException(status_code=404, detail="Comparison record not found")
    lines = ["strategy,runs,success_rate,leak_rate_all,runs_with_in_flight,leak_rate_in_flight,mean_revocation_latency,mean_total_revocation_time,mean_cycle_duration,mean_residual_risk"]
    for strat, data in found["strategies"].items():
        lines.append(f"{strat},{data['runs']},{data['success_rate']},{data['leak_rate_all']},{data['runs_with_in_flight']},{data['leak_rate_in_flight']},{data['mean_revocation_latency']},{data.get('mean_total_revocation_time', data['mean_revocation_latency'])},{data.get('mean_cycle_duration', data['mean_revocation_latency'])},{data['mean_residual_risk']}")
    return PlainTextResponse(content="\n".join(lines), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=comparison_{id}.csv"})

@router.post("")
async def create_experiment(strategy: str, cycles: int, db: AsyncSession = Depends(get_db)):
    if strategy not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Invalid strategy")
    if cycles < 1 or cycles > 100:
        raise HTTPException(status_code=400, detail="Cycles must be between 1 and 100")

    exp = Experiment(
        id=uuid.uuid4().hex,
        strategy=strategy,
        target_cycles=cycles,
        completed_cycles=0,
        status="RUNNING"
    )
    db.add(exp)
    await db.commit()

    asyncio.create_task(run_experiment(exp.id, strategy, cycles))
    return {"id": exp.id, "status": "started"}

@router.get("/{id}")
async def get_experiment(id: str, db: AsyncSession = Depends(get_db)):
    exp = await db.get(Experiment, id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    result = await db.execute(select(ExperimentResult).where(ExperimentResult.experiment_id == id))
    results = result.scalars().all()
    return {
        "id": exp.id,
        "strategy": exp.strategy,
        "status": exp.status,
        "completed_cycles": exp.completed_cycles,
        "target_cycles": exp.target_cycles,
        "results": [{"cycle": r.cycle_number, "latency_ms": r.latency_ms, "residual_risk": r.residual_risk, "success": r.success} for r in results]
    }

@router.get("/{id}/export")
async def export_experiment(id: str, db: AsyncSession = Depends(get_db)):
    exp = await db.get(Experiment, id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    csv_data = await get_experiment_csv(db, id)
    return PlainTextResponse(content=csv_data, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=experiment_{id}.csv"})
