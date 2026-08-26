"""
NEXUS API — Pydantic Schemas.

Request and response models for the REST API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    message: str = Field(..., min_length=1, description="The user's message.")
    conversation_id: str | None = Field(
        None, description="Optional conversation ID to continue an existing conversation."
    )


class ToolCallInfo(BaseModel):
    """Information about a tool call made during response generation."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    success: bool = True


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""

    response: str
    conversation_id: str
    model_used: str | None = None
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)


class ChatResetResponse(BaseModel):
    """Response from the chat reset endpoint."""

    message: str = "Conversation reset successfully."


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


class MessageSchema(BaseModel):
    """A single message in a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    timestamp: datetime


class ConversationSummary(BaseModel):
    """Summary of a conversation for listing."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    summary: str | None = None
    created_at: datetime
    message_count: int = 0


class ConversationDetail(BaseModel):
    """Full conversation with messages."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    summary: str | None = None
    created_at: datetime
    messages: list[MessageSchema] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    """Paginated list of conversations."""

    conversations: list[ConversationSummary]
    total: int
    page: int = 1
    page_size: int = 20


class DeleteResponse(BaseModel):
    """Response for delete operations."""

    message: str
    deleted_id: str


class ConversationUpdateRequest(BaseModel):
    """Request to update a conversation."""

    summary: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response from the health check endpoint."""

    status: str = "ok"
    version: str
    uptime_seconds: float
    llm_providers: list[str] = Field(default_factory=list)
    tool_count: int = 0
    database_status: str = "unknown"
    environment: str = "development"


# ---------------------------------------------------------------------------
# Voice (Phase 2)
# ---------------------------------------------------------------------------


class VoiceTranscribeResponse(BaseModel):
    """Response from the voice transcription endpoint."""

    text: str
    language: str = "en-US"
    provider: str = ""
    success: bool = True
    error: str | None = None


class VoiceSynthesizeRequest(BaseModel):
    """Request body for the voice synthesis endpoint."""

    text: str = Field(..., min_length=1, description="Text to synthesize to speech.")
    voice: str | None = Field(None, description="Override TTS voice.")
    speed: float | None = Field(None, ge=0.25, le=4.0, description="Speaking speed multiplier.")


class VoiceSynthesizeResponse(BaseModel):
    """Response from the voice synthesis endpoint."""

    success: bool = True
    audio_format: str = "mp3"
    duration_estimate_ms: int = 0
    error: str | None = None


class VoiceConfigResponse(BaseModel):
    """Current voice configuration and status."""

    enabled: bool = False
    running: bool = False
    state: str = "stopped"
    interaction_mode: str = "voice_and_text"
    language: str = "en-US"
    stt_provider: str = ""
    tts_provider: str = ""
    tts_voice: str = ""
    tts_speed: float = 1.0
    interrupt_enabled: bool = True
    vad_uses_silero: bool = False


class VoiceConfigUpdate(BaseModel):
    """Request to update voice configuration."""

    interaction_mode: str | None = Field(
        None,
        description="voice_and_text | voice_only | text_only",
    )
    tts_voice: str | None = Field(None, description="TTS voice identifier.")
    tts_speed: float | None = Field(None, ge=0.25, le=4.0, description="Speaking speed.")
    language: str | None = Field(None, description="Language code (e.g., en-US).")


class VoiceStatusResponse(BaseModel):
    """Response with detailed voice pipeline status."""

    pipeline: VoiceConfigResponse
    available_voices: list[dict[str, str]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Identity & Wake Word (Phase 3)
# ---------------------------------------------------------------------------


class IdentityResponse(BaseModel):
    """Assistant identity information."""

    assistant_name: str
    user_name: str
    wake_word: str
    aliases: list[str] = Field(default_factory=list)
    all_wake_words: list[str] = Field(default_factory=list)
    require_wake_word: bool = False
    has_pending_confirmation: bool = False
    pending_action: str | None = None


class IdentityUpdateRequest(BaseModel):
    """Request body for updating identity settings."""

    assistant_name: str | None = Field(None, min_length=1, description="New assistant name.")
    user_name: str | None = Field(None, min_length=1, description="New user name.")
    wake_word: str | None = Field(None, min_length=1, description="New primary wake word.")
    aliases: list[str] | None = Field(None, description="Updated list of aliases.")
    require_wake_word: bool | None = Field(None, description="Require wake word in voice mode.")


class NameChangeRequest(BaseModel):
    """Request to initiate an assistant name change."""

    name: str = Field(..., min_length=1, description="The requested new name for the assistant.")


class NameChangeResponse(BaseModel):
    """Response from initiating a name change."""

    status: str = "pending_confirmation"
    current_name: str
    target_name: str
    confirmation_prompt: str


class ConfirmationRequest(BaseModel):
    """Request to confirm or reject a pending action."""

    confirmed: bool = Field(..., description="True to confirm, False to reject.")
    response_text: str | None = Field(
        None,
        description="Optional natural language response ('yes', 'no').",
    )


class ConfirmationResponse(BaseModel):
    """Response after handling a confirmation request."""

    status: str
    message: str
    confirmed: bool


class WakeWordDetectRequest(BaseModel):
    """Request to test wake word detection on input text."""

    text: str = Field(..., min_length=1, description="Text to analyze for wake word.")


class WakeWordDetectResponse(BaseModel):
    """Result of wake word detection."""

    matched: bool
    wake_word: str = ""
    prefix: str | None = None
    command: str = ""
    raw_text: str
