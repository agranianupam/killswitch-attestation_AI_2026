import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from services.crypto_service import ensure_keys_exist, load_public_key, load_private_key, sign_test_result, verify_signature, append_to_chain, verify_chain
from schemas.contracts import TestResult
from models.database import Base
from models.attestation import AttestationEntry

def test_crypto_signature_verification():
    ensure_keys_exist()
    tr = TestResult(
        timestamp=datetime.now(timezone.utc),
        revocation_latency_ms=100.5,
        leaked_channels=[],
        in_flight_failures=0
    )
    payload_json = tr.model_dump_json(indent=None)
    sig = sign_test_result(tr)
    pub_key = load_public_key()
    assert verify_signature(payload_json, sig, pub_key) is True
    tampered_payload = payload_json.replace("100.5", "100.6")
    assert verify_signature(tampered_payload, sig, pub_key) is False

def test_verify_with_private_key_raises():
    ensure_keys_exist()
    priv_key = load_private_key()
    with pytest.raises(TypeError):
        verify_signature("{}", b"dummy", priv_key)

@pytest.mark.asyncio
async def test_chain_tamper_detection():
    ensure_keys_exist()
    pub_key = load_public_key()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        e1 = await append_to_chain(db, "ev-1", '{"step": 1}', "abcd1234"*8)
        assert e1.prev_hash == "GENESIS"
        e2 = await append_to_chain(db, "ev-2", '{"step": 2}', "beef5678"*8)
        assert e2.prev_hash == e1.entry_hash

        res = await verify_chain(db, pub_key)
        assert res["valid"] is False
        assert res["first_failure_index"] == 0

        tr1 = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=50.0, leaked_channels=[], in_flight_failures=0)
        sig1 = sign_test_result(tr1).hex()
        tr2 = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=60.0, leaked_channels=[], in_flight_failures=0)
        sig2 = sign_test_result(tr2).hex()

    engine2 = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session2 = sessionmaker(engine2, expire_on_commit=False, class_=AsyncSession)
    async with engine2.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session2() as db2:
        entry1 = await append_to_chain(db2, "ev-10", tr1.model_dump_json(), sig1)
        entry2 = await append_to_chain(db2, "ev-20", tr2.model_dump_json(), sig2)
        valid_res = await verify_chain(db2, pub_key)
        assert valid_res["valid"] is True
        assert valid_res["entries_checked"] == 2

        entry2.payload_json = '{"tampered": true}'
        await db2.commit()

        tampered_res = await verify_chain(db2, pub_key)
        assert tampered_res["valid"] is False
        assert tampered_res["first_failure_index"] == 1
