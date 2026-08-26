"""
NEXUS Voice — Audio I/O.

Manages microphone input capture and speaker output playback using sounddevice.
Provides thread-safe, callback-based audio streaming for real-time processing.
"""

from __future__ import annotations

import asyncio
import io
import queue
import threading
import wave
from collections.abc import Callable
from typing import Any

import numpy as np

from nexus.utils.logging import get_logger

log = get_logger("voice.audio_io")

# Type alias for audio callbacks
AudioCallback = Callable[[np.ndarray], None]


class AudioRecorder:
    """
    Captures microphone audio into a thread-safe queue.

    Uses sounddevice's InputStream with a callback to push audio chunks
    to consumers in real time. Audio is captured as 16-bit PCM, mono,
    at the configured sample rate (default 16kHz).
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration_ms: int = 30,
        dtype: str = "int16",
    ) -> None:
        """
        Args:
            sample_rate: Audio sample rate in Hz.
            channels: Number of audio channels (1 = mono).
            chunk_duration_ms: Duration of each audio chunk in milliseconds.
            dtype: NumPy dtype for audio samples.
        """
        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self._dtype = dtype
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: Any = None
        self._is_recording = False
        self._callbacks: list[AudioCallback] = []
        self._lock = threading.Lock()

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info: Any, status: Any
    ) -> None:
        """Sounddevice callback — pushes audio chunks to the queue."""
        if status:
            log.warning("Audio input status: %s", status)
        chunk = indata.copy().flatten()
        self._audio_queue.put(chunk)
        for cb in self._callbacks:
            try:
                cb(chunk)
            except Exception as e:
                log.error("Audio callback error: %s", e)

    def add_callback(self, callback: AudioCallback) -> None:
        """Register a callback to receive audio chunks."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: AudioCallback) -> None:
        """Remove a previously registered callback."""
        import contextlib

        with contextlib.suppress(ValueError):
            self._callbacks.remove(callback)

    def start(self) -> None:
        """Start recording from the microphone."""
        if self._is_recording:
            return

        try:
            import sounddevice as sd
        except ImportError as err:
            raise RuntimeError(
                "sounddevice is required for voice input. "
                "Install with: pip install nexus-agent[voice]"
            ) from err

        with self._lock:
            try:
                self._stream = sd.InputStream(
                    samplerate=self._sample_rate,
                    channels=self._channels,
                    dtype=self._dtype,
                    blocksize=self._chunk_size,
                    callback=self._audio_callback,
                )
                self._stream.start()
                self._is_recording = True
                log.info(
                    "Microphone recording started (rate=%dHz, chunk=%d samples)",
                    self._sample_rate,
                    self._chunk_size,
                )
            except Exception as e:
                log.error("Failed to start microphone: %s", e)
                raise RuntimeError(
                    f"Could not open microphone: {e}. "
                    "Check that a microphone is connected and no other app is using it."
                ) from e

    def stop(self) -> None:
        """Stop recording."""
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    log.warning("Error closing audio stream: %s", e)
                self._stream = None
            self._is_recording = False
            # Drain the queue
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break
            log.info("Microphone recording stopped")

    def get_chunk(self, timeout: float = 0.1) -> np.ndarray | None:
        """
        Get the next audio chunk from the queue.

        Args:
            timeout: Maximum time to wait for a chunk in seconds.

        Returns:
            Audio chunk as numpy array, or None if timeout.
        """
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain_queue(self) -> list[np.ndarray]:
        """Drain all chunks from the queue and return them."""
        chunks = []
        while not self._audio_queue.empty():
            try:
                chunks.append(self._audio_queue.get_nowait())
            except queue.Empty:
                break
        return chunks

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def chunk_size(self) -> int:
        return self._chunk_size


class AudioPlayer:
    """
    Plays audio through the system speakers.

    Supports interruption — calling stop() immediately halts playback.
    Audio is played in a background thread to avoid blocking the event loop.
    """

    def __init__(self, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._is_playing = False
        self._stop_event = threading.Event()
        self._play_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def play_audio(self, audio_data: np.ndarray, sample_rate: int | None = None) -> None:
        """
        Play audio data synchronously (blocks until complete or interrupted).

        Args:
            audio_data: Audio samples as a numpy array.
            sample_rate: Sample rate of the audio data. Uses default if None.
        """
        try:
            import sounddevice as sd
        except ImportError as err:
            raise RuntimeError(
                "sounddevice is required for audio output. "
                "Install with: pip install nexus-agent[voice]"
            ) from err

        rate = sample_rate or self._sample_rate
        self._stop_event.clear()
        self._is_playing = True

        try:
            # Play in small chunks so we can check for stop requests
            chunk_size = int(rate * 0.1)  # 100ms chunks
            for i in range(0, len(audio_data), chunk_size):
                if self._stop_event.is_set():
                    log.info("Audio playback interrupted")
                    break
                chunk = audio_data[i : i + chunk_size]
                sd.play(chunk, samplerate=rate)
                sd.wait()
        except Exception as e:
            log.error("Audio playback error: %s", e)
        finally:
            self._is_playing = False

    async def play_audio_async(
        self,
        audio_data: np.ndarray,
        sample_rate: int | None = None,
    ) -> None:
        """Play audio in a background thread (non-blocking)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.play_audio, audio_data, sample_rate)

    def play_bytes(self, audio_bytes: bytes, sample_rate: int | None = None) -> None:
        """Play raw PCM audio bytes (16-bit signed int)."""
        audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        self.play_audio(audio_data, sample_rate)

    async def play_bytes_async(
        self,
        audio_bytes: bytes,
        sample_rate: int | None = None,
    ) -> None:
        """Play raw PCM audio bytes in a background thread."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.play_bytes, audio_bytes, sample_rate)

    def stop(self) -> None:
        """Stop any ongoing audio playback immediately."""
        self._stop_event.set()
        try:
            import sounddevice as sd

            sd.stop()
        except Exception:
            pass
        self._is_playing = False
        log.debug("Audio playback stop requested")

    @property
    def is_playing(self) -> bool:
        return self._is_playing


def audio_to_wav_bytes(
    audio_data: np.ndarray,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """
    Convert a numpy audio array to WAV format bytes.

    Args:
        audio_data: Audio samples as numpy array (int16).
        sample_rate: Sample rate in Hz.
        channels: Number of channels.
        sample_width: Bytes per sample (2 = 16-bit).

    Returns:
        WAV file bytes.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)
        wf.writeframes(audio_data.tobytes())
    return buffer.getvalue()


def wav_bytes_to_audio(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """
    Convert WAV bytes back to a numpy array.

    Returns:
        Tuple of (audio_data as int16 numpy array, sample_rate).
    """
    buffer = io.BytesIO(wav_bytes)
    with wave.open(buffer, "rb") as wf:
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        audio_data = np.frombuffer(frames, dtype=np.int16)
    return audio_data, sample_rate
