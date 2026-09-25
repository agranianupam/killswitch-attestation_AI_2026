"""
models/credential.py — Credential ORM model (FR-2, FR-4).

Channel types: api_key, session_token, iam_role, external_tool
Status values: ACTIVE, REVOKING, REVOKED, REVOCATION_FAILED, EXPIRED
Credential value format: mock-{channel_type}-{6 hex chars}
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from models.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


CHANNEL_TYPES = ["api_key", "session_token", "iam_role", "external_tool"]

CREDENTIAL_STATUS = ["ACTIVE", "REVOKING", "REVOKED", "REVOCATION_FAILED", "EXPIRED"]


class Credential(Base):
    __tablename__ = "credentials"

    id               = Column(String, primary_key=True)
    agent_id         = Column(String, ForeignKey("agents.id"))
    channel_type     = Column(String, nullable=False)
    credential_value = Column(String, nullable=False)
    status           = Column(String, default="ACTIVE")
    created_at       = Column(DateTime, default=utcnow)
    revoked_at       = Column(DateTime, nullable=True)

    agent = relationship("Agent", back_populates="credentials")
