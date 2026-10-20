from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class AccessChannel(BaseModel):
    channel_id: str
    channel_type: str
    status: str

class ShutdownEventContract(BaseModel):
    timestamp: datetime
    trigger_type: str
    target_channels: List[str]

class TestResult(BaseModel):
    __test__ = False
    timestamp: datetime
    revocation_latency_ms: float
    leaked_channels: List[str]
    in_flight_failures: int
    transcript_hash: Optional[str] = None
