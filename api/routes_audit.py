from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import get_db
from models.attestation import AuditLog, AttestationEntry
from services.crypto_service import verify_chain, load_public_key
from services.export_service import export_signed_report

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("/entries")
async def get_attestation_entries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AttestationEntry).order_by(AttestationEntry.created_at.asc()))
    entries = result.scalars().all()
    return [
        {
            "index": idx,
            "entry_index": idx,
            "id": e.id,
            "entry_hash": e.entry_hash,
            "current_hash": e.entry_hash,
            "prev_hash": e.prev_hash,
            "previous_hash": e.prev_hash,
            "signature": e.signature,
            "shutdown_event_id": e.shutdown_event_id,
            "event_id": e.shutdown_event_id,
            "timestamp": e.created_at.isoformat() if e.created_at else None,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "payload_json": e.payload_json
        } for idx, e in enumerate(entries)
    ]

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

import re

@router.get("/export/{event_id}", response_class=PlainTextResponse)
async def api_export_report(event_id: str, db: AsyncSession = Depends(get_db)):
    if not re.match(r"^[a-zA-Z0-9_\-]+$", event_id):
        raise HTTPException(status_code=400, detail="Invalid event ID format")
    report_content = await export_signed_report(db, event_id)
    if report_content.startswith("No attestation entry or event found"):
        raise HTTPException(status_code=404, detail="Attestation report not found for the requested event ID")
    return PlainTextResponse(
        content=report_content,
        headers={"Content-Disposition": f'attachment; filename="killswitch_attestation_{event_id}.md"'}
    )
