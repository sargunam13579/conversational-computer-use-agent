"""
NEXUS Voice — Text-to-Speech (TTS) Engine.

Provides a provider-abstracted TTS engine with support for:
  - Edge TTS (online, high-quality Microsoft voices — default)
  - pyttsx3 (offline, uses Windows SAPI5 / espeak)

Supports interruption by splitting text into sentences and checking
a stop flag between each sentence.
"""

from __future__ import annotations

import asyncio
import re
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from nexus.utils.logging import get_logger

log = get_logger("voice.tts")


def _split_sentences(text: str) -> list[str]:
    """
    Split text into natural sentence chunks for interruptible TTS.

    Splits on sentence-ending punctuation while preserving the punctuation.
    Short fragments are merged with the previous sentence.
    """
    stripped = text.strip()
    if not stripped:
        return []

    # Split on sentence-ending punctuation
    raw = re.split(r"(?<=[.!?])\s+", stripped)
    if not raw:
        return [stripped]

    # Merge very short fragments (< 10 chars) with the previous sentence
    sentences: list[str] = []
    for part in raw:
        part = part.strip()
        if not part:
            continue
        if sentences and len(part) < 10:
            sentences[-1] = sentences[-1] + " " + part
        else:
            sentences.append(part)

    return sentences if sentences else [stripped]


class BaseTTSProvider(ABC):
    """Abstract base class for Text-to-Speech providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str = "",
        speed: float = 1.0,
    ) -> bytes:
        """
        Synthesize text to audio bytes.

        Args:
            text: The text to speak.
            voice: Voice identifier (provider-specific).
            speed: Speaking speed multiplier (1.0 = normal).

        Returns:
            Audio data as raw PCM bytes (16-bit, 16kHz, mono)
            or MP3/WAV bytes depending on provider.

        Raises:
            TTSError: If synthesis fails.
        """
        ...

    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if the provider is available."""
        ...

    @abstractmethod
    async def list_voices(self) -> list[dict[str, str]]:
        """List available voices."""
        ...


class TTSError(Exception):
    """Raised when text-to-speech synthesis fails."""

    pass


class EdgeTTSProvider(BaseTTSProvider):
    """
    High-quality TTS using Microsoft Edge's free speech API.

    Provides natural-sounding voices in many languages.
    Requires internet connectivity.
    """

    @property
    def provider_name(self) -> str:
        return "Edge TTS"

    async def synthesize(
        self,
        text: str,
        voice: str = "en-IN-PrabhatNeural",
        speed: float = 1.0,
    ) -> bytes:
        try:
            import edge_tts
        except ImportError as err:
            raise TTSError(
                "edge-tts library not installed. Install with: pip install nexus-agent[voice]"
            ) from err

        # Normalize voice identifier
        resolved_voice = voice or "en-IN-PrabhatNeural"

        # Detect Tamil Unicode characters (U+0B80 to U+0BFF) and route to Edge TTS Tamil Neural voice
        has_tamil = any("\u0b80" <= c <= "\u0bff" for c in text)
        if has_tamil:
            resolved_voice = "ta-IN-ValluvarNeural"
        elif resolved_voice.lower() in (
            "breeze",
            "en-us-breezeneural",
            "breeze-male",
            "breeze-voice",
            "default",
            "indian",
            "indian-male",
            "indian-men",
            "en-in-prabhatneural",
            "en-us-andrewneural",
            "en-us-jennyneural",
        ):
            resolved_voice = "en-IN-PrabhatNeural"

        # Convert speed to edge-tts format: e.g. -8% for relaxed, natural human tempo
        speed_pct = int((speed - 1.0) * 100)
        speed_str = f"+{speed_pct}%" if speed_pct >= 0 else f"{speed_pct}%"

        try:
            communicate = edge_tts.Communicate(text, resolved_voice, rate=speed_str)

            audio_chunks: list[bytes] = []
            async for chunk in communicate.stream():
                if isinstance(chunk, dict) and chunk.get("type") == "audio":
                    chunk_data = chunk.get("data")
                    if isinstance(chunk_data, (bytes, bytearray)):
                        audio_chunks.append(chunk_data if isinstance(chunk_data, bytes) else bytes(chunk_data))

            if not audio_chunks:
                raise TTSError("Edge TTS returned no audio data")

            audio_bytes = b"".join(audio_chunks)
            log.debug(
                "Edge TTS synthesized %d bytes for: '%s...'",
                len(audio_bytes),
                text[:50],
            )
            return audio_bytes

        except TTSError:
            raise
        except Exception as e:
            raise TTSError(f"Edge TTS synthesis failed: {e}") from e

    async def check_availability(self) -> bool:
        import importlib.util

        return importlib.util.find_spec("edge_tts") is not None

    async def list_voices(self) -> list[dict[str, str]]:
        try:
            import edge_tts

            voices = await edge_tts.list_voices()
            return [
                {
                    "id": v["ShortName"],
                    "name": v["FriendlyName"],
                    "language": v["Locale"],
                    "gender": v["Gender"],
                }
                for v in voices
            ]
        except Exception as e:
            log.error("Failed to list Edge TTS voices: %s", e)
            return []


class Pyttsx3TTSProvider(BaseTTSProvider):
    """
    Offline TTS using pyttsx3.

    Uses the system's native speech engine (SAPI5 on Windows,
    espeak on Linux, NSSpeechSynthesizer on macOS).
    """

    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()

    def _ensure_engine(self) -> None:
        """Initialize the pyttsx3 engine if needed."""
        if self._engine is not None:
            return
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            log.info("pyttsx3 TTS engine initialized")
        except Exception as e:
            raise TTSError(f"Failed to initialize pyttsx3: {e}") from e

    @property
    def provider_name(self) -> str:
        return "pyttsx3 (Offline)"

    async def synthesize(
        self,
        text: str,
        voice: str = "",
        speed: float = 1.0,
    ) -> bytes:
        import contextlib

        loop = asyncio.get_event_loop()

        def _do_synthesize() -> bytes:
            with self._lock:
                self._ensure_engine()

                engine = self._engine
                if engine is None:
                    raise TTSError("pyttsx3 engine could not be initialized")

                # Set voice if specified
                if voice:
                    with contextlib.suppress(Exception):
                        engine.setProperty("voice", voice)

                # Set speed (pyttsx3 uses words-per-minute, default ~200)
                base_rate = 200
                engine.setProperty("rate", int(base_rate * speed))

                # Save to a temporary WAV file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name

                try:
                    engine.save_to_file(text, tmp_path)
                    engine.runAndWait()

                    audio_bytes = Path(tmp_path).read_bytes()
                    log.debug(
                        "pyttsx3 synthesized %d bytes for: '%s...'",
                        len(audio_bytes),
                        text[:50],
                    )
                    return audio_bytes
                finally:
                    with contextlib.suppress(Exception):
                        Path(tmp_path).unlink(missing_ok=True)

        return await loop.run_in_executor(None, _do_synthesize)

    async def check_availability(self) -> bool:
        import importlib.util

        return importlib.util.find_spec("pyttsx3") is not None

    async def list_voices(self) -> list[dict[str, str]]:
        try:
            self._ensure_engine()
            engine = self._engine
            if engine is None:
                return []
            voices: Any = engine.getProperty("voices")
            if not isinstance(voices, (list, tuple)):
                return []
            return [
                {
                    "id": getattr(v, "id", str(v)),
                    "name": getattr(v, "name", str(v)),
                    "language": ",".join(getattr(v, "languages", []))
                    if getattr(v, "languages", None)
                    else "unknown",
                    "gender": "unknown",
                }
                for v in voices
            ]
        except Exception as e:
            log.error("Failed to list pyttsx3 voices: %s", e)
            return []


class TTSEngine:
    """
    Text-to-Speech engine with provider abstraction and interruption support.

    Splits text into sentences and speaks them one-by-one, checking for
    interruption between each sentence.
    """

    def __init__(
        self,
        provider_name: str = "edge",
        voice: str = "en-US-AndrewNeural",
        speed: float = 1.0,
        fallback_voice: str = "",
    ) -> None:
        """
        Args:
            provider_name: TTS provider to use ("edge" or "pyttsx3").
            voice: Default voice identifier.
            speed: Default speaking speed multiplier.
            fallback_voice: Voice ID for the pyttsx3 fallback.
        """
        self._provider_name = provider_name
        self._voice = voice
        self._speed = speed
        self._fallback_voice = fallback_voice
        self._provider: BaseTTSProvider | None = None
        self._fallback_provider: BaseTTSProvider | None = None
        self._is_speaking = False
        self._stop_requested = False
        self._lock = threading.Lock()

        self._init_providers()

    def _init_providers(self) -> None:
        """Initialize the configured TTS provider and fallback."""
        if self._provider_name == "edge":
            self._provider = EdgeTTSProvider()
            self._fallback_provider = Pyttsx3TTSProvider()
        elif self._provider_name == "pyttsx3":
            self._provider = Pyttsx3TTSProvider()
            self._fallback_provider = None
        else:
            log.warning(
                "Unknown TTS provider '%s', falling back to edge",
                self._provider_name,
            )
            self._provider = EdgeTTSProvider()
            self._fallback_provider = Pyttsx3TTSProvider()
            self._provider_name = "edge"

        log.info("TTS engine initialized with provider: %s", self._provider.provider_name)

    async def synthesize(self, text: str) -> bytes:
        """
        Synthesize text to audio bytes.

        Falls back to pyttsx3 if the primary provider fails.

        Returns:
            Audio bytes (format depends on provider — MP3 for Edge, WAV for pyttsx3).
        """
        try:
            if self._provider is None:
                raise TTSError("No TTS provider configured")
            return await self._provider.synthesize(text, self._voice, self._speed)
        except TTSError as e:
            if self._fallback_provider is not None:
                log.warning("Primary TTS failed (%s), trying fallback", e)
                voice = self._fallback_voice or ""
                return await self._fallback_provider.synthesize(text, voice, self._speed)
            raise

    async def synthesize_sentences(
        self,
        text: str,
    ) -> list[bytes]:
        """
        Split text into sentences and synthesize each separately.

        This enables interruption between sentences.

        Returns:
            List of audio byte chunks, one per sentence.
        """
        sentences = _split_sentences(text)
        audio_chunks: list[bytes] = []

        for sentence in sentences:
            if self._stop_requested:
                log.info("TTS synthesis stopped by interruption")
                break

            try:
                chunk = await self.synthesize(sentence)
                audio_chunks.append(chunk)
            except TTSError as e:
                log.error("TTS failed for sentence: %s", e)
                continue

        return audio_chunks

    def request_stop(self) -> None:
        """Request the TTS engine to stop speaking after the current sentence."""
        self._stop_requested = True
        self._is_speaking = False
        log.debug("TTS stop requested")

    def reset_stop(self) -> None:
        """Reset the stop flag for a new utterance."""
        self._stop_requested = False

    async def speak(self, text: str) -> bool:
        """
        Synthesize and indicate readiness to play text.

        This method synthesizes the audio. The actual playback is handled
        by the VoicePipeline which coordinates with the AudioPlayer.

        Returns:
            True if synthesis completed without interruption.
        """
        self._stop_requested = False
        self._is_speaking = True

        try:
            await self.synthesize(text)
            return not self._stop_requested
        except TTSError as e:
            log.error("TTS speak failed: %s", e)
            return False
        finally:
            self._is_speaking = False

    async def check_availability(self) -> bool:
        """Check if any TTS provider is available."""
        return bool(
            (self._provider and await self._provider.check_availability())
            or (self._fallback_provider and await self._fallback_provider.check_availability())
        )

    async def list_voices(self) -> list[dict[str, str]]:
        """List available voices from the current provider."""
        if self._provider:
            return await self._provider.list_voices()
        return []

    @property
    def provider_name(self) -> str:
        if self._provider:
            return self._provider.provider_name
        return "None"

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def voice(self) -> str:
        return self._voice

    @voice.setter
    def voice(self, value: str) -> None:
        self._voice = value

    @property
    def speed(self) -> float:
        return self._speed

    @speed.setter
    def speed(self, value: float) -> None:
        self._speed = max(0.25, min(4.0, value))
