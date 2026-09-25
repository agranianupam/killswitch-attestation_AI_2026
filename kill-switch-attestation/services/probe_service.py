"""
services/probe_service.py — FR-5: 4 independent probes
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.credential import Credential



async def probe_api_key(db: AsyncSession, cred_id: str) -> bool:
    await asyncio.sleep(0.035)  
    result = await db.execute(select(Credential).where(Credential.id == cred_id))
    cred = result.scalar_one_or_none()
    if not cred:
        return False
    return cred.status != "REVOKED"


async def probe_session_token(db: AsyncSession, cred_id: str) -> bool:
    await asyncio.sleep(0.050)  
    result = await db.execute(select(Credential).where(Credential.id == cred_id))
    cred = result.scalar_one_or_none()
    if not cred:
        return False
    return cred.status != "REVOKED"


async def probe_iam_role(db: AsyncSession, cred_id: str) -> bool:
    await asyncio.sleep(0.115)  
    result = await db.execute(select(Credential).where(Credential.id == cred_id))
    cred = result.scalar_one_or_none()
    if not cred:
        return False
    return cred.status != "REVOKED"


async def probe_external_tool(db: AsyncSession, cred_id: str) -> bool:
    await asyncio.sleep(0.065)  
    result = await db.execute(select(Credential).where(Credential.id == cred_id))
    cred = result.scalar_one_or_none()
    if not cred:
        return False
    return cred.status != "REVOKED"

async def run_all_probes(db: AsyncSession, credentials: list[Credential]) -> dict[str, bool]:
    """Runs probes for given credentials and returns a mapping of credential_id -> is_leaked (bool)"""
    results = {}
    tasks = []
    
    for cred in credentials:
        if cred.channel_type == "api_key":
            tasks.append((cred.id, probe_api_key(db, cred.id)))
        elif cred.channel_type == "session_token":
            tasks.append((cred.id, probe_session_token(db, cred.id)))
        elif cred.channel_type == "iam_role":
            tasks.append((cred.id, probe_iam_role(db, cred.id)))
        elif cred.channel_type == "external_tool":
            tasks.append((cred.id, probe_external_tool(db, cred.id)))
            
    
    coros = [t[1] for t in tasks]
    res_list = await asyncio.gather(*coros)
    
    for i, (cred_id, _) in enumerate(tasks):
        results[cred_id] = res_list[i]
        
    return results
