"""
models/agent.py — Agent ORM model (FR-1).

Status values: ACTIVE, SHUTDOWN_INITIATED, CONTAINING, TERMINATED, CONTAINED
Risk values:   LOW, MEDIUM, HIGH
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from models.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Agent(Base):
    __tablename__ = "agents"

    id           = Column(String, primary_key=True)       
    name         = Column(String, unique=True, nullable=False)
    status       = Column(String, default="ACTIVE")        
    risk_level   = Column(String, default="LOW")           
    current_task = Column(String, nullable=True)
    created_at   = Column(DateTime, default=utcnow)

    credentials  = relationship("Credential", back_populates="agent")
