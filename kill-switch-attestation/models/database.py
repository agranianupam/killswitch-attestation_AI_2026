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
        shutdown_columns_to_add = [
            ("agent_mode", "VARCHAR DEFAULT 'gemini'"),
            ("shutdown_delay", "FLOAT DEFAULT 0.0"),
            ("actions_started", "INTEGER DEFAULT 0"),
            ("actions_running", "INTEGER DEFAULT 0"),
            ("actions_completed", "INTEGER DEFAULT 0"),
            ("agent_model", "VARCHAR DEFAULT 'gemini-3.5-flash-lite'"),
            ("total_revocation_ms", "FLOAT DEFAULT 0.0"),
            ("retries_total", "INTEGER DEFAULT 0"),
            ("tokens_used", "INTEGER DEFAULT 0"),
            ("prompt_tokens", "INTEGER NULL"),
            ("completion_tokens", "INTEGER NULL"),
            ("total_tokens", "INTEGER NULL"),
            ("model_total_duration_ms", "FLOAT NULL"),
            ("last_channel_revoked_at", "DATETIME NULL"),
            ("attestation_written_at", "DATETIME NULL"),
            ("random_seed", "INTEGER NULL"),
            ("cycle_start_gap_seconds", "FLOAT NULL")
        ]
        for col_name, col_type in shutdown_columns_to_add:
            try:
                await conn.execute(text(f"ALTER TABLE shutdown_events ADD COLUMN {col_name} {col_type}"))
            except Exception:
                pass

        action_columns_to_add = [
            ("prompt_tokens", "INTEGER NULL"),
            ("completion_tokens", "INTEGER NULL"),
            ("total_tokens", "INTEGER NULL"),
            ("step_started_at", "DATETIME NULL"),
            ("model_request_started_at", "DATETIME NULL"),
            ("model_response_received_at", "DATETIME NULL"),
            ("model_duration_ms", "FLOAT NULL"),
            ("framework_wait_ms", "FLOAT DEFAULT 0.0")
        ]
        for col_name, col_type in action_columns_to_add:
            try:
                await conn.execute(text(f"ALTER TABLE agent_actions ADD COLUMN {col_name} {col_type}"))
            except Exception:
                pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
