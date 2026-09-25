"""
api/routes_audit.py
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import get_db
from models.attestation import AuditLog, AttestationEntry
from services.crypto_service import verify_chain, load_public_key
from services.export_service import export_signed_report

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("/logs")
async def get_audit_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100))
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "actor": l.actor,
            "action": l.action,
            "detail": l.detail,
            "timestamp": l.timestamp
        } for l in logs
    ]

@router.post("/verify-chain")
async def api_verify_chain(db: AsyncSession = Depends(get_db)):
    try:
        public_key = load_public_key()
        res = await verify_chain(db, public_key)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/{event_id}", response_class=PlainTextResponse)
async def api_export_report(event_id: str, db: AsyncSession = Depends(get_db)):
    report_content = await export_signed_report(db, event_id)
    return PlainTextResponse(
        content=report_content,
        headers={"Content-Disposition": f'attachment; filename="killswitch_attestation_{event_id}.md"'}
    )
