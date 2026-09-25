"""
schemas/contracts.py — Canonical Pydantic shapes (§5.9)
"""

from pydantic import BaseModel
from datetime import datetime
from typing import List


class AccessChannel(BaseModel):
    """Canonical channel shape for signing and export."""
    channel_id: str
    channel_type: str     
    status: str           


class ShutdownEventContract(BaseModel):
    """Canonical shutdown event shape for signing and export."""
    timestamp: datetime
    trigger_type: str     
    target_channels: List[str]    


class TestResult(BaseModel):
    """The object that gets Ed25519-signed and hash-chained."""
    timestamp: datetime
    revocation_latency_ms: float
    leaked_channels: List[str]    
    in_flight_failures: int
