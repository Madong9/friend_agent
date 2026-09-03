"""SQLAlchemy engine and session lifecycle."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(url: str) -> Engine:
    connect_args = (
        {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    )
    new_engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if url.startswith("sqlite"):

        @event.listens_for(new_engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return new_engine


engine = build_engine(get_settings().database_url)
SqlSessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def SessionLocal() -> Session | Any:
    """Create the configured unit of work.

    Local development keeps a regular SQLAlchemy/SQLite Session. CloudBase PG
    shared clusters use an HTTP/PostgREST adapter with the same narrow session
    surface consumed by the existing services and Agent tools.
    """

    settings = get_settings()
    if settings.data_backend == "cloudbase_http":
        from .repositories.cloudbase_http import CloudBaseHttpSession

        return CloudBaseHttpSession.from_settings(settings)
    return SqlSessionLocal()


def get_db() -> Generator[Session | Any, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
