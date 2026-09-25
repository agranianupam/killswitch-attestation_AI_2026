"""
models/database.py — Engine, session, Base, and init_db.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import config
from datetime import datetime, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

engine = create_async_engine(config.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables if they don't exist."""
    
    from models import agent, credential, operation, shutdown_event, experiment, attestation  
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        yield session
