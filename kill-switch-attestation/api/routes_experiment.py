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

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

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
