from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from services.alert_service import get_alerts, acknowledge_alert, clear_all_alerts, get_alerts_summary

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

class AlertAckResponse(BaseModel):
    success: bool
    message: str

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
    success = await acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"success": True, "message": f"Alert {alert_id} acknowledged"}

@router.post("/clear", response_model=AlertAckResponse)
async def clear_alerts():
    count = await clear_all_alerts()
    return {"success": True, "message": f"{count} alerts acknowledged"}
