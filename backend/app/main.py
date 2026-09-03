from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from .config import get_settings
from .api import (
    activities_router,
    agent_router,
    auth_router,
    conversations_router,
    engagement_router,
    feedback_router,
    matches_router,
    users_router,
)
from .database import SessionLocal, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.validate_runtime()
    if settings.data_backend == "cloudbase_http":
        with SessionLocal() as db:
            db.healthcheck()
    else:
        inspector = inspect(engine)
        required_tables = {
            "users",
            "agent_sessions",
            "agent_traces",
            "partner_requests",
            "notifications",
        }
        missing_tables = required_tables - set(inspector.get_table_names())
        session_columns = (
            {column["name"] for column in inspector.get_columns("agent_sessions")}
            if "agent_sessions" not in missing_tables
            else set()
        )
        missing_session_columns = {
            "active_turn_id",
            "lock_expires_at",
        } - session_columns
        if missing_tables or missing_session_columns:
            raise RuntimeError(
                "database schema is not at the Agent persistence head; "
                "run `alembic upgrade head` before starting the API"
            )
    from .agents import TraceStore
    from .memory import MemoryManager

    with SessionLocal() as db:
        MemoryManager(db).cleanup_expired_sessions()
        TraceStore(db).cleanup_expired_traces()
    try:
        yield
    finally:
        if settings.data_backend == "sqlite":
            engine.dispose()


app = FastAPI(
    title="校园搭子 AI Agent",
    description="可解释、可追踪、确定性匹配的校园交友 Agent MVP",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(engagement_router)
app.include_router(agent_router)
app.include_router(matches_router)
app.include_router(feedback_router)
app.include_router(activities_router)


@app.get("/__tcb_probe__", include_in_schema=False)
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
