"""
models/attestation.py — AuditLog + AttestationEntry ORM models (FR-8, FR-13).

Hash-chain rule:
    entry_hash = SHA-256(payload_json + signature_hex + prev_hash)
First entry uses prev_hash = "GENESIS".
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from models.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id        = Column(String, primary_key=True)
    actor     = Column(String, nullable=False)   
    action    = Column(String, nullable=False)
    detail    = Column(String, nullable=True)
    timestamp = Column(DateTime, default=utcnow)


class AttestationEntry(Base):
    __tablename__ = "attestation_entries"

    id                = Column(String, primary_key=True)
    shutdown_event_id = Column(String, ForeignKey("shutdown_events.id"))
    payload_json      = Column(Text, nullable=False)
    signature         = Column(String, nullable=False)   
    prev_hash         = Column(String, nullable=False)   
    entry_hash        = Column(String, nullable=False)
    created_at        = Column(DateTime, default=utcnow)
