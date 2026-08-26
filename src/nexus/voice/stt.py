"""
NEXUS Voice — Speech-to-Text (STT) Engine.

Provides a provider-abstracted STT engine with support for:
  - Google Web Speech API (free, online — default)
  - Vosk (offline, requires model download)

Designed for future multilingual support (English initially, Tamil planned).
"""

from __future__ import annotations

import io
import wave
from abc import ABC, abstractmethod

import numpy as np

from nexus.utils.logging import get_logger

log = get_logger("voice.stt")


class BaseSTTProvider(ABC):
    """Abstract base class for Speech-to-Text providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @abstractmethod
    async def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: str = "en-US",
    ) -> str:
        """
        Transcribe audio to text.

        Args:
            audio_data: Audio samples as a numpy array (int16).
            sample_rate: Sample rate of the audio in Hz.
            language: BCP-47 language code for recognition.

        Returns:
            Transcribed text string.

        Raises:
            STTError: If transcription fails.
        """
        ...

    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if the provider is available."""
        ...


class STTError(Exception):
    """Raised when speech-to-text transcription fails."""

    pass


class GoogleWebSTTProvider(BaseSTTProvider):
    """
    Speech-to-Text using Google's free Web Speech API.

    Uses the `speech_recognition` library which wraps Google's free
    (no API key needed) speech recognition service. Good quality,
    but requires internet connectivity.
    """

    @property
    def provider_name(self) -> str:
        return "Google Web Speech"

    async def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: str = "en-US",
    ) -> str:
        import asyncio

        try:
            import speech_recognition as sr
        except ImportError as err:
            raise STTError(
                "SpeechRecognition library not installed. "
                "Install with: pip install nexus-agent[voice]"
            ) from err

        def _do_transcribe() -> str:
            recognizer = sr.Recognizer()

            # Convert numpy array to WAV bytes for speech_recognition
            if audio_data.dtype != np.int16:
                audio_int16 = (audio_data * 32767).astype(np.int16)
            else:
                audio_int16 = audio_data

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_int16.tobytes())

            wav_buffer.seek(0)

            with sr.AudioFile(wav_buffer) as source:
                audio = recognizer.record(source)

            try:
                recognize_fn = getattr(recognizer, "recognize_google", None)
                if callable(recognize_fn):
                    text = str(recognize_fn(audio, language=language))
                else:
                    raise STTError("Google recognition backend not available on Recognizer")
                log.info("STT transcription: '%s'", text)
                return text
            except sr.UnknownValueError:
                log.debug("STT: Could not understand audio")
                return ""
            except sr.RequestError as e:
                raise STTError(f"Google Web Speech API error: {e}") from e

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_transcribe)

    async def check_availability(self) -> bool:
        import importlib.util

        return importlib.util.find_spec("speech_recognition") is not None


class VoskSTTProvider(BaseSTTProvider):
    """
    Offline Speech-to-Text using Vosk.

    Requires downloading a language model. Provides fully offline
    transcription with decent accuracy.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path
        self._model = None

    @property
    def provider_name(self) -> str:
        return "Vosk (Offline)"

    def _ensure_model(self, language: str) -> None:
        """Load the Vosk model if not already loaded."""
        if self._model is not None:
            return

        try:
            from vosk import Model, SetLogLevel

            SetLogLevel(-1)  # Suppress Vosk's verbose logging

            if self._model_path:
                self._model = Model(self._model_path)
            else:
                # Try to use a small model for the language
                lang_short = language.split("-")[0]  # "en-US" -> "en"
                self._model = Model(lang=lang_short)
            log.info("Vosk model loaded for language: %s", language)
        except Exception as e:
            raise STTError(
                f"Failed to load Vosk model: {e}. "
                "Download a model from https://alphacephei.com/vosk/models"
            ) from e

    async def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: str = "en-US",
    ) -> str:
        import asyncio
        import json

        def _do_transcribe() -> str:
            try:
                from vosk import KaldiRecognizer
            except ImportError as err:
                raise STTError(
                    "Vosk library not installed. Install with: pip install nexus-agent[voice]"
                ) from err

            self._ensure_model(language)

            recognizer = KaldiRecognizer(self._model, sample_rate)
            recognizer.SetWords(True)

            if audio_data.dtype != np.int16:
                audio_int16 = (audio_data * 32767).astype(np.int16)
            else:
                audio_int16 = audio_data

            audio_bytes = audio_int16.tobytes()

            # Process in chunks
            chunk_size = 4000
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i : i + chunk_size]
                recognizer.AcceptWaveform(chunk)

            result = json.loads(recognizer.FinalResult())
            text = result.get("text", "")
            log.info("STT transcription (Vosk): '%s'", text)
            return text

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_transcribe)

    async def check_availability(self) -> bool:
        import importlib.util

        return importlib.util.find_spec("vosk") is not None


class STTEngine:
    """
    Speech-to-Text engine with provider abstraction.

    Routes transcription requests to the configured provider
    (Google Web Speech or Vosk).
    """

    def __init__(
        self,
        provider_name: str = "google_web",
        language: str = "en-US",
        vosk_model_path: str | None = None,
    ) -> None:
        """
        Args:
            provider_name: STT provider to use ("google_web" or "vosk").
            language: Default language for recognition.
            vosk_model_path: Optional path to Vosk model directory.
        """
        self._provider_name = provider_name
        self._language = language
        self._provider: BaseSTTProvider | None = None
        self._vosk_model_path = vosk_model_path

        self._init_provider()

    def _init_provider(self) -> None:
        """Initialize the configured STT provider."""
        if self._provider_name == "google_web":
            self._provider = GoogleWebSTTProvider()
        elif self._provider_name == "vosk":
            self._provider = VoskSTTProvider(model_path=self._vosk_model_path)
        else:
            log.warning(
                "Unknown STT provider '%s', falling back to google_web",
                self._provider_name,
            )
            self._provider = GoogleWebSTTProvider()
            self._provider_name = "google_web"

        log.info("STT engine initialized with provider: %s", self._provider.provider_name)

    async def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> str:
        """
        Transcribe audio to text using the configured provider.

        Args:
            audio_data: Audio samples as numpy array.
            sample_rate: Sample rate of the audio.
            language: Override the default language.

        Returns:
            Transcribed text, or empty string if nothing was recognized.
        """
        if self._provider is None:
            raise STTError("No STT provider available")

        lang = language or self._language

        try:
            return await self._provider.transcribe(audio_data, sample_rate, lang)
        except STTError:
            raise
        except Exception as e:
            log.error("STT transcription failed: %s", e)
            raise STTError(f"Transcription failed: {e}") from e

    async def check_availability(self) -> bool:
        """Check if the current provider is available."""
        if self._provider is None:
            return False
        return await self._provider.check_availability()

    @property
    def provider_name(self) -> str:
        if self._provider:
            return self._provider.provider_name
        return "None"

    @property
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, value: str) -> None:
        self._language = value
