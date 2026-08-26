"""
NEXUS Audio Feedback & Earcon Subsystem.

Provides non-visual auditory feedback, state change earcons,
and accessibility sound cues for hands-free operation.
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from enum import StrEnum

from nexus.utils.logging import get_logger

log = get_logger("accessibility.audio")

# Optional winsound on Windows
try:
    import winsound
except ImportError:
    winsound = None  # type: ignore[assignment]


class EarconType(StrEnum):
    """Audio cue types representing agent state changes."""

    WAKE = "wake"  # Assistant activated / listening
    SUCCESS = "success"  # Action completed successfully
    ERROR = "error"  # Action failed / error occurred
    CONFIRMATION_REQUIRED = "confirmation"  # Risky action requires confirmation
    EMERGENCY_STOP = "emergency_stop"  # Kill switch triggered
    PROCESSING = "processing"  # Multi-step task progressing


@dataclass
class ToneSpec:
    """Frequency and duration specification for synthesised earcon."""

    frequency_hz: int
    duration_ms: int


_EARCON_TONES: dict[EarconType, list[ToneSpec]] = {
    EarconType.WAKE: [ToneSpec(600, 100), ToneSpec(900, 150)],
    EarconType.SUCCESS: [ToneSpec(523, 100), ToneSpec(659, 100), ToneSpec(784, 150)],
    EarconType.ERROR: [ToneSpec(300, 200), ToneSpec(220, 250)],
    EarconType.CONFIRMATION_REQUIRED: [ToneSpec(440, 150), ToneSpec(880, 150)],
    EarconType.EMERGENCY_STOP: [ToneSpec(1000, 100), ToneSpec(600, 100), ToneSpec(1000, 100), ToneSpec(600, 150)],
    EarconType.PROCESSING: [ToneSpec(700, 80)],
}


class AudioFeedbackManager:
    """
    Emits earcons and audio chimes to confirm actions without requiring screen visual attention.
    """

    def __init__(self, enabled: bool = False, volume: float = 1.0) -> None:
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))

    def play_earcon(self, earcon_type: EarconType | str, async_play: bool = True) -> None:
        """
        Play an earcon sound cue.
        """
        if not self.enabled:
            return

        if isinstance(earcon_type, str):
            try:
                earcon_type = EarconType(earcon_type)
            except ValueError:
                earcon_type = EarconType.SUCCESS

        tones = _EARCON_TONES.get(earcon_type, [ToneSpec(440, 100)])

        if async_play:
            thread = threading.Thread(target=self._play_tones, args=(tones,), daemon=True)
            thread.start()
        else:
            self._play_tones(tones)

    def _play_tones(self, tones: list[ToneSpec]) -> None:
        try:
            if winsound is not None and sys.platform == "win32":
                for t in tones:
                    winsound.Beep(t.frequency_hz, t.duration_ms)
            else:
                # Terminal bell fallback on non-Windows/headless
                sys.stdout.write("\a")
                sys.stdout.flush()
        except Exception as e:
            log.debug("Audio feedback tone playback skipped: %s", e)

    def on_wake(self) -> None:
        """Shortcut for wake sound."""
        self.play_earcon(EarconType.WAKE)

    def on_success(self) -> None:
        """Shortcut for success chime."""
        self.play_earcon(EarconType.SUCCESS)

    def on_error(self) -> None:
        """Shortcut for error tone."""
        self.play_earcon(EarconType.ERROR)

    def on_confirmation(self) -> None:
        """Shortcut for confirmation alert."""
        self.play_earcon(EarconType.CONFIRMATION_REQUIRED)

    def on_emergency_stop(self) -> None:
        """Shortcut for emergency stop tone."""
        self.play_earcon(EarconType.EMERGENCY_STOP)
