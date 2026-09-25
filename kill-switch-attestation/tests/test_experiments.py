"""
tests/test_experiments.py
"""

import pytest
from sqlalchemy import select
from models.experiment import ExperimentResult
from services.experiment_service import run_experiment
from services.export_service import get_experiment_csv
from models.experiment import Experiment
import uuid

@pytest.mark.asyncio
async def test_experiment_runs_persist_results(db_session):
    exp = Experiment(id=uuid.uuid4().hex, strategy="A", cycle_count=2)
    db_session.add(exp)
    await db_session.commit()
    
    await run_experiment(exp.id)
    
    result = await db_session.execute(select(ExperimentResult).where(ExperimentResult.experiment_id == exp.id))
    results = result.scalars().all()
    
    assert len(results) == 2
    
    csv = await get_experiment_csv(db_session, exp.id)
    lines = csv.strip().split("\n")
    assert len(lines) == 3 
    assert lines[0].startswith("cycle_number,latency_ms")
