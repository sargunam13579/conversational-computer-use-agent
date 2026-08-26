"""
NEXUS Test Configuration.

Shared fixtures and configuration for the test suite.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio

# Set test environment before importing nexus modules
os.environ["NEXUS_ENV"] = "test"
os.environ["NEXUS_LOG_LEVEL"] = "DEBUG"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db(tmp_path: Path):
    """Provide a temporary test database."""
    from nexus.database.engine import close_engine, init_engine

    db_path = tmp_path / "test_nexus.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    engine = await init_engine(db_url, echo=False)
    yield engine
    await close_engine()


@pytest.fixture
def tool_registry():
    """Provide a fresh ToolRegistry."""
    from nexus.tools.registry import ToolRegistry

    return ToolRegistry()


@pytest.fixture
def starter_tools():
    """Provide all starter tools."""
    from nexus.tools.system.basic import get_starter_tools

    return get_starter_tools()
