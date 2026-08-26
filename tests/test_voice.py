"""
Tests for the NEXUS Voice System (Phase 2).

Tests cover:
  - STT engine initialization and provider routing
  - TTS engine initialization and text chunking
  - VAD configuration and state machine
  - Pipeline state transitions
  - Interruption behavior
  - Input mode detection
  - Error handling
  - Configuration validation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Helper: Generate a dummy audio segment
# ---------------------------------------------------------------------------


def _make_audio(duration_s: float = 1.0, sample_rate: int = 16000) -> np.ndarray:
    """Create a sine-wave audio segment for testing."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), dtype=np.float32)
    tone = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
    return tone


def _make_silence(duration_s: float = 1.0, sample_rate: int = 16000) -> np.ndarray:
    """Create a silent audio segment."""
    return np.zeros(int(sample_rate * duration_s), dtype=np.int16)


# ---------------------------------------------------------------------------
# Audio I/O Tests
# ---------------------------------------------------------------------------


class TestAudioIO:
    """Tests for audio_io module utility functions."""

    def test_audio_to_wav_bytes(self):
        from nexus.voice.audio_io import audio_to_wav_bytes

        audio = _make_audio(0.5)
        wav_bytes = audio_to_wav_bytes(audio, sample_rate=16000)

        assert isinstance(wav_bytes, bytes)
        assert len(wav_bytes) > 0
        # WAV files start with "RIFF"
        assert wav_bytes[:4] == b"RIFF"

    def test_wav_roundtrip(self):
        from nexus.voice.audio_io import audio_to_wav_bytes, wav_bytes_to_audio

        original = _make_audio(0.5)
        wav_bytes = audio_to_wav_bytes(original, sample_rate=16000)
        recovered, sr = wav_bytes_to_audio(wav_bytes)

        assert sr == 16000
        assert len(recovered) == len(original)
        np.testing.assert_array_equal(recovered, original)

    def test_audio_recorder_init(self):
        from nexus.voice.audio_io import AudioRecorder

        rec = AudioRecorder(sample_rate=16000, chunk_duration_ms=30)
        assert rec.sample_rate == 16000
        assert rec.is_recording is False

    def test_audio_player_init(self):
        from nexus.voice.audio_io import AudioPlayer

        player = AudioPlayer(sample_rate=16000)
        assert player.is_playing is False

    def test_audio_player_stop_when_not_playing(self):
        from nexus.voice.audio_io import AudioPlayer

        player = AudioPlayer()
        # Should not raise
        player.stop()
        assert player.is_playing is False

    def test_audio_recorder_callbacks(self):
        from nexus.voice.audio_io import AudioRecorder

        rec = AudioRecorder()
        cb = MagicMock()
        rec.add_callback(cb)
        assert cb in rec._callbacks

        rec.remove_callback(cb)
        assert cb not in rec._callbacks

    def test_audio_recorder_remove_nonexistent_callback(self):
        from nexus.voice.audio_io import AudioRecorder

        rec = AudioRecorder()
        cb = MagicMock()
        # Should not raise
        rec.remove_callback(cb)


# ---------------------------------------------------------------------------
# VAD Tests
# ---------------------------------------------------------------------------


class TestVAD:
    """Tests for the Voice Activity Detector."""

    def test_vad_init(self):
        """VAD initializes with correct defaults."""
        with patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"):
            from nexus.voice.vad import VADState, VoiceActivityDetector

            vad = VoiceActivityDetector(
                sample_rate=16000,
                threshold=0.5,
                silence_threshold_ms=1500,
            )
            assert vad.state == VADState.IDLE
            assert vad.is_speech is False

    def test_vad_energy_computation(self):
        """Energy computation returns reasonable values."""
        with patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"):
            from nexus.voice.vad import VoiceActivityDetector

            vad = VoiceActivityDetector()

            silence = _make_silence(0.1)
            energy = vad._compute_energy(silence)
            assert energy == 0.0

            tone = _make_audio(0.1)
            energy = vad._compute_energy(tone)
            assert energy > 0

    def test_vad_silence_stays_idle(self):
        """Silence chunks keep VAD in IDLE state."""
        with patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"):
            from nexus.voice.vad import VADState, VoiceActivityDetector

            vad = VoiceActivityDetector(energy_threshold=300)

            silence = _make_silence(0.03)
            result = vad.process_chunk(silence)
            assert result == VADState.IDLE

    def test_vad_reset(self):
        """Reset clears all VAD state."""
        with patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"):
            from nexus.voice.vad import VADState, VoiceActivityDetector

            vad = VoiceActivityDetector()
            vad._state = VADState.SPEECH
            vad._speech_chunks = [np.zeros(100, dtype=np.int16)]

            vad.reset()
            assert vad.state == VADState.IDLE
            assert vad.get_speech_segment() is None

    def test_vad_get_speech_segment_empty(self):
        """get_speech_segment returns None when no speech accumulated."""
        with patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"):
            from nexus.voice.vad import VoiceActivityDetector

            vad = VoiceActivityDetector()
            assert vad.get_speech_segment() is None

    def test_vad_get_speech_segment_with_data(self):
        """get_speech_segment concatenates accumulated chunks."""
        with patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"):
            from nexus.voice.vad import VoiceActivityDetector

            vad = VoiceActivityDetector()

            chunk1 = np.ones(100, dtype=np.int16)
            chunk2 = np.ones(200, dtype=np.int16) * 2
            vad._speech_chunks = [chunk1, chunk2]

            segment = vad.get_speech_segment()
            assert segment is not None
            assert len(segment) == 300
            # After getting segment, should be empty
            assert vad.get_speech_segment() is None


# ---------------------------------------------------------------------------
# STT Tests
# ---------------------------------------------------------------------------


class TestSTTEngine:
    """Tests for the Speech-to-Text engine."""

    def test_stt_engine_init_google_web(self):
        """STT engine initializes with google_web provider."""
        from nexus.voice.stt import STTEngine

        stt = STTEngine(provider_name="google_web", language="en-US")
        assert stt.provider_name == "Google Web Speech"
        assert stt.language == "en-US"

    def test_stt_engine_init_vosk(self):
        """STT engine initializes with vosk provider."""
        from nexus.voice.stt import STTEngine

        stt = STTEngine(provider_name="vosk", language="en-US")
        assert stt.provider_name == "Vosk (Offline)"

    def test_stt_engine_fallback_unknown(self):
        """Unknown provider falls back to google_web."""
        from nexus.voice.stt import STTEngine

        stt = STTEngine(provider_name="unknown_provider")
        assert stt.provider_name == "Google Web Speech"

    def test_stt_language_setter(self):
        """Language can be changed after init."""
        from nexus.voice.stt import STTEngine

        stt = STTEngine(language="en-US")
        stt.language = "ta-IN"
        assert stt.language == "ta-IN"

    @pytest.mark.asyncio
    async def test_stt_no_provider_raises(self):
        """Transcription raises when no provider is set."""
        from nexus.voice.stt import STTEngine, STTError

        stt = STTEngine()
        stt._provider = None

        with pytest.raises(STTError, match="No STT provider"):
            await stt.transcribe(_make_audio(1.0))

    @pytest.mark.asyncio
    async def test_google_web_stt_availability(self):
        """Google Web STT reports availability based on import."""
        from nexus.voice.stt import GoogleWebSTTProvider

        provider = GoogleWebSTTProvider()
        # This depends on whether speech_recognition is installed
        available = await provider.check_availability()
        assert isinstance(available, bool)

    @pytest.mark.asyncio
    async def test_stt_engine_check_availability(self):
        """STT engine check_availability delegates to provider."""
        from nexus.voice.stt import STTEngine

        stt = STTEngine()
        available = await stt.check_availability()
        assert isinstance(available, bool)


# ---------------------------------------------------------------------------
# TTS Tests
# ---------------------------------------------------------------------------


class TestTTSEngine:
    """Tests for the Text-to-Speech engine."""

    def test_tts_engine_init_edge(self):
        """TTS engine initializes with edge provider."""
        from nexus.voice.tts import TTSEngine

        tts = TTSEngine(provider_name="edge", voice="en-US-JennyNeural")
        assert tts.provider_name == "Edge TTS"
        assert tts.voice == "en-US-JennyNeural"
        assert tts.speed == 1.0

    def test_tts_engine_init_pyttsx3(self):
        """TTS engine initializes with pyttsx3 provider."""
        from nexus.voice.tts import TTSEngine

        tts = TTSEngine(provider_name="pyttsx3")
        assert tts.provider_name == "pyttsx3 (Offline)"

    def test_tts_engine_fallback_unknown(self):
        """Unknown provider falls back to edge."""
        from nexus.voice.tts import TTSEngine

        tts = TTSEngine(provider_name="unknown")
        assert tts.provider_name == "Edge TTS"

    def test_tts_voice_setter(self):
        """TTS voice can be changed."""
        from nexus.voice.tts import TTSEngine

        tts = TTSEngine()
        tts.voice = "en-US-GuyNeural"
        assert tts.voice == "en-US-GuyNeural"

    def test_tts_speed_setter(self):
        """TTS speed is clamped to valid range."""
        from nexus.voice.tts import TTSEngine

        tts = TTSEngine()
        tts.speed = 2.0
        assert tts.speed == 2.0
        tts.speed = 0.1  # Below min
        assert tts.speed == 0.25
        tts.speed = 10.0  # Above max
        assert tts.speed == 4.0

    def test_tts_stop_request(self):
        """TTS stop request sets the flag."""
        from nexus.voice.tts import TTSEngine

        tts = TTSEngine()
        assert not tts._stop_requested
        tts.request_stop()
        assert tts._stop_requested
        tts.reset_stop()
        assert not tts._stop_requested

    def test_tts_is_speaking(self):
        """is_speaking reflects current state."""
        from nexus.voice.tts import TTSEngine

        tts = TTSEngine()
        assert tts.is_speaking is False

    @pytest.mark.asyncio
    async def test_tts_check_availability(self):
        """TTS availability check works."""
        from nexus.voice.tts import TTSEngine

        tts = TTSEngine(provider_name="edge")
        available = await tts.check_availability()
        assert isinstance(available, bool)


class TestSentenceSplitting:
    """Tests for sentence splitting used in interruptible TTS."""

    def test_split_simple(self):
        from nexus.voice.tts import _split_sentences

        result = _split_sentences("Hello world. How are you?")
        assert len(result) == 2
        assert result[0] == "Hello world."
        assert result[1] == "How are you?"

    def test_split_exclamation(self):
        from nexus.voice.tts import _split_sentences

        # "Wow!" is < 10 chars so gets merged with next sentence
        result = _split_sentences("Wow! That's amazing. Really!")
        assert len(result) == 2

    def test_split_empty(self):
        from nexus.voice.tts import _split_sentences

        result = _split_sentences("")
        assert result == []

    def test_split_single_sentence(self):
        from nexus.voice.tts import _split_sentences

        result = _split_sentences("Just one sentence")
        assert result == ["Just one sentence"]

    def test_split_merges_short_fragments(self):
        from nexus.voice.tts import _split_sentences

        # "Oh." is < 10 chars and should be merged
        result = _split_sentences("Hello world. Oh. That's interesting.")
        # "Oh." should get merged with "Hello world."
        assert any("Oh." in s for s in result)

    def test_split_preserves_punctuation(self):
        from nexus.voice.tts import _split_sentences

        result = _split_sentences("First sentence. Second sentence!")
        assert result[0].endswith(".")
        assert result[1].endswith("!")


# ---------------------------------------------------------------------------
# Pipeline Tests
# ---------------------------------------------------------------------------


class TestPipelineState:
    """Tests for the VoicePipeline state machine."""

    def test_pipeline_states_exist(self):
        """All pipeline states are defined."""
        from nexus.voice.pipeline import PipelineState

        assert PipelineState.STOPPED.value == "stopped"
        assert PipelineState.IDLE.value == "idle"
        assert PipelineState.LISTENING.value == "listening"
        assert PipelineState.PROCESSING.value == "processing"
        assert PipelineState.SPEAKING.value == "speaking"
        assert PipelineState.ERROR.value == "error"

    def test_interaction_modes(self):
        """All interaction modes are defined."""
        from nexus.voice.pipeline import InteractionMode

        assert InteractionMode.VOICE_AND_TEXT.value == "voice_and_text"
        assert InteractionMode.VOICE_ONLY.value == "voice_only"
        assert InteractionMode.TEXT_ONLY.value == "text_only"

    def test_input_modes(self):
        """All input modes are defined."""
        from nexus.voice.pipeline import InputMode

        assert InputMode.VOICE.value == "voice"
        assert InputMode.TEXT.value == "text"


class TestVoicePipeline:
    """Tests for the VoicePipeline orchestrator."""

    def _make_mock_brain(self):
        """Create a mock NexusBrain."""
        brain = MagicMock()
        brain.process = AsyncMock(return_value="I'm NEXUS, your AI assistant.")
        brain._settings = MagicMock()
        brain._settings.voice.sample_rate = 16000
        brain._settings.voice.stt_provider = "google_web"
        brain._settings.voice.tts_provider = "edge"
        brain._settings.voice.tts.voice = "en-US-JennyNeural"
        brain._settings.voice.tts.speed = 1.0
        brain._settings.voice.tts.fallback_voice = ""
        brain._settings.voice.language = "en-US"
        brain._settings.voice.silence_threshold_ms = 1500
        brain._settings.voice.vad.threshold = 0.5
        brain._settings.voice.vad.min_speech_ms = 250
        brain._settings.voice.vad.energy_threshold = 300
        brain._settings.voice.interaction_mode = "voice_and_text"
        brain._settings.voice.interrupt_enabled = True
        return brain

    def _make_pipeline(self, brain=None, **kwargs):
        """Create a VoicePipeline with mocked audio/VAD/STT/TTS components."""
        if brain is None:
            brain = self._make_mock_brain()

        # Patch the component imports inside the pipeline __init__
        with (
            patch("nexus.voice.audio_io.AudioRecorder"),
            patch("nexus.voice.audio_io.AudioPlayer"),
            patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"),
            patch("nexus.voice.stt.STTEngine._init_provider"),
            patch("nexus.voice.tts.TTSEngine._init_providers"),
        ):
            from nexus.voice.pipeline import VoicePipeline

            pipeline = VoicePipeline(brain=brain, **kwargs)

            # Set mock attributes for status
            pipeline._stt._provider_name = "google_web"
            pipeline._stt._provider = MagicMock()
            pipeline._stt._provider.provider_name = "Google Web Speech"
            pipeline._stt._language = "en-US"
            pipeline._tts._provider = MagicMock()
            pipeline._tts._provider.provider_name = "Edge TTS"
            pipeline._tts._fallback_provider = MagicMock()
            pipeline._tts._voice = "en-US-JennyNeural"
            pipeline._tts._speed = 1.0
            pipeline._tts._stop_requested = False
            pipeline._tts._is_speaking = False

            return pipeline

    def test_pipeline_init(self):
        """Pipeline initializes all components."""
        from nexus.voice.pipeline import PipelineState

        pipeline = self._make_pipeline()

        assert pipeline.state == PipelineState.STOPPED
        assert pipeline.is_running is False

    def test_pipeline_interaction_mode(self):
        """Interaction mode can be changed."""
        from nexus.voice.pipeline import InteractionMode

        pipeline = self._make_pipeline()

        assert pipeline.interaction_mode == InteractionMode.VOICE_AND_TEXT
        pipeline.interaction_mode = "text_only"
        assert pipeline.interaction_mode == InteractionMode.TEXT_ONLY

    def test_pipeline_language_change(self):
        """Language can be changed at runtime."""
        pipeline = self._make_pipeline(language="en-US")

        assert pipeline.language == "en-US"
        pipeline.language = "ta-IN"
        assert pipeline.language == "ta-IN"

    def test_pipeline_get_status(self):
        """get_status returns a complete status dict."""
        pipeline = self._make_pipeline()
        status = pipeline.get_status()

        assert "state" in status
        assert "running" in status
        assert "interaction_mode" in status
        assert "stt_provider" in status
        assert "tts_provider" in status
        assert "tts_voice" in status
        assert "tts_speed" in status
        assert "language" in status
        assert "interrupt_enabled" in status

    def test_pipeline_state_callbacks(self):
        """State change callbacks are invoked."""
        from nexus.voice.pipeline import PipelineState

        pipeline = self._make_pipeline()

        states_received = []
        pipeline.on_state_change(lambda s: states_received.append(s))

        pipeline._set_state(PipelineState.IDLE)
        pipeline._set_state(PipelineState.LISTENING)

        assert PipelineState.IDLE in states_received
        assert PipelineState.LISTENING in states_received

    @pytest.mark.asyncio
    async def test_pipeline_text_only_no_start(self):
        """Pipeline does not start in text_only mode."""
        from nexus.voice.pipeline import PipelineState

        pipeline = self._make_pipeline(interaction_mode="text_only")

        await pipeline.start()
        assert pipeline.is_running is False
        assert pipeline.state == PipelineState.STOPPED

    @pytest.mark.asyncio
    async def test_pipeline_process_text_input(self):
        """Text input is processed through the brain without TTS."""
        brain = self._make_mock_brain()
        pipeline = self._make_pipeline(brain=brain)

        response = await pipeline.process_text_input("Hello NEXUS")
        assert response == "I'm NEXUS, your AI assistant."
        brain.process.assert_called_once_with("Hello NEXUS")

    @pytest.mark.asyncio
    async def test_pipeline_stop_when_not_running(self):
        """Stopping when not running is a no-op."""
        pipeline = self._make_pipeline()

        # Should not raise
        await pipeline.stop()
        assert pipeline.is_running is False


# ---------------------------------------------------------------------------
# Configuration Tests
# ---------------------------------------------------------------------------


class TestVoiceConfig:
    """Tests for voice configuration models."""

    def test_voice_settings_defaults(self):
        from nexus.core.config import VoiceSettings

        vs = VoiceSettings()
        assert vs.enabled is False
        assert vs.stt_provider == "google_web"
        assert vs.tts_provider == "edge"
        assert vs.interaction_mode == "voice_and_text"
        assert vs.language == "en-US"
        assert vs.interrupt_enabled is True
        assert vs.sample_rate == 16000

    def test_voice_tts_settings_defaults(self):
        from nexus.core.config import VoiceTTSSettings

        tts = VoiceTTSSettings()
        assert tts.voice == "en-US-JennyNeural"
        assert tts.speed == 1.0

    def test_voice_vad_settings_defaults(self):
        from nexus.core.config import VoiceVADSettings

        vad = VoiceVADSettings()
        assert vad.threshold == 0.5
        assert vad.min_speech_ms == 250
        assert vad.energy_threshold == 300

    def test_voice_stt_settings_defaults(self):
        from nexus.core.config import VoiceSTTSettings

        stt = VoiceSTTSettings()
        assert stt.language == "en-US"
        assert "en-US" in stt.supported_languages


# ---------------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------------


class TestVoiceErrorHandling:
    """Tests for error handling in the voice system."""

    def test_stt_error(self):
        from nexus.voice.stt import STTError

        err = STTError("test error")
        assert str(err) == "test error"

    def test_tts_error(self):
        from nexus.voice.tts import TTSError

        err = TTSError("test error")
        assert str(err) == "test error"

    @pytest.mark.asyncio
    async def test_stt_transcribe_provider_error(self):
        """STT wraps provider errors into STTError."""
        from nexus.voice.stt import STTEngine, STTError

        stt = STTEngine(provider_name="google_web")
        assert stt._provider is not None
        stt._provider.transcribe = AsyncMock(side_effect=Exception("network error"))

        with pytest.raises(STTError, match="Transcription failed"):
            await stt.transcribe(_make_audio(1.0))

    @pytest.mark.asyncio
    async def test_tts_synthesize_with_fallback(self):
        """TTS falls back to pyttsx3 when edge fails."""
        from nexus.voice.tts import TTSEngine, TTSError

        tts = TTSEngine(provider_name="edge")
        assert tts._provider is not None
        assert tts._fallback_provider is not None

        # Mock primary to fail
        tts._provider.synthesize = AsyncMock(side_effect=TTSError("edge down"))

        # Mock fallback to succeed
        tts._fallback_provider.synthesize = AsyncMock(return_value=b"fake_audio")

        result = await tts.synthesize("hello")
        assert result == b"fake_audio"

    @pytest.mark.asyncio
    async def test_tts_synthesize_both_fail(self):
        """TTSError raised when both primary and fallback fail."""
        from nexus.voice.tts import TTSEngine, TTSError

        tts = TTSEngine(provider_name="edge")
        assert tts._provider is not None
        assert tts._fallback_provider is not None

        tts._provider.synthesize = AsyncMock(side_effect=TTSError("edge down"))
        tts._fallback_provider.synthesize = AsyncMock(side_effect=TTSError("pyttsx3 down"))

        with pytest.raises(TTSError):
            await tts.synthesize("hello")


# ---------------------------------------------------------------------------
# Pipeline Flow & Interruption Tests
# ---------------------------------------------------------------------------


class TestVoicePipelineFlow:
    """Tests for the VoicePipeline execution flow and interruption."""

    @pytest.mark.asyncio
    async def test_process_speech_full_flow(self):
        """_process_speech executes STT, brain, and TTS."""

        brain = MagicMock()
        brain.process = AsyncMock(return_value="Speech response processed.")
        brain._settings = MagicMock()
        brain._settings.voice.sample_rate = 16000
        brain._settings.voice.stt_provider = "google_web"
        brain._settings.voice.tts_provider = "edge"
        brain._settings.voice.tts.voice = "en-US-JennyNeural"
        brain._settings.voice.tts.speed = 1.0
        brain._settings.voice.tts.fallback_voice = ""
        brain._settings.voice.language = "en-US"
        brain._settings.voice.silence_threshold_ms = 1500
        brain._settings.voice.vad.threshold = 0.5
        brain._settings.voice.vad.min_speech_ms = 250
        brain._settings.voice.vad.energy_threshold = 300
        brain._settings.voice.interaction_mode = "voice_and_text"
        brain._settings.voice.interrupt_enabled = True

        with (
            patch("nexus.voice.audio_io.AudioRecorder"),
            patch("nexus.voice.audio_io.AudioPlayer"),
            patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"),
            patch("nexus.voice.stt.STTEngine._init_provider"),
            patch("nexus.voice.tts.TTSEngine._init_providers"),
        ):
            from nexus.voice.pipeline import VoicePipeline

            pipeline = VoicePipeline(brain=brain)
            pipeline._stt.transcribe = AsyncMock(return_value="hello nexus")
            pipeline._speak_response = AsyncMock()

            audio_segment = _make_audio(0.5)
            await pipeline._process_speech(audio_segment)

            pipeline._stt.transcribe.assert_called_once()
            brain.process.assert_called_once_with("hello nexus")
            pipeline._speak_response.assert_called_once_with("Speech response processed.")

    @pytest.mark.asyncio
    async def test_process_speech_empty_stt(self):
        """Empty STT output does not call brain."""
        brain = MagicMock()
        brain.process = AsyncMock()

        with (
            patch("nexus.voice.audio_io.AudioRecorder"),
            patch("nexus.voice.audio_io.AudioPlayer"),
            patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"),
            patch("nexus.voice.stt.STTEngine._init_provider"),
            patch("nexus.voice.tts.TTSEngine._init_providers"),
        ):
            from nexus.voice.pipeline import PipelineState, VoicePipeline

            pipeline = VoicePipeline(brain=brain)
            pipeline._stt.transcribe = AsyncMock(return_value="   ")
            pipeline._speak_response = AsyncMock()

            await pipeline._process_speech(_make_audio(0.5))

            brain.process.assert_not_called()
            pipeline._speak_response.assert_not_called()
            assert pipeline.state == PipelineState.IDLE

    @pytest.mark.asyncio
    async def test_process_voice_text(self):
        """process_voice_text triggers brain processing and TTS speaking."""
        brain = MagicMock()
        brain.process = AsyncMock(return_value="Processed text to voice.")

        with (
            patch("nexus.voice.audio_io.AudioRecorder"),
            patch("nexus.voice.audio_io.AudioPlayer"),
            patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"),
            patch("nexus.voice.stt.STTEngine._init_provider"),
            patch("nexus.voice.tts.TTSEngine._init_providers"),
        ):
            from nexus.voice.pipeline import VoicePipeline

            pipeline = VoicePipeline(brain=brain)
            pipeline._speak_response = AsyncMock()

            result = await pipeline.process_voice_text("Read this out")
            assert result == "Processed text to voice."
            brain.process.assert_called_once_with("Read this out")
            pipeline._speak_response.assert_called_once_with("Processed text to voice.")

    @pytest.mark.asyncio
    async def test_speak_response_interrupted(self):
        """_speak_response halts when stop is requested."""
        brain = MagicMock()

        with (
            patch("nexus.voice.audio_io.AudioRecorder"),
            patch("nexus.voice.audio_io.AudioPlayer"),
            patch("nexus.voice.vad.VoiceActivityDetector._load_vad_model"),
            patch("nexus.voice.stt.STTEngine._init_provider"),
            patch("nexus.voice.tts.TTSEngine._init_providers"),
        ):
            from nexus.voice.pipeline import VoicePipeline

            pipeline = VoicePipeline(brain=brain)
            pipeline._running = True
            pipeline._tts.synthesize = AsyncMock(return_value=b"audio_chunk")
            pipeline._play_tts_audio = AsyncMock()

            # Set stop requested to simulate interruption after first synthesize
            async def mock_synth(text):
                pipeline._tts.request_stop()
                return b"audio_chunk"

            pipeline._tts.synthesize = AsyncMock(side_effect=mock_synth)

            await pipeline._speak_response("First sentence. Second sentence.")
            # Should have called synth only once because stop was requested
            assert pipeline._tts.synthesize.call_count == 1


# ---------------------------------------------------------------------------
# Voice API Route Tests
# ---------------------------------------------------------------------------


class TestVoiceAPIRoutes:
    """Tests for FastAPI voice endpoints."""

    @pytest.fixture
    def test_client(self):
        from fastapi.testclient import TestClient

        from nexus.api.app import create_app
        from nexus.core.config import get_settings

        settings = get_settings()
        app = create_app(settings)

        with TestClient(app) as client:
            # Create and attach mock brain after lifespan startup
            mock_brain = MagicMock()
            mock_brain.is_voice_active = False
            mock_brain.voice_pipeline = None
            mock_brain.start_voice = AsyncMock()
            mock_brain.stop_voice = AsyncMock()
            app.state.brain = mock_brain
            yield client, mock_brain

    def test_get_voice_config_default(self, test_client):
        client, _ = test_client
        response = client.get("/api/voice/config")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert data["running"] is False
        assert data["state"] == "stopped"

    def test_update_voice_config(self, test_client):
        client, mock_brain = test_client
        mock_pipeline = MagicMock()
        mock_pipeline.get_status.return_value = {
            "state": "idle",
            "running": True,
            "interaction_mode": "text_only",
            "language": "en-US",
            "stt_provider": "Google Web Speech",
            "tts_provider": "Edge TTS",
            "tts_voice": "en-US-JennyNeural",
            "tts_speed": 1.2,
            "vad_uses_silero": False,
            "interrupt_enabled": True,
            "recorder_active": False,
        }
        mock_brain.voice_pipeline = mock_pipeline
        response = client.put(
            "/api/voice/config",
            json={"interaction_mode": "text_only", "tts_speed": 1.2},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["interaction_mode"] == "text_only"

    def test_get_voice_status(self, test_client):
        client, _ = test_client
        with patch("nexus.voice.tts.TTSEngine.list_voices", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [{"id": "v1", "name": "Voice 1"}]
            response = client.get("/api/voice/status")
            assert response.status_code == 200
            data = response.json()
            assert "pipeline" in data
            assert "available_voices" in data

    def test_start_voice_endpoint(self, test_client):
        client, mock_brain = test_client
        response = client.post("/api/voice/start")
        assert response.status_code == 200
        assert response.json()["status"] == "started"
        mock_brain.start_voice.assert_called_once()

    def test_stop_voice_endpoint(self, test_client):
        client, mock_brain = test_client
        mock_brain.is_voice_active = True
        response = client.post("/api/voice/stop")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"
        mock_brain.stop_voice.assert_called_once()

    def test_transcribe_endpoint(self, test_client):
        from nexus.voice.audio_io import audio_to_wav_bytes

        client, _ = test_client
        audio = _make_audio(0.5)
        wav_bytes = audio_to_wav_bytes(audio, 16000)

        with patch("nexus.voice.stt.STTEngine.transcribe", new_callable=AsyncMock) as mock_stt:
            mock_stt.return_value = "transcribed speech"
            response = client.post(
                "/api/voice/transcribe",
                files={"audio": ("test.wav", wav_bytes, "audio/wav")},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["text"] == "transcribed speech"

    def test_synthesize_endpoint(self, test_client):
        client, _ = test_client
        with patch("nexus.voice.tts.TTSEngine.synthesize", new_callable=AsyncMock) as mock_synth:
            mock_synth.return_value = b"fake_audio_mp3"
            response = client.post(
                "/api/voice/synthesize",
                json={"text": "Hello world", "speed": 1.0},
            )
            assert response.status_code == 200
            assert response.content == b"fake_audio_mp3"


# ---------------------------------------------------------------------------
# CLI Voice Command Helper Tests
# ---------------------------------------------------------------------------


class TestVoiceCLI:
    """Tests for CLI voice helper functions."""

    @pytest.mark.asyncio
    async def test_toggle_voice_turns_on(self):
        from nexus.cli import _toggle_voice

        brain = MagicMock()
        brain.is_voice_active = False
        brain.start_voice = AsyncMock()

        await _toggle_voice(brain)
        brain.start_voice.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_voice_turns_off(self):
        from nexus.cli import _toggle_voice

        brain = MagicMock()
        brain.is_voice_active = True
        brain.stop_voice = AsyncMock()

        await _toggle_voice(brain)
        brain.stop_voice.assert_called_once()

    def test_print_voice_config_no_crash(self):
        from nexus.cli import _print_voice_config

        brain = MagicMock()
        brain.voice_pipeline = None
        # Should execute without error
        _print_voice_config(brain)

        # With mock active pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.get_status.return_value = {
            "state": "idle",
            "running": True,
            "interaction_mode": "voice_and_text",
            "language": "en-US",
            "stt_provider": "Google Web Speech",
            "tts_provider": "Edge TTS",
            "tts_voice": "en-US-JennyNeural",
            "tts_speed": 1.0,
            "vad_uses_silero": False,
            "interrupt_enabled": True,
            "recorder_active": True,
        }
        brain.voice_pipeline = mock_pipeline
        _print_voice_config(brain)


# ---------------------------------------------------------------------------
# Integration Tests (no hardware required)
# ---------------------------------------------------------------------------


class TestVoiceModuleImports:
    """Verify all voice module exports are importable."""

    def test_import_voice_package(self):
        from nexus.voice import (
            AudioPlayer,
            AudioRecorder,
            InputMode,
            InteractionMode,
            PipelineState,
            STTEngine,
            STTError,
            TTSEngine,
            TTSError,
            VADState,
            VoiceActivityDetector,
            VoicePipeline,
            audio_to_wav_bytes,
            wav_bytes_to_audio,
        )

        assert AudioPlayer is not None
        assert AudioRecorder is not None
        assert InputMode.VOICE == "voice"
        assert InteractionMode.VOICE_AND_TEXT == "voice_and_text"
        assert PipelineState.IDLE == "idle"
        assert STTEngine is not None
        assert STTError is not None
        assert TTSEngine is not None
        assert TTSError is not None
        assert VADState.SPEECH == "speech"
        assert VoiceActivityDetector is not None
        assert VoicePipeline is not None
        assert callable(audio_to_wav_bytes)
        assert callable(wav_bytes_to_audio)

    def test_import_api_schemas(self):
        from nexus.api.schemas import (
            VoiceConfigResponse,
            VoiceConfigUpdate,
            VoiceStatusResponse,
            VoiceSynthesizeRequest,
            VoiceSynthesizeResponse,
            VoiceTranscribeResponse,
        )

        assert VoiceConfigResponse is not None
        assert VoiceConfigUpdate is not None
        assert VoiceStatusResponse is not None
        assert VoiceSynthesizeRequest is not None
        assert VoiceSynthesizeResponse is not None
        assert VoiceTranscribeResponse is not None
