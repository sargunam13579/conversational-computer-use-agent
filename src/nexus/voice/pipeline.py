"""
NEXUS Voice — Voice Pipeline Orchestrator.

Wires together VAD → STT → NexusBrain → TTS into a continuous
conversation loop with interruption support.

The pipeline manages the full lifecycle:
  1. Listen for speech via microphone + VAD
  2. Transcribe speech to text via STT
  3. Process text through the Brain for an AI response
  4. Speak the response via TTS
  5. Monitor for interruption during speech (stop TTS if user speaks)
  6. Loop back to step 1

Interaction behavior:
  - Voice input → voice response
  - Text input  → text response (no TTS)
"""

from __future__ import annotations

import asyncio
import io
import subprocess
import tempfile
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from nexus.utils.events import get_event_bus
from nexus.utils.logging import get_logger
from nexus.voice.stt import STTError

if TYPE_CHECKING:
    from nexus.core.brain import NexusBrain

log = get_logger("voice.pipeline")


class PipelineState(StrEnum):
    """Current state of the voice pipeline."""

    STOPPED = "stopped"
    IDLE = "idle"  # Waiting for speech
    LISTENING = "listening"  # Speech detected, accumulating
    PROCESSING = "processing"  # STT + Brain processing
    SPEAKING = "speaking"  # TTS playback
    ERROR = "error"


class InteractionMode(StrEnum):
    """How the user interacts with NEXUS."""

    VOICE_AND_TEXT = "voice_and_text"
    VOICE_ONLY = "voice_only"
    TEXT_ONLY = "text_only"


class InputMode(StrEnum):
    """How the current input was received."""

    VOICE = "voice"
    TEXT = "text"


class VoicePipeline:
    """
    The main voice pipeline orchestrator.

    Coordinates microphone capture, voice activity detection, speech-to-text,
    brain processing, text-to-speech, and audio playback into a seamless
    voice conversation loop.
    """

    def __init__(
        self,
        brain: NexusBrain,
        sample_rate: int = 16000,
        stt_provider: str = "google_web",
        tts_provider: str = "edge",
        tts_voice: str = "en-US-JennyNeural",
        tts_speed: float = 1.0,
        tts_fallback_voice: str = "",
        language: str = "en-US",
        silence_threshold_ms: int = 1500,
        vad_threshold: float = 0.5,
        vad_min_speech_ms: int = 250,
        vad_energy_threshold: int = 300,
        interaction_mode: str = "voice_and_text",
        interrupt_enabled: bool = True,
    ) -> None:
        self._brain = brain
        self._sample_rate = sample_rate
        self._language = language
        self._interaction_mode = InteractionMode(interaction_mode)
        self._interrupt_enabled = interrupt_enabled

        self._state = PipelineState.STOPPED
        self._running = False
        self._listen_task: asyncio.Task | None = None
        self._event_bus = get_event_bus()

        # State change callbacks
        self._state_callbacks: list[Callable[[PipelineState], Any]] = []

        # --- Initialize components ---
        from nexus.voice.audio_io import AudioPlayer, AudioRecorder
        from nexus.voice.stt import STTEngine
        from nexus.voice.tts import TTSEngine
        from nexus.voice.vad import VoiceActivityDetector
        from nexus.voice.wake_word import WakeWordDetector

        self._recorder = AudioRecorder(
            sample_rate=sample_rate,
            channels=1,
            chunk_duration_ms=30,
        )
        self._player = AudioPlayer(sample_rate=sample_rate)
        self._vad = VoiceActivityDetector(
            sample_rate=sample_rate,
            threshold=vad_threshold,
            silence_threshold_ms=silence_threshold_ms,
            min_speech_ms=vad_min_speech_ms,
            energy_threshold=vad_energy_threshold,
        )
        self._stt = STTEngine(
            provider_name=stt_provider,
            language=language,
        )
        self._tts = TTSEngine(
            provider_name=tts_provider,
            voice=tts_voice,
            speed=tts_speed,
            fallback_voice=tts_fallback_voice,
        )

        # Wake-word detector (Phase 3)
        from unittest.mock import NonCallableMock

        identity: Any = getattr(self._brain, "identity", None)
        if (
            identity is not None
            and not isinstance(identity, NonCallableMock)
            and hasattr(identity, "all_wake_words")
        ):
            wake_words = list(identity.all_wake_words)
            id_config = getattr(identity, "config", None)
            prefixes = getattr(id_config, "wake_word_prefixes", None)
            self._require_wake_word = bool(getattr(id_config, "require_wake_word", False))
        else:
            wake_words = ["NEXUS"]
            prefixes = None
            self._require_wake_word = False

        self._wake_detector = WakeWordDetector(
            wake_words=wake_words,
            prefixes=prefixes,
        )

    @classmethod
    def from_settings(cls, brain: NexusBrain, settings: Any) -> VoicePipeline:
        """
        Create a VoicePipeline from NexusSettings.

        Args:
            brain: The NexusBrain instance.
            settings: NexusSettings object.

        Returns:
            A configured VoicePipeline.
        """
        vs = settings.voice
        return cls(
            brain=brain,
            sample_rate=vs.sample_rate,
            stt_provider=vs.stt_provider,
            tts_provider=vs.tts_provider,
            tts_voice=vs.tts.voice,
            tts_speed=vs.tts.speed,
            tts_fallback_voice=vs.tts.fallback_voice,
            language=vs.language,
            silence_threshold_ms=vs.silence_threshold_ms,
            vad_threshold=vs.vad.threshold,
            vad_min_speech_ms=vs.vad.min_speech_ms,
            vad_energy_threshold=vs.vad.energy_threshold,
            interaction_mode=vs.interaction_mode,
            interrupt_enabled=vs.interrupt_enabled,
        )

    def on_state_change(self, callback: Callable[[PipelineState], Any]) -> None:
        """Register a callback for pipeline state changes."""
        self._state_callbacks.append(callback)

    def _set_state(self, new_state: PipelineState) -> None:
        """Update the pipeline state and notify callbacks."""
        old_state = self._state
        self._state = new_state
        if old_state != new_state:
            log.debug("Pipeline: %s → %s", old_state.value, new_state.value)
            for cb in self._state_callbacks:
                try:
                    cb(new_state)
                except Exception as e:
                    log.error("State callback error: %s", e)

    async def start(self) -> None:
        """
        Start the voice pipeline.

        Begins capturing audio from the microphone and processing
        voice input in a background loop.
        """
        if self._running:
            log.warning("Voice pipeline is already running")
            return

        if self._interaction_mode == InteractionMode.TEXT_ONLY:
            log.info("Voice pipeline not started (text-only mode)")
            return

        log.info("Starting voice pipeline...")

        try:
            self._recorder.start()
        except RuntimeError as e:
            log.error("Cannot start voice pipeline: %s", e)
            self._set_state(PipelineState.ERROR)
            raise

        self._running = True
        self._set_state(PipelineState.IDLE)

        # Start the listen loop as a background task
        self._listen_task = asyncio.create_task(self._listen_loop())

        await self._event_bus.emit(
            "voice.pipeline.started",
            {"mode": self._interaction_mode.value},
            source="voice.pipeline",
        )
        log.info(
            "Voice pipeline started (mode=%s, stt=%s, tts=%s)",
            self._interaction_mode.value,
            self._stt.provider_name,
            self._tts.provider_name,
        )

    async def stop(self) -> None:
        """Stop the voice pipeline and release all resources."""
        if not self._running:
            return

        log.info("Stopping voice pipeline...")
        self._running = False

        # Cancel the listen task
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            import contextlib

            with contextlib.suppress(asyncio.CancelledError):
                await self._listen_task

        # Stop all components
        self._recorder.stop()
        self._player.stop()
        self._tts.request_stop()
        self._vad.reset()

        self._set_state(PipelineState.STOPPED)

        await self._event_bus.emit(
            "voice.pipeline.stopped",
            {},
            source="voice.pipeline",
        )
        log.info("Voice pipeline stopped")

    async def _listen_loop(self) -> None:
        """
        Main listening loop — runs continuously while the pipeline is active.

        Reads audio chunks from the recorder, feeds them to VAD, and
        triggers STT + processing when speech ends.
        """
        log.debug("Listen loop started")

        while self._running:
            try:
                self._set_state(PipelineState.IDLE)

                # Get audio chunk from recorder
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._recorder.get_chunk,
                    0.1,
                )
                if chunk is None:
                    await asyncio.sleep(0.01)
                    continue

                # Feed to VAD
                from nexus.voice.vad import VADState

                vad_result = self._vad.process_chunk(chunk)

                if vad_result == VADState.SPEECH:
                    if self._state != PipelineState.LISTENING:
                        self._set_state(PipelineState.LISTENING)
                        await self._event_bus.emit(
                            "voice.speech.start",
                            {},
                            source="voice.pipeline",
                        )

                        # If currently speaking, interrupt!
                        if self._player.is_playing and self._interrupt_enabled:
                            log.info("User interrupted — stopping TTS")
                            self._player.stop()
                            self._tts.request_stop()

                elif vad_result == VADState.SILENCE:
                    # End of speech — get the segment and process
                    speech_segment = self._vad.get_speech_segment()
                    if speech_segment is not None and len(speech_segment) > 0:
                        await self._event_bus.emit(
                            "voice.speech.end",
                            {"duration_samples": len(speech_segment)},
                            source="voice.pipeline",
                        )
                        await self._process_speech(speech_segment)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Listen loop error: %s", e)
                self._set_state(PipelineState.ERROR)
                await asyncio.sleep(1)  # Brief pause before retrying

        log.debug("Listen loop ended")

    async def _process_speech(self, audio_segment: np.ndarray) -> None:
        """
        Process a speech segment: transcribe → brain → speak.

        Args:
            audio_segment: The captured speech audio as numpy array.
        """
        self._set_state(PipelineState.PROCESSING)

        # Step 1: Speech-to-Text
        try:
            text = await self._stt.transcribe(
                audio_segment,
                self._sample_rate,
                self._language,
            )

            if not text.strip():
                log.debug("STT returned empty text, ignoring")
                self._set_state(PipelineState.IDLE)
                return

            log.info("Voice input: '%s'", text)

            await self._event_bus.emit(
                "voice.stt.result",
                {"text": text, "language": self._language},
                source="voice.pipeline",
            )

        except STTError as e:
            log.error("STT failed: %s", e)
            self._set_state(PipelineState.ERROR)
            await asyncio.sleep(0.5)
            return

        # Step 2: Wake word processing (Phase 3)
        input_for_brain = text
        match = self._wake_detector.detect(text)

        if self._require_wake_word:
            if not match.matched:
                log.debug("Speech ignored: wake word not detected in '%s'", text)
                self._set_state(PipelineState.IDLE)
                return

            if not match.has_command:
                # User just called the wake word (e.g. "Hey Nexus")
                log.info("Wake word '%s' detected without command", match.wake_word)
                await self._speak_response("Yes? I'm listening.")
                return
            else:
                input_for_brain = match.command
        else:
            # Wake word not strictly required, but extract command if wake word was present
            if match.matched and match.has_command:
                input_for_brain = match.command

        # Step 3: Process through the Brain
        try:
            response = await self._brain.process(input_for_brain)
            log.info("Brain response: '%s...'", response[:80] if response else "")

        except Exception as e:
            log.error("Brain processing failed: %s", e)
            response = "Sorry, I encountered an error processing your request."

        # Step 4: Text-to-Speech (voice input → voice output)
        await self._speak_response(response)

    async def _speak_response(self, text: str) -> None:
        """
        Speak a response via TTS.

        Splits text into sentences for interruptible playback.

        Args:
            text: The response text to speak.
        """
        if self._interaction_mode == InteractionMode.TEXT_ONLY:
            return

        self._set_state(PipelineState.SPEAKING)
        self._tts.reset_stop()

        await self._event_bus.emit(
            "voice.tts.start",
            {"text": text[:100]},
            source="voice.pipeline",
        )

        try:
            from nexus.voice.tts import TTSError, _split_sentences

            sentences = _split_sentences(text)

            for sentence in sentences:
                if not self._running or self._tts._stop_requested:
                    log.info("TTS interrupted between sentences")
                    break

                try:
                    audio_bytes = await self._tts.synthesize(sentence)

                    if not self._running or self._tts._stop_requested:
                        break

                    # Play the audio
                    await self._play_tts_audio(audio_bytes)

                except TTSError as e:
                    log.error("TTS failed for sentence: %s", e)
                    continue

        except Exception as e:
            log.error("Speech response error: %s", e)

        await self._event_bus.emit(
            "voice.tts.end",
            {},
            source="voice.pipeline",
        )
        self._set_state(PipelineState.IDLE)

    async def _play_tts_audio(self, audio_bytes: bytes) -> None:
        """
        Play TTS audio bytes through the speakers.

        Handles format conversion from MP3 (Edge TTS) or WAV (pyttsx3).
        """
        try:
            # Try to decode as WAV first
            import wave

            try:
                buf = io.BytesIO(audio_bytes)
                with wave.open(buf, "rb") as wf:
                    sample_rate = wf.getframerate()
                    frames = wf.readframes(wf.getnframes())
                    audio_data = np.frombuffer(frames, dtype=np.int16)
                    audio_float = audio_data.astype(np.float32) / 32768.0
                    await self._player.play_audio_async(audio_float, sample_rate)
                    return
            except wave.Error:
                pass

            # Edge TTS returns MP3 — convert to playable format
            # Use a temporary file approach with subprocess for MP3 decode
            await self._play_mp3_bytes(audio_bytes)

        except Exception as e:
            log.error("Audio playback error: %s", e)

    async def _play_mp3_bytes(self, mp3_bytes: bytes) -> None:
        """
        Play MP3 audio bytes by converting to WAV first.

        Uses ffmpeg if available, otherwise falls back to writing
        a temp file and using sounddevice with raw playback.
        """
        loop = asyncio.get_event_loop()

        def _convert_and_play() -> None:

            # Write MP3 to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(mp3_bytes)
                mp3_path = f.name

            wav_path = mp3_path.replace(".mp3", ".wav")

            try:
                # Try ffmpeg conversion
                result = subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        mp3_path,
                        "-ar",
                        str(self._sample_rate),
                        "-ac",
                        "1",
                        "-f",
                        "wav",
                        wav_path,
                    ],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0 and Path(wav_path).exists():
                    import wave

                    with wave.open(wav_path, "rb") as wf:
                        frames = wf.readframes(wf.getnframes())
                        audio_data = np.frombuffer(frames, dtype=np.int16)
                        audio_float = audio_data.astype(np.float32) / 32768.0
                        self._player.play_audio(audio_float, self._sample_rate)
                    return

            except FileNotFoundError:
                log.debug("ffmpeg not found, trying fallback MP3 playback")
            except Exception as e:
                log.debug("ffmpeg conversion failed: %s", e)

            # Fallback: try to use the system default player
            try:
                import platform

                if platform.system() == "Windows":
                    import os

                    os.startfile(mp3_path)
                    import time

                    # Estimate playback duration (rough: ~1 second per 16KB of MP3)
                    duration = max(1.0, len(mp3_bytes) / 16000)
                    time.sleep(duration)
            except Exception as e:
                log.warning("Could not play MP3 audio: %s", e)

            finally:
                # Clean up temp files
                try:
                    Path(mp3_path).unlink(missing_ok=True)
                    Path(wav_path).unlink(missing_ok=True)
                except Exception:
                    pass

        await loop.run_in_executor(None, _convert_and_play)

    async def process_text_input(self, text: str) -> str:
        """
        Process a text input through the brain.

        Text input → text response (no TTS).

        Args:
            text: The user's text input.

        Returns:
            The brain's text response.
        """
        response = await self._brain.process(text)
        return response

    async def process_voice_text(self, text: str) -> str:
        """
        Process text as if it were voice input (triggers TTS response).

        Useful for the /say command or API-triggered voice responses.

        Args:
            text: The text to process.

        Returns:
            The brain's response (also spoken via TTS).
        """
        response = await self._brain.process(text)
        await self._speak_response(response)
        return response

    # --- Configuration ---

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def interaction_mode(self) -> InteractionMode:
        return self._interaction_mode

    @interaction_mode.setter
    def interaction_mode(self, mode: str | InteractionMode) -> None:
        if isinstance(mode, str):
            mode = InteractionMode(mode)
        self._interaction_mode = mode
        log.info("Interaction mode changed to: %s", mode.value)

    @property
    def stt_engine(self) -> Any:
        return self._stt

    @property
    def tts_engine(self) -> Any:
        return self._tts

    @property
    def vad(self) -> Any:
        return self._vad

    @property
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, value: str) -> None:
        self._language = value
        self._stt.language = value
        log.info("Voice language changed to: %s", value)

    @property
    def wake_word_detector(self) -> Any:
        return self._wake_detector

    @property
    def require_wake_word(self) -> bool:
        return self._require_wake_word

    @require_wake_word.setter
    def require_wake_word(self, required: bool) -> None:
        self._require_wake_word = required
        log.info("Require wake word changed to: %s", required)

    def get_status(self) -> dict[str, Any]:
        """Get the current status of the voice pipeline."""
        assistant_name = self._brain.identity.name if hasattr(self._brain, "identity") else "NEXUS"
        wake_word = self._brain.identity.wake_word if hasattr(self._brain, "identity") else "NEXUS"
        aliases = self._brain.identity.aliases if hasattr(self._brain, "identity") else []
        return {
            "state": self._state.value,
            "running": self._running,
            "interaction_mode": self._interaction_mode.value,
            "language": self._language,
            "stt_provider": self._stt.provider_name,
            "tts_provider": self._tts.provider_name,
            "tts_voice": self._tts.voice,
            "tts_speed": self._tts.speed,
            "vad_uses_silero": self._vad.uses_silero,
            "interrupt_enabled": self._interrupt_enabled,
            "recorder_active": self._recorder.is_recording,
            "assistant_name": assistant_name,
            "wake_word": wake_word,
            "aliases": aliases,
            "require_wake_word": self._require_wake_word,
        }
