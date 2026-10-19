from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from models.database import Base

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("shutdown_events.id"), nullable=True)
    step_number = Column(Integer, default=0)
    tool_name = Column(String, nullable=False)
    arguments = Column(String, default="{}")
    timestamp = Column(DateTime, default=utcnow)
    outcome = Column(String, nullable=False)
    operation_id = Column(String, nullable=True)
    rejection_reason = Column(String, nullable=True)
    tokens_used = Column(Integer, default=0)
