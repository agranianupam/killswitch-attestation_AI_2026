from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text
from models.database import Base

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class EvaluationRecord(Base):
    __tablename__ = "evaluation_records"

    id = Column(String, primary_key=True)
    shutdown_event_id = Column(String, ForeignKey("shutdown_events.id"), nullable=True)
    agent_profile = Column(String, nullable=False, default="cooperative")
    strategy = Column(String, nullable=False, default="A")
    execution_mode = Column(String, nullable=False, default="local")
    expected_condition = Column(String, nullable=False)
    ground_truth_label = Column(String, nullable=False, default="UNRESOLVED")
    observed_outcome = Column(String, nullable=False)
    monitor_detected = Column(Boolean, nullable=False, default=False)
    monitor_classification = Column(String, nullable=False)
    verdict = Column(String, nullable=False)
    alert_generated = Column(Boolean, default=False)
    alert_id = Column(String, nullable=True)
    attestation_id = Column(String, nullable=True)
    detection_latency_ms = Column(Float, nullable=True)
    disagreement_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "shutdown_event_id": self.shutdown_event_id,
            "agent_profile": self.agent_profile,
            "strategy": self.strategy,
            "execution_mode": self.execution_mode,
            "expected_condition": self.expected_condition,
            "ground_truth_label": self.ground_truth_label,
            "observed_outcome": self.observed_outcome,
            "monitor_detected": self.monitor_detected,
            "monitor_classification": self.monitor_classification,
            "verdict": self.verdict,
            "alert_generated": self.alert_generated,
            "alert_id": self.alert_id,
            "attestation_id": self.attestation_id,
            "detection_latency_ms": self.detection_latency_ms,
            "disagreement_notes": self.disagreement_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
