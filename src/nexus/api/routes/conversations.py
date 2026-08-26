"""
NEXUS API — Conversation History Endpoints.

List, view, and delete stored conversations and their messages.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nexus.api.schemas import (
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    ConversationUpdateRequest,
    DeleteResponse,
    MessageSchema,
)
from nexus.database.engine import get_session
from nexus.database.repositories.conversation import ConversationRepository
from nexus.utils.logging import get_logger

log = get_logger("api.conversations")

router = APIRouter(tags=["conversations"])


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List conversations",
    description="Retrieve a paginated list of all conversations.",
)
async def list_conversations(
    page: int = 1,
    page_size: int = 20,
) -> ConversationListResponse:
    """List all conversations with pagination."""
    try:
        async with get_session() as session:
            repo = ConversationRepository(session)
            conversations, total = await repo.list_conversations(
                offset=(page - 1) * page_size,
                limit=page_size,
            )

            summaries = []
            for conv in conversations:
                msg_count = await repo.count_messages(conv.id)
                summaries.append(
                    ConversationSummary(
                        id=conv.id,
                        summary=conv.summary,
                        created_at=conv.created_at,
                        message_count=msg_count,
                    )
                )

            return ConversationListResponse(
                conversations=summaries,
                total=total,
                page=page,
                page_size=page_size,
            )
    except RuntimeError as e:
        if "not initialized" in str(e).lower():
            return ConversationListResponse(
                conversations=[],
                total=0,
                page=page,
                page_size=page_size,
            )
        raise


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    summary="Get conversation details",
    description="Retrieve a conversation and all its messages.",
)
async def get_conversation(conversation_id: str) -> ConversationDetail:
    """Get a conversation with its full message history."""
    try:
        async with get_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.get_conversation(conversation_id)

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation '{conversation_id}' not found.",
                )

            messages = [
                MessageSchema(
                    id=msg.id,
                    role=msg.role,
                    content=msg.content,
                    timestamp=msg.timestamp,
                )
                for msg in conversation.messages
            ]

            return ConversationDetail(
                id=conversation.id,
                summary=conversation.summary,
                created_at=conversation.created_at,
                messages=messages,
            )
    except HTTPException:
        raise
    except RuntimeError as e:
        if "not initialized" in str(e).lower():
            raise HTTPException(status_code=503, detail="Database not initialized.") from e
        raise


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationSummary,
    summary="Update conversation",
    description="Update a conversation summary/title.",
)
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdateRequest,
) -> ConversationSummary:
    """Update a conversation title."""
    try:
        async with get_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.get_conversation(conversation_id)

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation '{conversation_id}' not found.",
                )

            conversation.summary = body.summary.strip()
            await session.commit()
            msg_count = await repo.count_messages(conversation_id)

            log.info("Renamed conversation %s to '%s'", conversation_id, conversation.summary)
            return ConversationSummary(
                id=conversation.id,
                summary=conversation.summary,
                created_at=conversation.created_at,
                message_count=msg_count,
            )
    except HTTPException:
        raise
    except RuntimeError as e:
        if "not initialized" in str(e).lower():
            raise HTTPException(status_code=503, detail="Database not initialized.") from e
        raise


@router.delete(
    "/conversations/{conversation_id}",
    response_model=DeleteResponse,
    summary="Delete a conversation",
    description="Delete a conversation and all its messages.",
)
async def delete_conversation(conversation_id: str) -> DeleteResponse:
    """Delete a conversation by ID."""
    try:
        async with get_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.get_conversation(conversation_id)

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation '{conversation_id}' not found.",
                )

            await repo.delete_conversation(conversation_id)

            log.info("Deleted conversation %s", conversation_id)
            return DeleteResponse(
                message="Conversation deleted successfully.",
                deleted_id=conversation_id,
            )
    except HTTPException:
        raise
    except RuntimeError as e:
        if "not initialized" in str(e).lower():
            raise HTTPException(status_code=503, detail="Database not initialized.") from e
        raise
