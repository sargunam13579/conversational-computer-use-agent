"""
NEXUS Voice — Dynamic Wake-Word Detection.

Provides wake-word extraction, prefix handling ('Hey', 'OK', 'Hi'),
alias matching, and command separation from speech or text input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nexus.utils.logging import get_logger

log = get_logger("voice.wake_word")

DEFAULT_PREFIXES = ["hey", "ok", "okay", "hi", "hello"]


@dataclass
class WakeWordMatch:
    """Result of wake-word detection."""

    matched: bool
    wake_word: str = ""
    prefix: str | None = None
    command: str = ""
    raw_text: str = ""

    @property
    def has_command(self) -> bool:
        """Whether a command was provided along with the wake word."""
        return bool(self.command.strip())


class WakeWordDetector:
    """
    Detects wake words and extracts commands from speech or text.

    Supports:
      - Direct trigger: "<WakeWord>, <command>" (e.g. "Nexus, open Chrome")
      - Prefixed trigger: "Hey <WakeWord>, <command>" (e.g. "Hey Aria, what time is it?")
      - Trailing trigger: "<command>, <WakeWord>" (e.g. "Open Chrome, Nexus")
      - Standalone wake word: "Nexus" or "Hey Nexus"
      - Dynamic aliases and customized assistant names.
    """

    def __init__(
        self,
        wake_words: list[str] | None = None,
        prefixes: list[str] | None = None,
    ) -> None:
        self._wake_words = [w.strip() for w in (wake_words or ["NEXUS"]) if w.strip()]
        self._prefixes = [p.strip().lower() for p in (prefixes or DEFAULT_PREFIXES) if p.strip()]

    @property
    def wake_words(self) -> list[str]:
        return list(self._wake_words)

    @wake_words.setter
    def wake_words(self, words: list[str]) -> None:
        self._wake_words = [w.strip() for w in words if w.strip()]

    @property
    def prefixes(self) -> list[str]:
        return list(self._prefixes)

    @prefixes.setter
    def prefixes(self, prefixes: list[str]) -> None:
        self._prefixes = [p.strip().lower() for p in prefixes if p.strip()]

    def update_wake_words(self, primary: str, aliases: list[str] | None = None) -> None:
        """Update the list of active wake words and aliases."""
        words = [primary.strip()]
        if aliases:
            for a in aliases:
                clean = a.strip()
                if clean and clean not in words:
                    words.append(clean)
        self._wake_words = words

    def detect(self, text: str) -> WakeWordMatch:
        """
        Check if text starts or ends with any configured wake word and extract command.

        Args:
            text: Transcribed speech or user text input.

        Returns:
            WakeWordMatch instance with detection details.
        """
        raw = text.strip()
        if not raw:
            return WakeWordMatch(matched=False, raw_text=text)

        # Try matching each wake word
        for ww in self._wake_words:
            match = self._match_wake_word(raw, ww)
            if match.matched:
                return match

        return WakeWordMatch(matched=False, raw_text=text)

    def _match_wake_word(self, text: str, wake_word: str) -> WakeWordMatch:
        """Match a specific wake word against the input text."""
        ww_escaped = re.escape(wake_word)
        prefixes_pattern = "|".join(re.escape(p) for p in self._prefixes)

        # 1. Prefixed trigger at start: e.g., "Hey Nexus, open Chrome" or "OK Nexus"
        pattern_prefix = (
            rf"^(?P<prefix>{prefixes_pattern})\s+{ww_escaped}(?:[,\s:!-]+(?P<cmd>.*))?$"
        )
        m = re.match(pattern_prefix, text, re.IGNORECASE)
        if m:
            prefix_val = m.group("prefix")
            cmd = m.group("cmd") or ""
            return WakeWordMatch(
                matched=True,
                wake_word=wake_word,
                prefix=prefix_val.lower() if prefix_val else None,
                command=cmd.strip(" ,.!?:\t\n"),
                raw_text=text,
            )

        # 2. Direct trigger at start: e.g., "Nexus, open Chrome" or "Nexus"
        pattern_direct = rf"^{ww_escaped}(?:[,\s:!-]+(?P<cmd>.*))?$"
        m = re.match(pattern_direct, text, re.IGNORECASE)
        if m:
            cmd = m.group("cmd") or ""
            return WakeWordMatch(
                matched=True,
                wake_word=wake_word,
                prefix=None,
                command=cmd.strip(" ,.!?:\t\n"),
                raw_text=text,
            )

        # 3. Trailing trigger at end: e.g., "Open Chrome, Nexus" or "Open Chrome, hey Nexus"
        pattern_trailing = (
            rf"^(?P<cmd>.+?)[,\s:!-]+(?:(?P<prefix>{prefixes_pattern})\s+)?{ww_escaped}[.!?\s]*$"
        )
        m = re.match(pattern_trailing, text, re.IGNORECASE)
        if m:
            cmd = m.group("cmd") or ""
            prefix_val = m.group("prefix")
            return WakeWordMatch(
                matched=True,
                wake_word=wake_word,
                prefix=prefix_val.lower() if prefix_val else None,
                command=cmd.strip(" ,.!?:\t\n"),
                raw_text=text,
            )

        return WakeWordMatch(matched=False, raw_text=text)

    def extract_command_or_original(self, text: str) -> tuple[bool, str]:
        """
        Helper that returns (matched, command_or_original_text).

        If wake word matched, returns (True, extracted_command).
        If not matched, returns (False, text).
        """
        match = self.detect(text)
        if match.matched:
            return True, match.command if match.has_command else ""
        return False, text
