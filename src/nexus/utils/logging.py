"""
NEXUS Logging System.

Provides structured, colored console output and file logging using Python's
built-in logging module enhanced with Rich for beautiful terminal output.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

if sys.platform == "win32":
    reconfig_out = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig_out):
        with contextlib.suppress(Exception):
            reconfig_out(encoding="utf-8", errors="replace")
    reconfig_err = getattr(sys.stderr, "reconfigure", None)
    if callable(reconfig_err):
        with contextlib.suppress(Exception):
            reconfig_err(encoding="utf-8", errors="replace")

NEXUS_THEME = Theme(
    {
        "nexus.info": "cyan",
        "nexus.success": "bold green",
        "nexus.warning": "bold yellow",
        "nexus.error": "bold red",
        "nexus.tool": "bold magenta",
        "nexus.thinking": "dim italic",
        "nexus.user": "bold white",
        "nexus.agent": "bold cyan",
        "nexus.system": "dim white",
    }
)

console = Console(theme=NEXUS_THEME, safe_box=True, legacy_windows=False)

# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------

_configured = False


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
) -> logging.Logger:
    """
    Configure the NEXUS logging system.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to a log file for persistent logging.

    Returns:
        The root 'nexus' logger instance.
    """
    global _configured
    if _configured:
        return logging.getLogger("nexus")

    log_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger("nexus")
    logger.setLevel(log_level)
    logger.propagate = False

    # --- Rich console handler (beautiful terminal output) ---
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
        log_time_format="[%H:%M:%S]",
    )
    rich_handler.setLevel(log_level)
    rich_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(rich_handler)

    # --- File handler (structured, for debugging) ---
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "chromadb", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True
    logger.debug("NEXUS logging initialized (level=%s)", level)
    return logger


def get_logger(name: str = "nexus") -> logging.Logger:
    """
    Get a child logger under the 'nexus' namespace.

    Usage:
        log = get_logger(__name__)
        log.info("Something happened")
    """
    if not _configured:
        setup_logging()
    if name.startswith("nexus."):
        return logging.getLogger(name)
    return logging.getLogger(f"nexus.{name}")


# ---------------------------------------------------------------------------
# Pretty-print helpers used by the CLI and UI
# ---------------------------------------------------------------------------


def print_user(text: str) -> None:
    """Print a user message to the console."""
    console.print(f"[nexus.user]You:[/] {text}")


def print_agent(text: str) -> None:
    """Print an agent (NEXUS) response to the console."""
    console.print(f"[nexus.agent]NEXUS:[/] {text}")


def print_thinking(text: str) -> None:
    """Print a thinking/reasoning step (dimmed)."""
    console.print(f"[nexus.thinking]  💭 {text}[/]")


def print_tool(tool_name: str, status: str = "executing") -> None:
    """Print a tool execution notification."""
    icon = "⚡" if status == "executing" else "✅" if status == "done" else "❌"
    console.print(f"[nexus.tool]  {icon} Tool: {tool_name} ({status})[/]")


def print_system(text: str) -> None:
    """Print a system message (dimmed)."""
    console.print(f"[nexus.system]  ℹ {text}[/]")


def print_error(text: str) -> None:
    """Print an error message."""
    console.print(f"[nexus.error]  ✖ Error: {text}[/]")


def print_success(text: str) -> None:
    """Print a success message."""
    console.print(f"[nexus.success]  ✔ {text}[/]")


def print_warning(text: str) -> None:
    """Print a warning message."""
    console.print(f"[nexus.warning]  ⚠ {text}[/]")
