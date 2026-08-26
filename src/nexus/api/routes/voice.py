"""
NEXUS API — Voice Routes.

REST endpoints for voice transcription, synthesis, and configuration.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

from nexus.api.schemas import (
    VoiceConfigResponse,
    VoiceConfigUpdate,
    VoiceStatusResponse,
    VoiceSynthesizeRequest,
    VoiceTranscribeResponse,
)
from nexus.utils.logging import get_logger
from nexus.voice.stt import STTError
from nexus.voice.tts import TTSError

log = get_logger("api.voice")

router = APIRouter(prefix="/voice", tags=["voice"])


def _get_brain(request: Request):
    """Get the NexusBrain from app state."""
    return request.app.state.brain


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------


@router.post(
    "/transcribe",
    response_model=VoiceTranscribeResponse,
    summary="Transcribe audio to text",
)
async def transcribe_audio(
    request: Request,
    audio: UploadFile = File(..., description="Audio file (WAV, 16kHz mono preferred)"),
    language: str = "en-US",
) -> VoiceTranscribeResponse:
    """
    Upload an audio file and get the transcribed text.

    Supports WAV format (16kHz, 16-bit, mono recommended).
    """
    try:
        from nexus.voice.audio_io import wav_bytes_to_audio
        from nexus.voice.stt import STTEngine

        settings = request.app.state.settings

        # Read audio file
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # Convert WAV to numpy array
        try:
            audio_data, sample_rate = wav_bytes_to_audio(audio_bytes)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail="Invalid audio format. Please upload a WAV file.",
            ) from e

        # Transcribe
        stt = STTEngine(
            provider_name=settings.voice.stt_provider,
            language=language,
        )
        text = await stt.transcribe(audio_data, sample_rate, language)

        return VoiceTranscribeResponse(
            text=text,
            language=language,
            provider=stt.provider_name,
            success=True,
        )

    except STTError as e:
        return VoiceTranscribeResponse(
            text="",
            language=language,
            success=False,
            error=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("Transcription error: %s", e)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}") from e


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------


@router.post(
    "/synthesize",
    summary="Synthesize text to speech audio",
)
async def synthesize_speech(
    request: Request,
    body: VoiceSynthesizeRequest,
) -> Response:
    """
    Convert text to speech audio.

    Returns audio bytes (MP3 for Edge TTS, WAV for pyttsx3).
    """
    try:
        from nexus.voice.tts import TTSEngine

        settings = request.app.state.settings

        tts = TTSEngine(
            provider_name=settings.voice.tts_provider,
            voice=body.voice or settings.voice.tts.voice,
            speed=body.speed or settings.voice.tts.speed,
        )

        audio_bytes = await tts.synthesize(body.text)

        # Determine content type based on provider
        content_type = "audio/mpeg" if settings.voice.tts_provider == "edge" else "audio/wav"

        return Response(
            content=audio_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": "attachment; filename=speech.mp3",
            },
        )

    except TTSError as e:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {e}") from e
    except Exception as e:
        log.error("Synthesis error: %s", e)
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {e}") from e


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@router.get(
    "/config",
    response_model=VoiceConfigResponse,
    summary="Get voice configuration",
)
async def get_voice_config(request: Request) -> VoiceConfigResponse:
    """Get the current voice configuration and pipeline status."""
    brain = _get_brain(request)
    settings = request.app.state.settings

    if brain.voice_pipeline is not None:
        status = brain.voice_pipeline.get_status()
        return VoiceConfigResponse(
            enabled=settings.voice.enabled,
            running=status["running"],
            state=status["state"],
            interaction_mode=status["interaction_mode"],
            language=status["language"],
            stt_provider=status["stt_provider"],
            tts_provider=status["tts_provider"],
            tts_voice=status["tts_voice"],
            tts_speed=status["tts_speed"],
            interrupt_enabled=status["interrupt_enabled"],
            vad_uses_silero=status["vad_uses_silero"],
        )

    return VoiceConfigResponse(
        enabled=settings.voice.enabled,
        running=False,
        state="stopped",
        interaction_mode=settings.voice.interaction_mode,
        language=settings.voice.language,
        stt_provider=settings.voice.stt_provider,
        tts_provider=settings.voice.tts_provider,
        tts_voice=settings.voice.tts.voice,
        tts_speed=settings.voice.tts.speed,
        interrupt_enabled=settings.voice.interrupt_enabled,
    )


@router.put(
    "/config",
    response_model=VoiceConfigResponse,
    summary="Update voice configuration",
)
async def update_voice_config(
    request: Request,
    body: VoiceConfigUpdate,
) -> VoiceConfigResponse:
    """Update voice configuration (applied to the running pipeline if active)."""
    brain = _get_brain(request)

    if brain.voice_pipeline is None:
        raise HTTPException(
            status_code=400,
            detail="Voice pipeline is not running. Start it first.",
        )

    pipeline = brain.voice_pipeline

    if body.interaction_mode is not None:
        try:
            pipeline.interaction_mode = body.interaction_mode
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid interaction mode: {body.interaction_mode}",
            ) from e

    if body.tts_voice is not None:
        pipeline.tts_engine.voice = body.tts_voice

    if body.tts_speed is not None:
        pipeline.tts_engine.speed = body.tts_speed

    if body.language is not None:
        pipeline.language = body.language

    return await get_voice_config(request)


@router.get(
    "/status",
    response_model=VoiceStatusResponse,
    summary="Get detailed voice status with available voices",
)
async def get_voice_status(request: Request) -> VoiceStatusResponse:
    """Get detailed voice pipeline status including available voices."""
    config = await get_voice_config(request)

    # Get available voices
    voices: list[dict[str, str]] = []
    try:
        from nexus.voice.tts import TTSEngine

        settings = request.app.state.settings
        tts = TTSEngine(provider_name=settings.voice.tts_provider)
        voices = await tts.list_voices()
    except Exception as e:
        log.debug("Could not list voices: %s", e)

    return VoiceStatusResponse(
        pipeline=config,
        available_voices=voices[:20],  # Limit to 20 voices
    )


# ---------------------------------------------------------------------------
# Pipeline Control
# ---------------------------------------------------------------------------


@router.post("/start", summary="Start the voice pipeline")
async def start_voice(request: Request) -> dict:
    """Start the voice pipeline for real-time voice interaction."""
    brain = _get_brain(request)

    if brain.is_voice_active:
        return {"status": "already_running", "message": "Voice pipeline is already running"}

    try:
        await brain.start_voice()
        return {"status": "started", "message": "Voice pipeline started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start voice: {e}") from e


@router.post("/stop", summary="Stop the voice pipeline")
async def stop_voice(request: Request) -> dict:
    """Stop the voice pipeline."""
    brain = _get_brain(request)

    if not brain.is_voice_active:
        return {"status": "already_stopped", "message": "Voice pipeline is not running"}

    await brain.stop_voice()
    return {"status": "stopped", "message": "Voice pipeline stopped"}
