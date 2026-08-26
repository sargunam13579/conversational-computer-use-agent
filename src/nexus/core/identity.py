"""
NEXUS Core — Identity & Wake Word Management.

Manages assistant name, wake words, aliases, and persistent identity settings.
Provides secure persistence to disk and triggers events on identity changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from nexus.utils.events import get_event_bus
from nexus.utils.logging import get_logger

log = get_logger("core.identity")

DEFAULT_ASSISTANT_NAME = "NEXUS"
DEFAULT_WAKE_WORD = "NEXUS"
DEFAULT_PREFIXES = ["hey", "ok", "okay", "hi", "hello"]


class IdentityConfig(BaseModel):
    """Configuration for assistant identity and wake words."""

    assistant_name: str = Field(
        default=DEFAULT_ASSISTANT_NAME,
        description="Primary assistant name.",
    )
    user_name: str = Field(default="User", description="User's display name.")
    wake_word: str = Field(default=DEFAULT_WAKE_WORD, description="Primary wake word.")
    aliases: list[str] = Field(
        default_factory=list,
        description="Secondary names and aliases that also trigger the assistant.",
    )
    wake_word_prefixes: list[str] = Field(
        default_factory=lambda: list(DEFAULT_PREFIXES),
        description="Prefix words that can precede the wake word (e.g., 'hey', 'ok').",
    )
    require_wake_word: bool = Field(
        default=False,
        description="Whether voice processing requires a wake word before executing commands.",
    )


class IdentityManager:
    """
    Manages assistant identity, wake word configuration, aliases, and storage.

    Persists identity settings to disk (`~/.nexus/identity.json` or custom path)
    so changes survive restarts.
    """

    def __init__(
        self,
        storage_path: Path | str | None = None,
        config: IdentityConfig | None = None,
    ) -> None:
        if storage_path is not None:
            self._storage_path = Path(storage_path)
        else:
            # Default to ~/.nexus/identity.json
            self._storage_path = Path.home() / ".nexus" / "identity.json"

        self._event_bus = get_event_bus()

        if config is not None:
            self._config = config
        else:
            self._config = self._load()

    @property
    def config(self) -> IdentityConfig:
        """Get the current identity config."""
        return self._config

    @property
    def name(self) -> str:
        """Current assistant name."""
        return self._config.assistant_name

    @property
    def wake_word(self) -> str:
        """Primary wake word."""
        return self._config.wake_word

    @property
    def aliases(self) -> list[str]:
        """List of secondary aliases."""
        return list(self._config.aliases)

    @property
    def user_name(self) -> str:
        """User's display name."""
        return self._config.user_name

    @property
    def all_wake_words(self) -> list[str]:
        """
        All recognized trigger names: primary wake word + aliases.

        Returns unique, normalized trigger names.
        """
        words = [self._config.wake_word]
        if self._config.assistant_name not in words:
            words.append(self._config.assistant_name)
        for alias in self._config.aliases:
            if alias and alias not in words:
                words.append(alias)
        return words

    def set_name(self, new_name: str, sync_wake_word: bool = True) -> None:
        """
        Change the assistant's name and optionally sync the primary wake word.

        Args:
            new_name: The new assistant name (e.g. 'Aria').
            sync_wake_word: If True, updates primary wake word to match new name.
        """
        clean_name = new_name.strip()
        if not clean_name:
            raise ValueError("Assistant name cannot be empty.")

        old_name = self._config.assistant_name
        self._config.assistant_name = clean_name

        if sync_wake_word:
            self._config.wake_word = clean_name

        self._save()
        log.info("Assistant name changed from '%s' to '%s'", old_name, clean_name)

        # Notify listeners
        self._event_bus.emit_sync(
            "identity.name_changed",
            {"old_name": old_name, "new_name": clean_name, "wake_word": self._config.wake_word},
            source="identity_manager",
        )

    def set_wake_word(self, wake_word: str) -> None:
        """
        Change the primary wake word.

        Args:
            wake_word: The new wake word.
        """
        clean = wake_word.strip()
        if not clean:
            raise ValueError("Wake word cannot be empty.")

        old = self._config.wake_word
        self._config.wake_word = clean
        self._save()
        log.info("Wake word changed from '%s' to '%s'", old, clean)

        self._event_bus.emit_sync(
            "identity.wake_word_changed",
            {"old_wake_word": old, "new_wake_word": clean},
            source="identity_manager",
        )

    def add_alias(self, alias: str) -> bool:
        """
        Add a secondary name/alias if not already present.

        Returns True if added, False if already present.
        """
        clean = alias.strip()
        if not clean:
            return False

        # Case-insensitive check
        if any(a.lower() == clean.lower() for a in self._config.aliases):
            return False

        self._config.aliases.append(clean)
        self._save()
        log.info("Added alias '%s'", clean)

        self._event_bus.emit_sync(
            "identity.alias_added",
            {"alias": clean, "all_aliases": self._config.aliases},
            source="identity_manager",
        )
        return True

    def remove_alias(self, alias: str) -> bool:
        """
        Remove an alias.

        Returns True if removed, False if not found.
        """
        clean = alias.strip().lower()
        initial_len = len(self._config.aliases)
        self._config.aliases = [a for a in self._config.aliases if a.lower() != clean]

        if len(self._config.aliases) < initial_len:
            self._save()
            log.info("Removed alias '%s'", alias)
            self._event_bus.emit_sync(
                "identity.alias_removed",
                {"alias": alias, "all_aliases": self._config.aliases},
                source="identity_manager",
            )
            return True
        return False

    def set_user_name(self, user_name: str) -> None:
        """Update the user's name."""
        self._config.user_name = user_name.strip()
        self._save()

    def set_require_wake_word(self, required: bool) -> None:
        """Toggle whether wake word is required in voice processing."""
        self._config.require_wake_word = required
        self._save()

    def update(self, **kwargs: Any) -> None:
        """Update multiple identity settings at once."""
        if "assistant_name" in kwargs and kwargs["assistant_name"]:
            self._config.assistant_name = kwargs["assistant_name"].strip()
        if "user_name" in kwargs and kwargs["user_name"]:
            self._config.user_name = kwargs["user_name"].strip()
        if "wake_word" in kwargs and kwargs["wake_word"]:
            self._config.wake_word = kwargs["wake_word"].strip()
        if "aliases" in kwargs and isinstance(kwargs["aliases"], list):
            self._config.aliases = [str(a).strip() for a in kwargs["aliases"] if str(a).strip()]
        if "wake_word_prefixes" in kwargs and isinstance(kwargs["wake_word_prefixes"], list):
            self._config.wake_word_prefixes = [
                str(p).strip() for p in kwargs["wake_word_prefixes"] if str(p).strip()
            ]
        if "require_wake_word" in kwargs:
            self._config.require_wake_word = bool(kwargs["require_wake_word"])

        self._save()
        log.info("Identity updated: %s", self._config.model_dump())

    def _load(self) -> IdentityConfig:
        """Load identity config from storage file, or return defaults."""
        if self._storage_path.exists():
            try:
                data = json.loads(self._storage_path.read_text(encoding="utf-8"))
                return IdentityConfig.model_validate(data)
            except Exception as e:
                log.warning(
                    "Failed to load identity file %s: %s. Using defaults.",
                    self._storage_path,
                    e,
                )
        return IdentityConfig()

    def _save(self) -> None:
        """Save identity config to storage file."""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            content = json.dumps(self._config.model_dump(), indent=2)
            self._storage_path.write_text(content, encoding="utf-8")
        except Exception as e:
            log.error("Failed to save identity to %s: %s", self._storage_path, e)
