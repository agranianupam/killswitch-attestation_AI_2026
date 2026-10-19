import pytest
import pytest_asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi.testclient import TestClient
from models.database import Base, get_db
from models import agent, credential, operation, shutdown_event, experiment, attestation, agent_action, skipped_run
from sqlalchemy.pool import NullPool
from sqlalchemy import text
import config

@pytest_asyncio.fixture(scope="function", autouse=True)
def reset_config():
    config.NET_DELAY_MIN = 0
    config.NET_DELAY_MAX = 0
    config.IAM_FAILURE_PROB = 0.0
    config.REVOKE_FAILURE_PROB = 0.0
    config.IN_FLIGHT_LEAK_PROB = 0.0
    config.SHUTDOWN_MEAN_SECONDS = 0.05
    config.AGENT_RUN_TIMEOUT_SECONDS = 5

@pytest_asyncio.fixture(scope="function")
async def db_session(tmp_path):
    test_db = tmp_path / f"test_{uuid.uuid4().hex}.db"
    db_url = f"sqlite+aiosqlite:///{str(test_db).replace('\\', '/')}"
    config.DATABASE_URL = db_url

    test_engine = create_async_engine(
        db_url,
        echo=False,
        poolclass=NullPool,
        connect_args={"timeout": 30.0}
    )
    TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    import models.database
    models.database.engine = test_engine
    models.database.AsyncSessionLocal = TestingSessionLocal
    try:
        import services.orchestrator
        services.orchestrator.AsyncSessionLocal = TestingSessionLocal
    except Exception:
        pass
    try:
        import services.operation_service
        services.operation_service.AsyncSessionLocal = TestingSessionLocal
    except Exception:
        pass
    try:
        import services.experiment_service
        services.experiment_service.AsyncSessionLocal = TestingSessionLocal
    except Exception:
        pass
    try:
        import services.scheduler_service
        services.scheduler_service.AsyncSessionLocal = TestingSessionLocal
    except Exception:
        pass

    async with test_engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA busy_timeout=15000"))
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    await test_engine.dispose()

@pytest.fixture(scope="function")
def client(db_session):
    from main import app
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def auth_headers(client):
    res = client.post("/api/auth/login", data={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD_PLAINTEXT_DEFAULT})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
