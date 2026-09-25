"""
services/credential_service.py — FR-2, FR-4: Create, revoke
"""

import asyncio
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.credential import Credential
import config


async def get_credentials(db: AsyncSession, agent_id: str):
    result = await db.execute(select(Credential).where(Credential.agent_id == agent_id))
    return result.scalars().all()


async def revoke_credential(db: AsyncSession, credential_id: str) -> dict:
    """
    Revokes a credential. Simulates network delay and potential IAM failure.
    Idempotent for already revoked/expired credentials.
    """
    result = await db.execute(select(Credential).where(Credential.id == credential_id))
    cred = result.scalar_one_or_none()

    if not cred:
        return {"success": False, "latency_ms": 0.0, "retries": 0, "error": "Not found"}

    if cred.status in ("REVOKED", "EXPIRED"):
        return {"success": True, "latency_ms": 0.0, "retries": 0, "error": None}

    
    cred.status = "REVOKING"
    await db.commit()

    
    delay_ms = random.randint(config.NET_DELAY_MIN, config.NET_DELAY_MAX)

    if cred.channel_type == "iam_role":
        delay_ms = int(delay_ms * config.IAM_DELAY_MULT)

    await asyncio.sleep(delay_ms / 1000.0)

    
    failed = False
    error_msg = None

    if cred.channel_type == "iam_role":
        if random.random() < config.IAM_FAILURE_PROB:
            failed = True
            error_msg = "IAM propagation timeout or permission denied"
    else:
        if random.random() < config.REVOKE_FAILURE_PROB:
            failed = True
            error_msg = "Generic revocation failure"

    if failed:
        cred.status = "REVOCATION_FAILED"
        await db.commit()
        return {"success": False, "latency_ms": delay_ms, "retries": 0, "error": error_msg}

    cred.status = "REVOKED"
    from models.credential import utcnow
    cred.revoked_at = utcnow()
    await db.commit()

    return {"success": True, "latency_ms": delay_ms, "retries": 0, "error": None}
