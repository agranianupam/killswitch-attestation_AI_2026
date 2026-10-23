from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from services.alert_service import get_alerts, acknowledge_alert, clear_all_alerts, get_alerts_summary, get_active_critical_incident

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

class AlertAckResponse(BaseModel):
    success: bool
    status: str = "acknowledged"
    message: str

@router.get("/critical/active")
async def get_active_critical():
    incident = await get_active_critical_incident()
    return {"incident": incident, "alert": incident, "has_active_critical": incident is not None}

@router.get("")
async def list_alerts(
    limit: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    unacknowledged_only: bool = Query(False)
):
    alerts = await get_alerts(
        limit=limit,
        severity=severity,
        category=category,
        unacknowledged_only=unacknowledged_only
    )
    return {"alerts": alerts, "count": len(alerts)}

@router.get("/summary")
async def alerts_summary():
    return await get_alerts_summary()

@router.post("/{alert_id}/ack", response_model=AlertAckResponse)
async def ack_alert(alert_id: str):
    clean_id = alert_id.replace("incident_", "").strip()
    success = await acknowledge_alert(clean_id)
    if not success:
        from services.alert_service import acknowledge_alerts_by_experiment
        success = await acknowledge_alerts_by_experiment(clean_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"success": True, "status": "acknowledged", "message": f"Alert {alert_id} acknowledged"}

@router.post("/clear", response_model=AlertAckResponse)
async def clear_alerts():
    count = await clear_all_alerts()
    return {"success": True, "message": f"{count} alerts acknowledged"}
