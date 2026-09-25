"""
main.py — Lifespan, routers, static mount
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from models.database import init_db
from models.database import AsyncSessionLocal
from services.agent_service import seed_demo_agent
from services.crypto_service import ensure_keys_exist
from services.operation_service import start_operation_loop, stop_operation_loop
from services.scheduler_service import stop_scheduler

from api.auth import router as auth_router
from api.routes_agent import router as agent_router
from api.routes_shutdown import router as shutdown_router
from api.routes_scheduler import router as scheduler_router
from api.routes_experiment import router as experiment_router
from api.routes_audit import router as audit_router
from api.routes_analytics import router as analytics_router
from api.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    await init_db()
    
    
    ensure_keys_exist()
    
    
    async with AsyncSessionLocal() as db:
        await seed_demo_agent(db)
        
    
    start_operation_loop()
    
    yield
    
    
    stop_operation_loop()
    stop_scheduler()
    
app = FastAPI(lifespan=lifespan, title="Kill-Switch Attestation System")

app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(shutdown_router)
app.include_router(scheduler_router)
app.include_router(experiment_router)
app.include_router(audit_router)
app.include_router(analytics_router)
app.include_router(ws_router)

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
