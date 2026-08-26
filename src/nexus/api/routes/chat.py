"""
NEXUS API — Chat Endpoint.

Send messages to the AI Brain and receive responses, with optional
conversation continuity.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from nexus.api.schemas import ChatRequest, ChatResetResponse, ChatResponse, ToolCallInfo
from nexus.utils.logging import get_logger

log = get_logger("api.chat")

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message to NEXUS",
    description="Send a user message and receive an AI-generated response. "
    "Optionally provide a conversation_id to continue a previous conversation.",
)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Process a user message through the NEXUS AI Brain."""
    brain = request.app.state.brain

    if not brain.is_initialized:
        try:
            await brain.initialize()
        except Exception as e:
            log.error("Brain initialization failed: %s", e)
            raise HTTPException(
                status_code=503,
                detail=f"NEXUS AI Brain failed to initialize: {e}",
            ) from e

    # Check that we have at least one provider
    if not brain._router.has_providers:
        raise HTTPException(
            status_code=503,
            detail="No LLM providers available. Please configure at least one API key in your .env file.",
        )

    log.info("[BACKEND CHAT REQUEST] message='%.80s'", body.message)

    try:
        response_text = await brain.process(body.message)
    except Exception as e:
        log.error("Brain processing error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {e}",
        ) from e

    # Persist message and conversation into SQLite database
    conversation_id = body.conversation_id
    try:
        from sqlalchemy import select

        from nexus.database.engine import get_session
        from nexus.database.models import Session as DBSession
        from nexus.database.models import User
        from nexus.database.repositories.conversation import ConversationRepository

        async with get_session() as session:
            repo = ConversationRepository(session)
            conv = None
            if conversation_id:
                conv = await repo.get_conversation(conversation_id)

            if conv is None:
                user_res = await session.execute(select(User).limit(1))
                db_user = user_res.scalar_one_or_none()
                if db_user is None:
                    db_user = User(name="User")
                    session.add(db_user)
                    await session.flush()

                sess_res = await session.execute(select(DBSession).where(DBSession.user_id == db_user.id).limit(1))
                db_session = sess_res.scalar_one_or_none()
                if db_session is None:
                    db_session = DBSession(user_id=db_user.id)
                    session.add(db_session)
                    await session.flush()

                clean_summary = body.message.strip()[:42] + ("..." if len(body.message.strip()) > 42 else "")
                conv = await repo.create_conversation(session_id=db_session.id, summary=clean_summary)
                conversation_id = conv.id

            await repo.add_message(conversation_id=conv.id, role="user", content=body.message)
            await repo.add_message(conversation_id=conv.id, role="assistant", content=response_text)
            await session.commit()
    except Exception as db_err:
        log.warning("Database message persistence notice: %s", db_err)
        conversation_id = conversation_id or "default"

    # Determine model used (best-effort from the router)
    model_used = None
    try:
        tier = brain._classify_tier(body.message)
        _, model_name = brain._router._resolve_provider_and_model(tier)
        model_used = model_name
    except Exception:
        pass

    # Gather any tool calls executed during this message turn
    tool_calls: list[ToolCallInfo] = []
    if hasattr(brain, "_orchestrator") and hasattr(brain._orchestrator, "last_tool_calls"):
        raw_tools = brain._orchestrator.last_tool_calls or []
        for t in raw_tools:
            if isinstance(t, ToolCallInfo):
                tool_calls.append(t)
            elif isinstance(t, dict):
                tool_calls.append(
                    ToolCallInfo(
                        name=str(t.get("name", "unknown")),
                        arguments=t.get("arguments", {}) if isinstance(t.get("arguments"), dict) else {},
                        result=str(t.get("result")) if t.get("result") is not None else None,
                        success=bool(t.get("success", True)),
                    )
                )

    final_conv_id: str = conversation_id if conversation_id is not None else "default"

    return ChatResponse(
        response=response_text,
        conversation_id=final_conv_id,
        model_used=model_used,
        tool_calls=tool_calls,
    )


@router.post(
    "/chat/reset",
    response_model=ChatResetResponse,
    summary="Reset conversation",
    description="Clear the current conversation context and start fresh.",
)
async def reset_chat(request: Request) -> ChatResetResponse:
    """Reset the conversation context."""
    brain = request.app.state.brain

    if brain.is_initialized:
        brain.reset_conversation()

    log.info("Conversation reset via API")
    return ChatResetResponse(message="Conversation reset successfully.")
