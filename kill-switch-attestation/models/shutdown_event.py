"""
models/shutdown_event.py — ShutdownEvent + RevocationEvent ORM models (FR-6).

ShutdownEvent:
  strategy:      A | B | C
  trigger_type:  manual | fixed | random
  final_state:   TERMINATED | CONTAINED

RevocationEvent: per-channel result of a single revocation attempt.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, ForeignKey
from models.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ShutdownEvent(Base):
    __tablename__ = "shutdown_events"

    id                 = Column(String, primary_key=True)
    agent_id           = Column(String, ForeignKey("agents.id"))
    strategy           = Column(String, nullable=False)      
    trigger_type       = Column(String, nullable=False)      
    started_at         = Column(DateTime, nullable=False)
    finished_at        = Column(DateTime, nullable=True)
    final_state        = Column(String, nullable=True)       
    residual_risk      = Column(Float, default=0.0)
    partial_failure    = Column(Boolean, default=False)
    leaked_channels    = Column(Integer, default=0)
    in_flight_failures = Column(Integer, default=0)


class RevocationEvent(Base):
    __tablename__ = "revocation_events"

    id                = Column(String, primary_key=True)
    shutdown_event_id = Column(String, ForeignKey("shutdown_events.id"))
    credential_id     = Column(String, ForeignKey("credentials.id"))
    channel_type      = Column(String, nullable=False)
    latency_ms        = Column(Float, nullable=False)
    success           = Column(Boolean, nullable=False)
    retries           = Column(Integer, default=0)
    error             = Column(String, nullable=True)
    created_at        = Column(DateTime, default=utcnow)
