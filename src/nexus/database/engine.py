"""
NEXUS Database Engine.

Manages the async SQLAlchemy engine and session factory for SQLite.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from nexus.utils.logging import get_logger

log = get_logger("database.engine")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _resolve_db_url(url: str) -> str:
    """Resolve ~ and env vars in the database URL."""
    if ":///" in url:
        prefix, path = url.rsplit(":///", 1)
        resolved = os.path.expandvars(os.path.expanduser(path))
        # Ensure parent directory exists
        Path(resolved).parent.mkdir(parents=True, exist_ok=True)
        return f"{prefix}:///{resolved}"
    return url


async def init_engine(db_url: str, echo: bool = False) -> AsyncEngine:
    """
    Initialize the async SQLAlchemy engine.

    Args:
        db_url: SQLAlchemy async database URL.
        echo: If True, log all SQL statements.

    Returns:
        The initialized AsyncEngine.
    """
    global _engine, _session_factory

    resolved_url = _resolve_db_url(db_url)
    log.info("Initializing database: %s", resolved_url.split("///")[-1])

    _engine = create_async_engine(
        resolved_url,
        echo=echo,
        pool_pre_ping=True,
        # SQLite-specific: enable WAL mode for better concurrent access
        connect_args={"check_same_thread": False},
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create all tables
    from nexus.database.models import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    log.info("Database initialized successfully")
    return _engine


async def close_engine() -> None:
    """Close the database engine and release connections."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        log.info("Database engine closed")


def get_engine() -> AsyncEngine:
    """Return the current engine, raising if not initialized."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    return _engine


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async database session as a context manager.

    Usage:
        async with get_session() as session:
            result = await session.execute(select(User))
    """
    if _session_factory is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
