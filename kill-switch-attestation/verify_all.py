import asyncio
import uuid
import json
from models.database import init_db, AsyncSessionLocal, engine, Base
from models.agent import Agent
from services.agent_service import seed_demo_agent
from services.crypto_service import ensure_keys_exist, load_public_key, verify_chain
from services.orchestrator import run_shutdown
from services.export_service import export_signed_report
from models.attestation import AttestationEntry
from sqlalchemy import select
from datetime import datetime, timezone
import config

import os
import tempfile
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

async def main():
    # Setup test DB in isolated temp file
    temp_dir = tempfile.gettempdir()
    db_file = os.path.join(temp_dir, f"verify_test_{uuid.uuid4().hex}.db")
    db_url = f"sqlite+aiosqlite:///{db_file.replace(os.sep, '/')}"
    config.DATABASE_URL = db_url

    test_engine = create_async_engine(db_url, echo=False, poolclass=NullPool)
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    import models.database
    models.database.engine = test_engine
    models.database.AsyncSessionLocal = TestSessionLocal

    for mod_name in ["services.orchestrator", "services.operation_service", "services.experiment_service", "services.scheduler_service"]:
        try:
            mod = __import__(mod_name, fromlist=["AsyncSessionLocal"])
            mod.AsyncSessionLocal = TestSessionLocal
        except Exception:
            pass

    await init_db()
    ensure_keys_exist()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as db:
        agent = await seed_demo_agent(db)
        
    print("--- 1. Hash-Chain Verification ---")
    try:
        # Run two shutdowns to create a chain
        async with TestSessionLocal() as db:
            res1 = await run_shutdown(db, agent.id, "A", "manual")

        async with TestSessionLocal() as db:
            # Re-seed to have active credentials
            agent2 = await seed_demo_agent(db)
            res2 = await run_shutdown(db, agent2.id, "B", "manual")

        async with TestSessionLocal() as db:
            pub_key = load_public_key()
            chain_res = await verify_chain(db, pub_key)
            print(f"[Normal Chain] Valid: {chain_res['valid']}, Entries Checked: {chain_res['entries_checked']}")
            assert chain_res["valid"] is True

            # Tamper with the first entry
            result = await db.execute(select(AttestationEntry).order_by(AttestationEntry.created_at))
            entries = result.scalars().all()
            entry_to_tamper = entries[0]

            # Tamper payload
            payload = json.loads(entry_to_tamper.payload_json)
            payload["leaked_channels"] = ["fake_leak"]
            entry_to_tamper.payload_json = json.dumps(payload)
            await db.commit()

            chain_res_tampered = await verify_chain(db, pub_key)
            print(f"[Tampered Chain] Valid: {chain_res_tampered['valid']}, Failed at index: {chain_res_tampered['first_failure_index']}")
            assert chain_res_tampered["valid"] is False

        print("\n--- 2. Signed Audit Export ---")
        async with TestSessionLocal() as db:
            report = await export_signed_report(db, res2["shutdown_event_id"])
            print("Generated Report Preview:")
            print("-" * 40)
            print("\n".join(report.split("\n")[:15]))
            print("...")
            print("-" * 40)
            assert "VERIFIED" in report or "Verified" in report
            assert res2["shutdown_event_id"] in report

        print("\n--- 3. Scheduler Verification ---")
        from services.scheduler_service import start_scheduler, stop_scheduler, get_scheduler_status

        start_scheduler("poisson", "A")
        status = get_scheduler_status()
        print(f"Scheduler Status (Started): {status['running']}, Mode: {status['mode']}")
        assert status["running"] is True

        stop_scheduler()
        status = get_scheduler_status()
        print(f"Scheduler Status (Stopped): {status['running']}")
        assert status["running"] is False

        print("\nAll verifications passed!")
    finally:
        await test_engine.dispose()
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass

if __name__ == "__main__":
    asyncio.run(main())
