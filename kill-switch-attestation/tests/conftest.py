"""
tests/conftest.py — In-memory DB, TestClient, fixtures
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi.testclient import TestClient
from models.database import Base, get_db


import config
config.DATABASE_URL = "sqlite+aiosqlite:///./test_killswitch.db"
config.NET_DELAY_MIN = 0
config.NET_DELAY_MAX = 0
config.IAM_FAILURE_PROB = 0.0
config.REVOKE_FAILURE_PROB = 0.0

engine = create_async_engine(config.DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

import models.database
models.database.engine = engine
models.database.AsyncSessionLocal = TestingSessionLocal

@pytest_asyncio.fixture(scope="function", autouse=True)
def reset_config():
    config.NET_DELAY_MIN = 0
    config.NET_DELAY_MAX = 0
    config.IAM_FAILURE_PROB = 0.0
    config.REVOKE_FAILURE_PROB = 0.0

@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def client(db_session):
    from main import app
    
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
