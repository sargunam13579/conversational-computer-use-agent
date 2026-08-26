"""
NEXUS Voice Navigation & Screen Reader Accessibility Subsystem.

Provides voice-first navigation mappings, verbal text-to-speech formatting
for visual layouts/tables, and high-visibility themes for hands-free operation.
"""

from __future__ import annotations

import re
from typing import Any

from nexus.utils.logging import get_logger

log = get_logger("accessibility.navigation")


class VoiceNavigationEngine:
    """
    Translates complex visual data and UI elements into natural speech descriptions
    and maps physical button/UI interactions to direct voice intents.
    """

    @staticmethod
    def format_for_screen_reader(text: str) -> str:
        """
        Strip markdown symbols, ASCII tables, and formatting artifacts
        into clean, speakable text for screen readers and TTS engines.
        """
        if not text:
            return ""

        # Remove ANSI color codes
        cleaned = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)

        # Remove markdown link syntax [text](url) -> text
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)

        # Remove markdown header hashes
        cleaned = re.sub(r"^#{1,6}\s*", "", cleaned, flags=re.MULTILINE)

        # Remove markdown bold/italics
        cleaned = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", cleaned)

        # Remove markdown code ticks
        cleaned = re.sub(r"`{1,3}", "", cleaned)

        # Remove horizontal rules
        cleaned = re.sub(r"^[-\*_]{3,}\s*$", "", cleaned, flags=re.MULTILINE)

        # Normalize multiple newlines
        cleaned = re.sub(r"\n{2,}", "\n. ", cleaned)

        return cleaned.strip()

    @staticmethod
    def format_plan_for_voice(plan_goal: str, total_steps: int, current_step_index: int, current_step_desc: str) -> str:
        """
        Generate a concise verbal progress announcement for multi-step task execution.
        """
        step_num = current_step_index + 1
        return (
            f"Goal: {plan_goal}. Now executing step {step_num} of {total_steps}: {current_step_desc}."
        )

    @staticmethod
    def format_status_for_voice(status_dict: dict[str, Any]) -> str:
        """
        Converts system diagnostics into natural speech.
        """
        parts = []
        if "battery" in status_dict:
            bat = status_dict["battery"]
            percent = bat.get("percent", 100)
            plugged = "plugged in" if bat.get("power_plugged") else "on battery"
            parts.append(f"Battery is at {percent} percent, {plugged}.")

        if "cpu_percent" in status_dict:
            parts.append(f"CPU utilization is {status_dict['cpu_percent']} percent.")

        if "paired_devices" in status_dict:
            count = len(status_dict["paired_devices"])
            parts.append(f"{count} paired device{'s' if count != 1 else ''} connected.")

        return " ".join(parts) if parts else "All systems operating normally."
