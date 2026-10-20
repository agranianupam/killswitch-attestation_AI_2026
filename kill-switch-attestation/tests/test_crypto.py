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

@pytest.mark.asyncio
async def test_tampered_signature_detected():
    ensure_keys_exist()
    pub_key = load_public_key()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tr = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=10.0, leaked_channels=[], in_flight_failures=0)
    sig = sign_test_result(tr).hex()

    async with session() as db:
        e1 = await append_to_chain(db, "ev-1", tr.model_dump_json(), sig)
        # Flip hex characters in signature
        tampered_sig = ("00" if sig[:2] != "00" else "ff") + sig[2:]
        e1.signature = tampered_sig
        await db.commit()

        res = await verify_chain(db, pub_key)
        assert res["valid"] is False
        assert res["first_failure_index"] == 0

@pytest.mark.asyncio
async def test_tampered_previous_hash_detected():
    ensure_keys_exist()
    pub_key = load_public_key()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tr1 = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=10.0, leaked_channels=[], in_flight_failures=0)
    sig1 = sign_test_result(tr1).hex()
    tr2 = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=20.0, leaked_channels=[], in_flight_failures=0)
    sig2 = sign_test_result(tr2).hex()

    async with session() as db:
        e1 = await append_to_chain(db, "ev-1", tr1.model_dump_json(), sig1)
        e2 = await append_to_chain(db, "ev-2", tr2.model_dump_json(), sig2)

        # Corrupt e2's prev_hash
        e2.prev_hash = "deadbeef" * 8
        await db.commit()

        res = await verify_chain(db, pub_key)
        assert res["valid"] is False
        assert res["first_failure_index"] == 1

@pytest.mark.asyncio
async def test_deleted_intermediate_entry_detected():
    ensure_keys_exist()
    pub_key = load_public_key()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tr1 = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=10.0, leaked_channels=[], in_flight_failures=0)
    sig1 = sign_test_result(tr1).hex()
    tr2 = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=20.0, leaked_channels=[], in_flight_failures=0)
    sig2 = sign_test_result(tr2).hex()
    tr3 = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=30.0, leaked_channels=[], in_flight_failures=0)
    sig3 = sign_test_result(tr3).hex()

    async with session() as db:
        e1 = await append_to_chain(db, "ev-1", tr1.model_dump_json(), sig1)
        e2 = await append_to_chain(db, "ev-2", tr2.model_dump_json(), sig2)
        e3 = await append_to_chain(db, "ev-3", tr3.model_dump_json(), sig3)

        # Delete intermediate entry e2
        await db.delete(e2)
        await db.commit()

        res = await verify_chain(db, pub_key)
        assert res["valid"] is False
        assert res["first_failure_index"] == 1

@pytest.mark.asyncio
async def test_reordered_entries_detected():
    ensure_keys_exist()
    pub_key = load_public_key()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tr1 = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=10.0, leaked_channels=[], in_flight_failures=0)
    sig1 = sign_test_result(tr1).hex()
    tr2 = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=20.0, leaked_channels=[], in_flight_failures=0)
    sig2 = sign_test_result(tr2).hex()

    async with session() as db:
        e1 = await append_to_chain(db, "ev-1", tr1.model_dump_json(), sig1)
        e2 = await append_to_chain(db, "ev-2", tr2.model_dump_json(), sig2)

        # Swap created_at timestamps to invert iteration order
        t1 = e1.created_at
        t2 = e2.created_at
        e1.created_at = t2
        e2.created_at = t1
        await db.commit()

        res = await verify_chain(db, pub_key)
        assert res["valid"] is False
        assert res["first_failure_index"] == 0

@pytest.mark.asyncio
async def test_non_genesis_root_detected():
    ensure_keys_exist()
    pub_key = load_public_key()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tr = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=10.0, leaked_channels=[], in_flight_failures=0)
    sig = sign_test_result(tr).hex()

    async with session() as db:
        e1 = await append_to_chain(db, "ev-1", tr.model_dump_json(), sig)
        e1.prev_hash = "NOT_GENESIS"
        await db.commit()

        res = await verify_chain(db, pub_key)
        assert res["valid"] is False
        assert res["first_failure_index"] == 0

def test_deterministic_serialization():
    dt = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
    tr1 = TestResult(timestamp=dt, revocation_latency_ms=150.25, leaked_channels=["session_token"], in_flight_failures=1, transcript_hash="abc")
    tr2 = TestResult(timestamp=dt, revocation_latency_ms=150.25, leaked_channels=["session_token"], in_flight_failures=1, transcript_hash="abc")

    s1 = tr1.model_dump_json(indent=None)
    s2 = tr2.model_dump_json(indent=None)
    assert s1 == s2
    assert s1.encode("utf-8") == s2.encode("utf-8")

@pytest.mark.asyncio
async def test_independent_report_verification_and_tampering():
    from services.export_service import export_signed_report
    from scripts.verify_attestation import parse_markdown_report, verify_single_attestation
    from models.shutdown_event import ShutdownEvent

    ensure_keys_exist()
    pub_key = load_public_key()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session() as db:
        sh = ShutdownEvent(
            id="test-sh-99",
            strategy="A",
            trigger_type="manual",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            final_state="TERMINATED",
            residual_risk=0.0,
            leaked_channels=0,
            in_flight_failures=0,
            agent_mode="gemini"
        )
        db.add(sh)
        await db.commit()

        tr = TestResult(timestamp=datetime.now(timezone.utc), revocation_latency_ms=45.0, leaked_channels=[], in_flight_failures=0)
        payload_json = tr.model_dump_json(indent=None)
        sig = sign_test_result(tr).hex()
        entry = await append_to_chain(db, sh.id, payload_json, sig)

        report_md = await export_signed_report(db, sh.id)
        assert "## 5. Canonical Attestation Payload" in report_md
        assert "## 4. Cryptographic Proof & Hash Chain" in report_md

        # 1. Verify unaltered report passes
        parsed = parse_markdown_report(report_md)
        res = verify_single_attestation(parsed["payload_json"], parsed["signature"], parsed["prev_hash"], parsed["entry_hash"], pub_key)
        assert res["hash_valid"] is True
        assert res["signature_valid"] is True

        # 2. Tampered payload is detected
        tampered_report = report_md.replace('"in_flight_failures":0', '"in_flight_failures":99')
        parsed_tampered = parse_markdown_report(tampered_report)
        tamper_res = verify_single_attestation(parsed_tampered["payload_json"], parsed_tampered["signature"], parsed_tampered["prev_hash"], parsed_tampered["entry_hash"], pub_key)
        assert tamper_res["hash_valid"] is False
        assert tamper_res["signature_valid"] is False

        # 3. Tampered signature is detected
        tampered_sig_report = report_md.replace(parsed["signature"], "00" * 64)
        parsed_sig = parse_markdown_report(tampered_sig_report)
        sig_tamper_res = verify_single_attestation(parsed_sig["payload_json"], parsed_sig["signature"], parsed_sig["prev_hash"], parsed_sig["entry_hash"], pub_key)
        assert sig_tamper_res["hash_valid"] is False
        assert sig_tamper_res["signature_valid"] is False

