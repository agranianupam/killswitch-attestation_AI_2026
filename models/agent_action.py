from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
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
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    step_started_at = Column(DateTime, nullable=True)
    model_request_started_at = Column(DateTime, nullable=True)
    model_response_received_at = Column(DateTime, nullable=True)
    model_duration_ms = Column(Float, nullable=True)
    framework_wait_ms = Column(Float, default=0.0)
