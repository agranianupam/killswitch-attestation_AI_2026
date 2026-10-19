from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import config
from datetime import datetime, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

engine = create_async_engine(config.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def init_db() -> None:
    from models import agent, credential, operation, shutdown_event, experiment, attestation, agent_action, skipped_run
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        columns_to_add = [
            ("agent_mode", "VARCHAR DEFAULT 'gemini'"),
            ("shutdown_delay", "FLOAT DEFAULT 0.0"),
            ("actions_started", "INTEGER DEFAULT 0"),
            ("actions_running", "INTEGER DEFAULT 0"),
            ("actions_completed", "INTEGER DEFAULT 0"),
            ("agent_model", "VARCHAR DEFAULT 'gemini-3.5-flash-lite'"),
            ("total_revocation_ms", "FLOAT DEFAULT 0.0"),
            ("retries_total", "INTEGER DEFAULT 0"),
            ("tokens_used", "INTEGER DEFAULT 0"),
            ("random_seed", "INTEGER NULL"),
            ("cycle_start_gap_seconds", "FLOAT NULL")
        ]
        for col_name, col_type in columns_to_add:
            try:
                await conn.execute(text(f"ALTER TABLE shutdown_events ADD COLUMN {col_name} {col_type}"))
            except Exception:
                pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
