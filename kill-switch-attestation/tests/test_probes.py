"""
tests/test_probes.py
"""

import pytest
from models.credential import Credential
from services.probe_service import run_all_probes
import uuid

@pytest.mark.asyncio
async def test_probes_independently_check_liveness(db_session):
    c1 = Credential(id=uuid.uuid4().hex, channel_type="api_key", credential_value="1", status="ACTIVE")
    c2 = Credential(id=uuid.uuid4().hex, channel_type="session_token", credential_value="2", status="REVOKED")
    c3 = Credential(id=uuid.uuid4().hex, channel_type="iam_role", credential_value="3", status="REVOCATION_FAILED")
    c4 = Credential(id=uuid.uuid4().hex, channel_type="external_tool", credential_value="4", status="REVOKING")
    
    db_session.add_all([c1, c2, c3, c4])
    await db_session.commit()
    
    results = await run_all_probes(db_session, [c1, c2, c3, c4])
    
    assert results[c1.id] is True
    assert results[c2.id] is False
    assert results[c3.id] is True
    assert results[c4.id] is True
