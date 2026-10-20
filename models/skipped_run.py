import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from models.database import Base

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class SkippedRun(Base):
    __tablename__ = "skipped_runs"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=utcnow)
    reason = Column(String, nullable=False)
    friendly_message = Column(String, nullable=True)
    agent_mode = Column(String, default="gemini")
