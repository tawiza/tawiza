"""Conversations API endpoints.

Provides CRUD operations for chat conversations and messages.
Uses PostgreSQL for persistent storage.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.database import get_db_session
from src.infrastructure.persistence.repositories import (
    ConversationRepository,
    MessageRepository,
)
from src.infrastructure.security.auth import User as AuthUser
from src.infrastructure.security.auth import get_current_user

router = APIRouter(prefix="/conversations", tags=["Conversations"])


# --- Pydantic Models ---


class MessageCreate(BaseModel):
    """Create message request."""

    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message content")
    metadata: dict | None = Field(default=None, description="Additional metadata")


class Message(BaseModel):
    """Message model."""

    id: str
    role: str
    content: str
    created_at: str
    metadata: dict | None = None


class ConversationCreate(BaseModel):
    """Create conversation request."""

    title: str | None = Field(default=None, description="Conversation title")
    level: str = Field(default="analytical", description="Cognitive level")
    department_code: str | None = Field(
        default=None, description="Department code (e.g., '75')"
    )


class ConversationUpdate(BaseModel):
    """Update conversation request."""

    title: str | None = None
    level: str | None = None
    department_code: str | None = None


class ConversationSummary(BaseModel):
    """Conversation summary (for list)."""

    id: str
    title: str
    level: str
    message_count: int
    created_at: str
    updated_at: str
    preview: str | None = None
    department_code: str | None = None


class ConversationDetail(BaseModel):
    """Full conversation with messages."""

    id: str
    title: str
    level: str
    created_at: str
    updated_at: str
    messages: list[Message]
    department_code: str | None = None


class ConversationList(BaseModel):
    """Paginated conversation list."""

    conversations: list[ConversationSummary]
    total: int
    page: int
    per_page: int


class MessageList(BaseModel):
    """Paginated message list."""

    messages: list[Message]
    total: int
    page: int
    per_page: int


# --- Helper Functions ---


def generate_title_from_content(content: str) -> str:
    """Generate a title from the first message content."""
    if len(content) <= 50:
        return content
    title = content[:50]
    last_space = title.rfind(" ")
    if last_space > 20:
        title = title[:last_space]
    return title + "..."


# --- API Endpoints ---


@router.get("", response_model=ConversationList)
async def list_conversations(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    level: str | None = Query(default=None, description="Filter by cognitive level"),
    department_code: str | None = Query(
        default=None, description="Filter by department"
    ),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """List all conversations for current user."""
    repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    user_uuid = UUID(current_user.user_id)

    # Get total count
    total = await repo.count_by_user(user_uuid)

    # Get paginated conversations
    offset = (page - 1) * per_page
    conversations = await repo.list_by_user(
        user_id=user_uuid,
        limit=per_page,
        offset=offset,
        cognitive_level=level,
        department_code=department_code,
    )

    # Build summaries with message counts
    summaries = []
    for conv in conversations:
        msg_count = await msg_repo.count_by_conversation(conv.id)

        # Get preview from last message
        preview = None
        messages = await msg_repo.get_by_conversation(conv.id, limit=1)
        if messages:
            last_content = messages[-1].content
            preview = (
                last_content[:100] + "..." if len(last_content) > 100 else last_content
            )

        summaries.append(
            ConversationSummary(
                id=str(conv.id),
                title=conv.title or "Nouvelle conversation",
                level=conv.cognitive_level,
                message_count=msg_count,
                created_at=conv.created_at.isoformat(),
                updated_at=conv.updated_at.isoformat(),
                preview=preview,
                department_code=conv.department_code,
            )
        )

    return ConversationList(
        conversations=summaries,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new conversation."""
    repo = ConversationRepository(session)

    conversation = await repo.create(
        user_id=UUID(current_user.user_id),
        title=request.title,
        cognitive_level=request.level,
        department_code=request.department_code,
    )

    return ConversationDetail(
        id=str(conversation.id),
        title=conversation.title or "Nouvelle conversation",
        level=conversation.cognitive_level,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
        messages=[],
        department_code=conversation.department_code,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Get conversation with all messages."""
    repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format",
        )

    conversation = await repo.get_by_id(conv_uuid)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Check ownership
    if str(conversation.user_id) != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get messages
    db_messages = await msg_repo.get_by_conversation(conv_uuid, limit=1000)
    messages = [
        Message(
            id=str(msg.id),
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at.isoformat(),
            metadata=msg.extra_data if msg.extra_data else None,
        )
        for msg in db_messages
    ]

    return ConversationDetail(
        id=str(conversation.id),
        title=conversation.title or "Nouvelle conversation",
        level=conversation.cognitive_level,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
        messages=messages,
        department_code=conversation.department_code,
    )


@router.put("/{conversation_id}", response_model=ConversationDetail)
async def update_conversation(
    conversation_id: str,
    request: ConversationUpdate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Update conversation metadata."""
    repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format",
        )

    conversation = await repo.get_by_id(conv_uuid)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if str(conversation.user_id) != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Update fields
    updated = await repo.update(
        conversation_id=conv_uuid,
        title=request.title,
        cognitive_level=request.level,
        department_code=request.department_code,
    )

    # Get messages
    db_messages = await msg_repo.get_by_conversation(conv_uuid, limit=1000)
    messages = [
        Message(
            id=str(msg.id),
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at.isoformat(),
            metadata=msg.extra_data if msg.extra_data else None,
        )
        for msg in db_messages
    ]

    return ConversationDetail(
        id=str(updated.id),
        title=updated.title or "Nouvelle conversation",
        level=updated.cognitive_level,
        created_at=updated.created_at.isoformat(),
        updated_at=updated.updated_at.isoformat(),
        messages=messages,
        department_code=updated.department_code,
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a conversation."""
    repo = ConversationRepository(session)

    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format",
        )

    conversation = await repo.get_by_id(conv_uuid)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if str(conversation.user_id) != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    await repo.delete(conv_uuid)


@router.get("/{conversation_id}/messages", response_model=MessageList)
async def list_messages(
    conversation_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """List messages in a conversation with pagination."""
    repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format",
        )

    conversation = await repo.get_by_id(conv_uuid)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if str(conversation.user_id) != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get total count
    total = await msg_repo.count_by_conversation(conv_uuid)

    # Get paginated messages
    db_messages = await msg_repo.get_by_conversation(conv_uuid, limit=per_page)
    messages = [
        Message(
            id=str(msg.id),
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at.isoformat(),
            metadata=msg.extra_data if msg.extra_data else None,
        )
        for msg in db_messages
    ]

    return MessageList(
        messages=messages,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/{conversation_id}/messages", response_model=Message, status_code=status.HTTP_201_CREATED
)
async def add_message(
    conversation_id: str,
    request: MessageCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Add a message to a conversation."""
    repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format",
        )

    conversation = await repo.get_by_id(conv_uuid)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if str(conversation.user_id) != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Create message
    message = await msg_repo.create(
        conversation_id=conv_uuid,
        role=request.role,
        content=request.content,
        extra_data=request.metadata,
    )

    # Auto-generate title from first user message
    msg_count = await msg_repo.count_by_conversation(conv_uuid)
    if msg_count == 1 and request.role == "user" and not conversation.title:
        await repo.update(
            conversation_id=conv_uuid,
            title=generate_title_from_content(request.content),
        )

    return Message(
        id=str(message.id),
        role=message.role,
        content=message.content,
        created_at=message.created_at.isoformat(),
        metadata=message.extra_data if message.extra_data else None,
    )


@router.get("/search/query", response_model=ConversationList)
async def search_conversations(
    q: str = Query(..., min_length=2, description="Search query"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Search conversations by title or message content.

    Uses PostgreSQL full-text search for efficient querying.
    Searches both conversation titles (ILIKE) and message content (tsvector).
    """
    repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    user_uuid = UUID(current_user.user_id)

    # Use PostgreSQL full-text search
    page_convs, total = await repo.search_full_text(
        user_id=user_uuid,
        query=q,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    # Build summaries
    summaries = []
    for conv in page_convs:
        msg_count = await msg_repo.count_by_conversation(conv.id)

        preview = None
        messages = await msg_repo.get_by_conversation(conv.id, limit=1)
        if messages:
            last_content = messages[-1].content
            preview = (
                last_content[:100] + "..." if len(last_content) > 100 else last_content
            )

        summaries.append(
            ConversationSummary(
                id=str(conv.id),
                title=conv.title or "Nouvelle conversation",
                level=conv.cognitive_level,
                message_count=msg_count,
                created_at=conv.created_at.isoformat(),
                updated_at=conv.updated_at.isoformat(),
                preview=preview,
                department_code=conv.department_code,
            )
        )

    return ConversationList(
        conversations=summaries,
        total=total,
        page=page,
        per_page=per_page,
    )
