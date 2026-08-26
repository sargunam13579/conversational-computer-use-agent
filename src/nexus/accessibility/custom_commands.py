"""
NEXUS Custom Voice Commands & Aliases Subsystem.

Allows users to define custom voice shortcuts and compound macros
to trigger multi-step workflows with single hands-free phrases.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nexus.utils.logging import get_logger

log = get_logger("accessibility.commands")


@dataclass
class CustomCommand:
    """A user-defined custom command mapping a trigger phrase to actions."""

    phrase: str
    actions: list[str]
    description: str = ""
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    match_exact: bool = False


class CustomCommandManager:
    """
    Manages custom voice phrases and macro expansion.
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        if storage_path is None:
            home = Path.home()
            self.storage_path = home / ".nexus" / "custom_commands.json"
        else:
            self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._commands: dict[str, CustomCommand] = {}
        self._load_defaults()
        self._load()

    def _load_defaults(self) -> None:
        """Seed initial helpful accessibility voice macros."""
        defaults = [
            CustomCommand(
                phrase="morning routine",
                actions=["check battery status", "read notifications", "open browser"],
                description="Starts morning routine by checking status and opening browser.",
            ),
            CustomCommand(
                phrase="focus mode",
                actions=["set volume to 20 percent", "close distracting tabs"],
                description="Lowers volume and minimizes distractions for deep work.",
            ),
            CustomCommand(
                phrase="wrap up day",
                actions=["save open files", "report battery status"],
                description="End-of-day summary and status check.",
            ),
        ]
        for cmd in defaults:
            self._commands[cmd.phrase.lower()] = cmd

    def _load(self) -> None:
        if not self.storage_path.exists():
            self._save()
            return
        try:
            raw = self.storage_path.read_text(encoding="utf-8")
            if not raw.strip():
                return
            data = json.loads(raw)
            for item in data.get("commands", []):
                cmd = CustomCommand(**item)
                self._commands[cmd.phrase.lower()] = cmd
        except Exception as e:
            log.warning("Could not load custom commands: %s", e)

    def _save(self) -> None:
        try:
            payload = {
                "version": "1.0",
                "updated_at": time.time(),
                "commands": [asdict(c) for c in self._commands.values()],
            }
            self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if os.name != "nt":
                os.chmod(self.storage_path, 0o600)
        except Exception as e:
            log.error("Failed to save custom commands: %s", e)

    def register_command(
        self,
        phrase: str,
        actions: list[str] | str,
        description: str = "",
        match_exact: bool = False,
    ) -> CustomCommand:
        """Register or update a custom command."""
        action_list = [actions] if isinstance(actions, str) else list(actions)
        norm_phrase = phrase.strip().lower()
        cmd = CustomCommand(
            phrase=norm_phrase,
            actions=action_list,
            description=description or f"Custom shortcut for '{phrase}'",
            match_exact=match_exact,
        )
        self._commands[norm_phrase] = cmd
        self._save()
        log.info("Registered custom voice command: '%s' -> %d action(s)", norm_phrase, len(action_list))
        return cmd

    def remove_command(self, phrase: str) -> bool:
        """Remove a custom command."""
        norm = phrase.strip().lower()
        if norm in self._commands:
            del self._commands[norm]
            self._save()
            log.info("Removed custom command: '%s'", norm)
            return True
        return False

    def list_commands(self) -> list[CustomCommand]:
        """List all registered custom commands."""
        return list(self._commands.values())

    def match_and_expand(self, user_input: str) -> list[str] | None:
        """
        Check if user input matches a custom command.
        If matched, returns the expanded list of sub-actions; otherwise None.
        """
        text = user_input.strip().lower()
        if not text:
            return None

        # 1. Exact match
        if text in self._commands and self._commands[text].enabled:
            return list(self._commands[text].actions)

        # 2. Substring match
        for phrase, cmd in self._commands.items():
            if not cmd.enabled:
                continue
            if cmd.match_exact:
                if text == phrase:
                    return list(cmd.actions)
            else:
                pattern = r"\b" + re.escape(phrase) + r"\b"
                if re.search(pattern, text):
                    return list(cmd.actions)

        return None
