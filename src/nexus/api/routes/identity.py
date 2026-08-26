"""
NEXUS API — Identity & Wake Word Routes (Phase 3).

REST endpoints for managing assistant name, wake word configuration,
aliases, and two-step confirmation verification.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from nexus.api.schemas import (
    ConfirmationRequest,
    ConfirmationResponse,
    IdentityResponse,
    IdentityUpdateRequest,
    NameChangeRequest,
    NameChangeResponse,
    WakeWordDetectRequest,
    WakeWordDetectResponse,
)
from nexus.utils.logging import get_logger

log = get_logger("api.identity")

router = APIRouter(prefix="/identity", tags=["identity"])


def _get_brain(request: Request):
    """Get the NexusBrain from app state."""
    return request.app.state.brain


@router.get(
    "",
    response_model=IdentityResponse,
    summary="Get current assistant identity configuration",
)
async def get_identity(request: Request) -> IdentityResponse:
    """Retrieve current assistant name, user name, wake words, and aliases."""
    brain = _get_brain(request)
    identity = brain.identity
    has_pending = brain.confirmation.has_pending
    pending_action = (
        str(brain.confirmation.pending_action.action)
        if has_pending and brain.confirmation.pending_action
        else None
    )

    return IdentityResponse(
        assistant_name=identity.name,
        user_name=identity.user_name,
        wake_word=identity.wake_word,
        aliases=identity.aliases,
        all_wake_words=identity.all_wake_words,
        require_wake_word=identity.config.require_wake_word,
        has_pending_confirmation=has_pending,
        pending_action=pending_action,
    )


@router.put(
    "",
    response_model=IdentityResponse,
    summary="Update identity settings directly",
)
async def update_identity(
    request: Request,
    body: IdentityUpdateRequest,
) -> IdentityResponse:
    """Directly update identity settings (e.g. user_name, require_wake_word, aliases)."""
    brain = _get_brain(request)
    identity = brain.identity

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return await get_identity(request)

    identity.update(**updates)
    brain._refresh_system_prompt()

    # Sync with running voice pipeline if active
    if brain.voice_pipeline is not None:
        brain.voice_pipeline.wake_word_detector.update_wake_words(
            primary=identity.wake_word,
            aliases=identity.aliases,
        )
        if body.require_wake_word is not None:
            brain.voice_pipeline.require_wake_word = body.require_wake_word

    return await get_identity(request)


@router.post(
    "/change-name",
    response_model=NameChangeResponse,
    summary="Initiate assistant name change with confirmation",
)
async def initiate_name_change(
    request: Request,
    body: NameChangeRequest,
) -> NameChangeResponse:
    """
    Request a name change for the assistant.

    Creates a pending confirmation request and returns the confirmation prompt.
    The name is not updated until confirmed via `/api/identity/confirm` or voice/chat confirmation.
    """
    brain = _get_brain(request)
    target_name = body.name.strip()
    if not target_name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    prompt = brain.request_name_change(target_name)

    return NameChangeResponse(
        status="pending_confirmation",
        current_name=brain.name,
        target_name=target_name,
        confirmation_prompt=prompt,
    )


@router.post(
    "/confirm",
    response_model=ConfirmationResponse,
    summary="Confirm or reject a pending identity/settings change",
)
async def confirm_action(
    request: Request,
    body: ConfirmationRequest,
) -> ConfirmationResponse:
    """Confirm or reject a currently pending action."""
    brain = _get_brain(request)

    if not brain.confirmation.has_pending:
        raise HTTPException(
            status_code=400,
            detail="No confirmation request is currently pending or it has expired.",
        )

    if body.confirmed:
        status, message = await brain.confirmation.confirm()
        return ConfirmationResponse(
            status=status.value,
            message=message,
            confirmed=True,
        )
    else:
        status, message = await brain.confirmation.reject()
        return ConfirmationResponse(
            status=status.value,
            message=message,
            confirmed=False,
        )


@router.post(
    "/cancel",
    response_model=ConfirmationResponse,
    summary="Cancel any pending confirmation immediately",
)
async def cancel_pending_confirmation(request: Request) -> ConfirmationResponse:
    """Cancel any active pending confirmation."""
    brain = _get_brain(request)
    if not brain.confirmation.has_pending:
        return ConfirmationResponse(
            status="none",
            message="No confirmation was pending.",
            confirmed=False,
        )

    status, message = await brain.confirmation.reject()
    return ConfirmationResponse(
        status=status.value,
        message=message,
        confirmed=False,
    )


@router.post(
    "/aliases",
    response_model=IdentityResponse,
    summary="Add a wake word alias",
)
async def add_alias(request: Request, alias: str) -> IdentityResponse:
    """Add a new alias that activates the assistant."""
    brain = _get_brain(request)
    clean = alias.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Alias cannot be empty")

    added = brain.identity.add_alias(clean)
    if not added:
        raise HTTPException(status_code=409, detail=f"Alias '{clean}' already exists")

    if brain.voice_pipeline is not None:
        brain.voice_pipeline.wake_word_detector.update_wake_words(
            primary=brain.identity.wake_word,
            aliases=brain.identity.aliases,
        )

    return await get_identity(request)


@router.delete(
    "/aliases/{alias}",
    response_model=IdentityResponse,
    summary="Remove a wake word alias",
)
async def remove_alias(request: Request, alias: str) -> IdentityResponse:
    """Remove an existing alias."""
    brain = _get_brain(request)
    removed = brain.identity.remove_alias(alias)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Alias '{alias}' not found")

    if brain.voice_pipeline is not None:
        brain.voice_pipeline.wake_word_detector.update_wake_words(
            primary=brain.identity.wake_word,
            aliases=brain.identity.aliases,
        )

    return await get_identity(request)


# ---------------------------------------------------------------------------
# Wake Word Detection Test Endpoint
# ---------------------------------------------------------------------------

wake_router = APIRouter(prefix="/wake-word", tags=["wake-word"])


@wake_router.post(
    "/detect",
    response_model=WakeWordDetectResponse,
    summary="Test wake word detection on input text",
)
async def detect_wake_word(
    request: Request,
    body: WakeWordDetectRequest,
) -> WakeWordDetectResponse:
    """Analyze input text using the current wake word detector."""
    brain = _get_brain(request)
    from nexus.voice.wake_word import WakeWordDetector

    detector = WakeWordDetector(
        wake_words=brain.identity.all_wake_words,
        prefixes=brain.identity.config.wake_word_prefixes,
    )
    match = detector.detect(body.text)

    return WakeWordDetectResponse(
        matched=match.matched,
        wake_word=match.wake_word,
        prefix=match.prefix,
        command=match.command,
        raw_text=match.raw_text,
    )
