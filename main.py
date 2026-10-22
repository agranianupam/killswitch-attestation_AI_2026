from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from models.database import init_db
from services.crypto_service import ensure_keys_exist
from services.operation_service import start_operation_loop, stop_operation_loop
from services.scheduler_service import start_scheduler, stop_scheduler
import config

from api.routes_agent import router as agent_router
from api.routes_shutdown import router as shutdown_router
from api.routes_scheduler import router as scheduler_router
from api.routes_experiment import router as experiment_router
from api.routes_audit import router as audit_router
from api.routes_analytics import router as analytics_router
from api.routes_alert import router as alert_router
from api.routes_adversarial import router as adversarial_router
from api.routes_external_agent import router as external_agent_router
from api.websocket import router as ws_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    ensure_keys_exist()
    sched_mode = getattr(config, "SCHED_MODE", "poisson")
    start_scheduler(mode=sched_mode, strategy="A")
    yield
    stop_operation_loop()
    stop_scheduler()

app = FastAPI(lifespan=lifespan, title="Kill-Switch Attestation System")

app.include_router(agent_router)
app.include_router(shutdown_router)
app.include_router(scheduler_router)
app.include_router(experiment_router)
app.include_router(audit_router)
app.include_router(analytics_router)
app.include_router(alert_router)
app.include_router(adversarial_router)
app.include_router(external_agent_router)
app.include_router(ws_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import os
    import uvicorn
    host = os.getenv("KS_HOST", "127.0.0.1")
    port = int(os.getenv("KS_PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
