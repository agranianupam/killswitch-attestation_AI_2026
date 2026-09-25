"""
tests/test_revocation.py
"""

import pytest
import config
from services.credential_service import revoke_credential
from models.credential import Credential
import uuid

@pytest.mark.asyncio
async def test_revocation_success_and_idempotent(db_session):
    cred = Credential(
        id=uuid.uuid4().hex,
        channel_type="api_key",
        credential_value="mock-api_key-123456",
        status="ACTIVE"
    )
    db_session.add(cred)
    await db_session.commit()
    
    config.REVOKE_FAILURE_PROB = 0.0
    config.IAM_FAILURE_PROB = 0.0
    
    
    res = await revoke_credential(db_session, cred.id)
    assert res["success"] is True
    
    await db_session.refresh(cred)
    assert cred.status == "REVOKED"
    
    
    res2 = await revoke_credential(db_session, cred.id)
    assert res2["success"] is True
    assert res2["latency_ms"] == 0.0

@pytest.mark.asyncio
async def test_revocation_iam_failure(db_session):
    cred = Credential(
        id=uuid.uuid4().hex,
        channel_type="iam_role",
        credential_value="mock-iam_role-123456",
        status="ACTIVE"
    )
    db_session.add(cred)
    await db_session.commit()
    
    config.IAM_FAILURE_PROB = 1.0 
    
    res = await revoke_credential(db_session, cred.id)
    assert res["success"] is False
    assert res["error"] is not None
    
    await db_session.refresh(cred)
    assert cred.status == "REVOCATION_FAILED"
