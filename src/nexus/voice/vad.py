"""
NEXUS Voice — Voice Activity Detection (VAD).

Detects speech start/end in an audio stream using Silero VAD with an
energy-based pre-filter to reduce CPU usage. Falls back to a simple
energy-based detector if Silero is unavailable.
"""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any

import numpy as np

from nexus.utils.events import get_event_bus
from nexus.utils.logging import get_logger

log = get_logger("voice.vad")


class VADState(StrEnum):
    """Current state of the voice activity detector."""

    IDLE = "idle"
    SPEECH = "speech"
    SILENCE = "silence"


class VoiceActivityDetector:
    """
    Detects voice activity in a stream of audio chunks.

    Uses Silero VAD for high-accuracy speech detection with an energy-based
    pre-filter to skip obvious silence cheaply. Falls back to energy-only
    detection if Silero is unavailable.

    Usage:
        vad = VoiceActivityDetector(sample_rate=16000)
        vad.start()

        # Feed audio chunks from AudioRecorder
        for chunk in audio_chunks:
            result = vad.process_chunk(chunk)
            if result == VADState.SPEECH:
                # Speech detected, accumulate audio
                ...
            elif result == VADState.SILENCE:
                # End of speech detected
                speech_audio = vad.get_speech_segment()
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        silence_threshold_ms: int = 1500,
        min_speech_ms: int = 250,
        energy_threshold: int = 300,
    ) -> None:
        """
        Args:
            sample_rate: Audio sample rate in Hz.
            threshold: Silero VAD confidence threshold (0.0–1.0).
            silence_threshold_ms: How long silence must last to end speech.
            min_speech_ms: Minimum speech duration to trigger a segment.
            energy_threshold: RMS energy below this is considered silence.
        """
        self._sample_rate = sample_rate
        self._threshold = threshold
        self._silence_threshold_ms = silence_threshold_ms
        self._min_speech_ms = min_speech_ms
        self._energy_threshold = energy_threshold

        self._state = VADState.IDLE
        self._speech_chunks: list[np.ndarray] = []
        self._speech_start_time: float | None = None
        self._last_speech_time: float | None = None

        self._silero_model = None
        self._use_silero = False
        self._event_bus = get_event_bus()

        self._load_vad_model()

    def _load_vad_model(self) -> None:
        """Attempt to load the Silero VAD model."""
        try:
            import importlib

            torch: Any = importlib.import_module("torch")

            hub_load_fn: Any = torch.hub.load
            hub_result: Any = hub_load_fn(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo="check",
                verbose=False,
            )
            if isinstance(hub_result, (tuple, list)):
                self._silero_model = hub_result[0]
            else:
                self._silero_model = hub_result
            self._use_silero = True
            log.info("Silero VAD model loaded successfully")
        except Exception as e:
            log.warning("Silero VAD unavailable (%s), using energy-based detection", e)
            self._use_silero = False

    def _compute_energy(self, chunk: np.ndarray) -> float:
        """Compute the RMS energy of an audio chunk."""
        if chunk.dtype == np.int16:
            chunk_float = chunk.astype(np.float32) / 32768.0
        else:
            chunk_float = chunk.astype(np.float32)
        return float(np.sqrt(np.mean(chunk_float**2)) * 32768)

    def _run_silero(self, chunk: np.ndarray) -> float:
        """Run Silero VAD on a chunk, returning the speech probability."""
        if not self._use_silero or self._silero_model is None:
            return 0.0

        try:
            import importlib

            torch: Any = importlib.import_module("torch")

            if chunk.dtype == np.int16:
                chunk_float = chunk.astype(np.float32) / 32768.0
            else:
                chunk_float = chunk.astype(np.float32)

            tensor = torch.from_numpy(chunk_float)
            # Silero VAD expects 512 samples at 16kHz (32ms windows)
            # Process in windows if chunk is larger
            window_size = 512
            if len(tensor) < window_size:
                # Pad short chunks
                tensor = torch.nn.functional.pad(tensor, (0, window_size - len(tensor)))
            if len(tensor) > window_size:
                # Use the last window
                tensor = tensor[-window_size:]

            prob = self._silero_model(tensor, self._sample_rate).item()
            return prob
        except Exception as e:
            log.debug("Silero VAD error: %s", e)
            return 0.0

    def process_chunk(self, chunk: np.ndarray) -> VADState:
        """
        Process an audio chunk and return the current VAD state.

        Args:
            chunk: Audio samples as numpy array.

        Returns:
            Current VAD state (IDLE, SPEECH, or SILENCE).
        """
        now = time.time()
        energy = self._compute_energy(chunk)

        # Energy pre-filter: skip Silero for obvious silence
        if energy < self._energy_threshold:
            is_speech = False
        elif self._use_silero:
            prob = self._run_silero(chunk)
            is_speech = prob >= self._threshold
        else:
            # Fallback: pure energy-based detection
            is_speech = energy >= self._energy_threshold * 2

        if is_speech:
            self._last_speech_time = now

            if self._state != VADState.SPEECH:
                # Transition to speech
                self._state = VADState.SPEECH
                self._speech_start_time = now
                self._speech_chunks = []
                log.debug("VAD: Speech started (energy=%.0f)", energy)

            self._speech_chunks.append(chunk.copy())
            return VADState.SPEECH

        else:
            if self._state == VADState.SPEECH:
                # Still accumulate silence chunks (might be a pause)
                self._speech_chunks.append(chunk.copy())

                # Check if silence has lasted long enough to end speech
                if self._last_speech_time is not None:
                    silence_duration_ms = (now - self._last_speech_time) * 1000
                    if (
                        silence_duration_ms >= self._silence_threshold_ms
                        and self._speech_start_time is not None
                    ):
                        speech_duration_ms = (now - self._speech_start_time) * 1000
                        if speech_duration_ms >= self._min_speech_ms:
                            self._state = VADState.SILENCE
                            log.debug(
                                "VAD: Speech ended (duration=%.0fms)",
                                speech_duration_ms,
                            )
                            return VADState.SILENCE
                        else:
                            # Too short, discard
                            self._state = VADState.IDLE
                            self._speech_chunks = []
                            return VADState.IDLE

                return VADState.SPEECH  # Still in speech, waiting for silence

            return VADState.IDLE

    def get_speech_segment(self) -> np.ndarray | None:
        """
        Get the accumulated speech segment after VAD detects end of speech.

        Returns:
            Concatenated audio of the speech segment, or None if no speech.
        """
        if not self._speech_chunks:
            return None

        segment = np.concatenate(self._speech_chunks)
        self._speech_chunks = []
        self._state = VADState.IDLE
        self._speech_start_time = None
        return segment

    def reset(self) -> None:
        """Reset the VAD state."""
        import contextlib

        self._state = VADState.IDLE
        self._speech_chunks = []
        self._speech_start_time = None
        self._last_speech_time = None

        # Reset Silero model state if loaded
        if self._silero_model is not None:
            with contextlib.suppress(Exception):
                self._silero_model.reset_states()

    @property
    def state(self) -> VADState:
        return self._state

    @property
    def is_speech(self) -> bool:
        return self._state == VADState.SPEECH

    @property
    def uses_silero(self) -> bool:
        return self._use_silero
