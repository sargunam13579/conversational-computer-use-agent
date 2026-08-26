"""
NEXUS — Application Entry Point.

Initializes all subsystems and starts the appropriate interface:
  - API mode (default): FastAPI server with REST endpoints
  - CLI mode: Interactive terminal chat interface
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from nexus.core.config import load_settings
from nexus.database.engine import close_engine, init_engine
from nexus.utils.logging import get_logger, setup_logging


async def _startup() -> None:
    """Initialize all NEXUS subsystems."""
    # Load configuration
    settings = load_settings()

    # Setup logging
    log_file = settings.resolved_data_dir / "logs" / settings.log_file
    setup_logging(level=settings.log_level, log_file=log_file)

    log = get_logger("main")
    log.info("Starting NEXUS v%s", settings.version)

    # Initialize database
    actual_db_url = f"sqlite+aiosqlite:///{settings.resolved_data_dir / 'nexus.db'}"
    await init_engine(actual_db_url, echo=settings.database.echo)


async def _shutdown() -> None:
    """Clean up all NEXUS subsystems."""
    log = get_logger("main")
    log.info("Shutting down NEXUS...")
    await close_engine()
    log.info("NEXUS stopped")


async def async_main_cli() -> None:
    """Async entry point for CLI mode."""
    try:
        await _startup()

        # Run the CLI interface
        from nexus.cli import run_cli

        await run_cli()

    except KeyboardInterrupt:
        pass
    finally:
        await _shutdown()


def run_api_server() -> None:
    """Start the FastAPI server using uvicorn."""
    import uvicorn

    from nexus.core.config import load_settings

    settings = load_settings()

    uvicorn.run(
        "nexus.api.app:create_app",
        factory=True,
        host=settings.api.host,
        port=settings.api.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


def main() -> None:
    """Synchronous entry point (called from `nexus` command)."""
    parser = argparse.ArgumentParser(
        prog="nexus",
        description="NEXUS — Voice-first, cross-device personal AI agent",
    )
    parser.add_argument(
        "--mode",
        choices=["api", "cli"],
        default="api",
        help="Run mode: 'api' starts the REST API server (default), 'cli' starts the interactive terminal.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Override the API server host (e.g., '0.0.0.0').",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override the API server port (e.g., 8080).",
    )

    args = parser.parse_args()

    if args.mode == "cli":
        try:
            asyncio.run(async_main_cli())
        except KeyboardInterrupt:
            print("\nGoodbye!")
            sys.exit(0)
    else:
        # API mode
        import uvicorn

        from nexus.core.config import load_settings

        settings = load_settings()

        host = args.host or settings.api.host
        port = args.port or settings.api.port

        uvicorn.run(
            "nexus.api.app:create_app",
            factory=True,
            host=host,
            port=port,
            log_level=settings.log_level.lower(),
            reload=False,
        )


if __name__ == "__main__":
    main()
