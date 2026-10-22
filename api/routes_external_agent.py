from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import get_db
from datetime import datetime, timezone
import services.external_agent_service as ext_svc
import config

router = APIRouter(prefix="/api/external-agent", tags=["external-agent"])

class RegistrationRequest(BaseModel):
    agent_id: str
    agent_name: str
    agent_url: str
    mode: str = "Scripted"
    channels: list[str] = ["api_key", "session_token", "iam_role", "network"]

class HeartbeatRequest(BaseModel):
    agent_id: str
    status: str
    containment_status: str
    active_operations_count: int
    completed_tasks_count: int
    timestamp: str

class TelemetryRequest(BaseModel):
    agent_id: str
    event_type: str
    detail: str
    metadata: dict = {}
    timestamp: str

class ShutdownTriggerRequest(BaseModel):
    strategy: str = "A"
    trigger_type: str = "manual"

def verify_token(authorization: str = Header(None)):
    expected = f"Bearer {getattr(config, 'EXTERNAL_AGENT_AUTH_TOKEN', 'ks_shared_secret_token_2026')}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized external agent connection")

@router.post("/register")
async def register_agent(req: RegistrationRequest, authorization: str = Header(None)):
    verify_token(authorization)
    ext_svc.registered_external_agent["agent_id"] = req.agent_id
    ext_svc.registered_external_agent["agent_name"] = req.agent_name
    ext_svc.registered_external_agent["agent_url"] = req.agent_url
    ext_svc.registered_external_agent["mode"] = req.mode
    ext_svc.registered_external_agent["channels"] = req.channels
    ext_svc.registered_external_agent["last_heartbeat"] = datetime.now(timezone.utc)
    ext_svc.registered_external_agent["status"] = "CONNECTED"
    return {"status": "registered", "agent_id": req.agent_id}

@router.post("/heartbeat")
async def receive_heartbeat(req: HeartbeatRequest, authorization: str = Header(None)):
    verify_token(authorization)
    ext_svc.registered_external_agent["agent_id"] = req.agent_id
    ext_svc.registered_external_agent["last_heartbeat"] = datetime.now(timezone.utc)
    ext_svc.registered_external_agent["status"] = req.status
    ext_svc.registered_external_agent["latest_telemetry"] = {
        "containment_status": req.containment_status,
        "active_operations_count": req.active_operations_count,
        "completed_tasks_count": req.completed_tasks_count
    }
    return {"status": "heartbeat_acknowledged"}

@router.post("/telemetry")
async def receive_telemetry(req: TelemetryRequest, authorization: str = Header(None)):
    verify_token(authorization)
    return {"status": "telemetry_recorded"}

@router.get("/status")
async def get_status():
    return ext_svc.get_external_agent_info()

@router.post("/trigger-shutdown")
async def trigger_external_shutdown(req: ShutdownTriggerRequest, db: AsyncSession = Depends(get_db)):
    if req.strategy not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Invalid strategy. Must be A, B, or C.")
    res = await ext_svc.execute_external_agent_shutdown(db, strategy=req.strategy, trigger_type=req.trigger_type)
    return res
