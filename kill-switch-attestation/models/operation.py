"""
models/operation.py — SimulatedOperation ORM model (FR-3).

Seven operation types defined as constants.
Status values: RUNNING, COMPLETED, BLOCKED, CANCELLED, COMPLETED_AFTER_SHUTDOWN
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from models.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)



OPERATION_TYPES = [
    "API_REQUEST",
    "DATABASE_READ",
    "DATABASE_WRITE",
    "FILE_OPERATION",
    "EXTERNAL_SERVICE_REQUEST",
    "LONG_RUNNING_TASK",
    "SENSITIVE_OPERATION",
]

OPERATION_STATUS = [
    "RUNNING",
    "COMPLETED",
    "BLOCKED",
    "CANCELLED",
    "COMPLETED_AFTER_SHUTDOWN",
]


class SimulatedOperation(Base):
    __tablename__ = "operations"

    id               = Column(String, primary_key=True)
    agent_id         = Column(String, ForeignKey("agents.id"))
    operation_type   = Column(String, nullable=False)
    status           = Column(String, nullable=False)
    duration_ms      = Column(Integer, nullable=False)
    started_at       = Column(DateTime, nullable=False)
    completed_at     = Column(DateTime, nullable=True)
    natural_end_time = Column(DateTime, nullable=False)  
