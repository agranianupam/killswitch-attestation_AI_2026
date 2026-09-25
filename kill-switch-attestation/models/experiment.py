"""
models/experiment.py — Experiment + ExperimentResult ORM models (FR-10).

Experiment status: RUNNING | COMPLETED | FAILED
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from models.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Experiment(Base):
    __tablename__ = "experiments"

    id           = Column(String, primary_key=True)
    strategy     = Column(String, nullable=False)
    cycle_count  = Column(Integer, nullable=False)
    status       = Column(String, default="RUNNING")   
    created_at   = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)


class ExperimentResult(Base):
    __tablename__ = "experiment_results"

    id                 = Column(String, primary_key=True)
    experiment_id      = Column(String, ForeignKey("experiments.id"))
    cycle_number       = Column(Integer, nullable=False)
    latency_ms         = Column(Float, nullable=False)
    leak_count         = Column(Integer, nullable=False)
    in_flight_failures = Column(Integer, nullable=False)
    retry_count        = Column(Integer, nullable=False)
    success_rate       = Column(Float, nullable=False)
    shutdown_event_id  = Column(String, ForeignKey("shutdown_events.id"))
