from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime
from models.database import Base

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True)
    severity = Column(String, nullable=False, default="info")
    category = Column(String, nullable=False, default="system")
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=True)
    experiment_id = Column(String, nullable=True)
    channel_or_op_id = Column(String, nullable=True)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "message": self.message,
            "recommended_action": self.recommended_action,
            "experiment_id": self.experiment_id,
            "channel_or_op_id": self.channel_or_op_id,
            "acknowledged": self.acknowledged,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
