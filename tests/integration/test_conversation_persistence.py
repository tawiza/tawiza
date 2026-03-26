"""Integration tests for conversation persistence in PostgreSQL."""

import asyncio
from uuid import UUID, uuid4

import pytest

# Skip all tests - requires PostgreSQL with tawiza role
pytestmark = pytest.mark.skipif(True, reason="Requires PostgreSQL with tawiza role")

from src.infrastructure.persistence.database import close_db, get_session
from src.infrastructure.persistence.repositories import (
    AnalysisResultRepository,
    ConversationRepository,
    MessageRepository,
)
from src.infrastructure.persistence.repositories.user_repository import UserRepository


@pytest.fixture
async def test_user():
    """Create a test user for conversations."""
    async with get_session() as session:
        repo = UserRepository(session)
        # Try to get existing test user or create new
        user = await repo.get_by_email("test-conv@tawiza.dev")
        if not user:
            user = await repo.create(
                email="test-conv@tawiza.dev",
                password="TestPassword123!",
                name="Test User",
            )
        return user


@pytest.mark.asyncio
async def test_create_conversation():
    """Test creating a conversation in PostgreSQL."""
    async with get_session() as session:
        # Get or create test user
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email("test-conv@tawiza.dev")
        if not user:
            user = await user_repo.create(
                email="test-conv@tawiza.dev",
                password="TestPassword123!",
                name="Test User",
            )

        # Create conversation
        conv_repo = ConversationRepository(session)
        conversation = await conv_repo.create(
            user_id=user.id,
            title="Test Conversation",
            cognitive_level="analytical",
            department_code="75",
        )

        assert conversation.id is not None
        assert conversation.title == "Test Conversation"
        assert conversation.cognitive_level == "analytical"
        assert conversation.department_code == "75"

        print(f"✓ Created conversation: {conversation.id}")


@pytest.mark.asyncio
async def test_add_messages():
    """Test adding messages to a conversation."""
    async with get_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email("test-conv@tawiza.dev")

        conv_repo = ConversationRepository(session)
        msg_repo = MessageRepository(session)

        # Create conversation
        conversation = await conv_repo.create(
            user_id=user.id,
            title="Message Test",
            cognitive_level="strategic",
        )

        # Add user message
        msg1 = await msg_repo.create(
            conversation_id=conversation.id,
            role="user",
            content="Analyse les entreprises du département 75",
            extra_data={"source": "chat_input"},
        )

        # Add assistant message
        msg2 = await msg_repo.create(
            conversation_id=conversation.id,
            role="assistant",
            content="J'analyse les données SIRENE pour le département 75...",
            extra_data={"confidence": 0.85, "sources": ["SIRENE", "INSEE"]},
        )

        assert msg1.role == "user"
        assert msg2.role == "assistant"
        assert msg2.extra_data["confidence"] == 0.85

        # Verify message count
        count = await msg_repo.count_by_conversation(conversation.id)
        assert count == 2

        print(f"✓ Added {count} messages to conversation")


@pytest.mark.asyncio
async def test_list_conversations():
    """Test listing user conversations."""
    async with get_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email("test-conv@tawiza.dev")

        conv_repo = ConversationRepository(session)

        # List conversations
        conversations = await conv_repo.list_by_user(user.id, limit=10, offset=0)

        assert len(conversations) > 0
        print(f"✓ Found {len(conversations)} conversations")


@pytest.mark.asyncio
async def test_conversation_survives_new_session():
    """Test that conversations persist across sessions."""
    # Create conversation in first session
    conv_id = None
    async with get_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email("test-conv@tawiza.dev")

        conv_repo = ConversationRepository(session)
        msg_repo = MessageRepository(session)

        conversation = await conv_repo.create(
            user_id=user.id,
            title="Persistence Test",
            cognitive_level="prospective",
        )
        conv_id = conversation.id

        await msg_repo.create(
            conversation_id=conv_id,
            role="user",
            content="This should persist!",
        )

    # Retrieve in NEW session
    async with get_session() as session:
        conv_repo = ConversationRepository(session)
        msg_repo = MessageRepository(session)

        # Fetch conversation
        conv = await conv_repo.get_by_id(conv_id)
        assert conv is not None
        assert conv.title == "Persistence Test"

        # Fetch messages
        messages = await msg_repo.get_by_conversation(conv_id, limit=10)
        assert len(messages) == 1
        assert messages[0].content == "This should persist!"

        print(f"✓ Conversation {conv_id} persisted across sessions!")


@pytest.mark.asyncio
async def test_analysis_result_caching():
    """Test caching analysis results."""
    async with get_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email("test-conv@tawiza.dev")

        repo = AnalysisResultRepository(session)

        # Store analysis result
        result = await repo.create(
            query="Entreprises en croissance Paris",
            result={"summary": "42 entreprises identifiées", "growth_rate": 0.15},
            user_id=user.id,
            cognitive_level="analytical",
            department_codes=["75"],
            sources=[{"name": "SIRENE", "count": 42}],
            confidence=0.92,
            duration_ms=1500,
        )

        assert result.id is not None
        assert result.confidence == 0.92

        # Find similar query
        cached = await repo.find_similar(
            query="Entreprises en croissance Paris",
            cognitive_level="analytical",
        )

        assert cached is not None
        assert cached.id == result.id
        print("✓ Analysis result cached and retrieved")


async def run_all_tests():
    """Run all persistence tests."""
    print("\n=== Conversation Persistence Tests ===\n")

    try:
        await test_create_conversation()
        await test_add_messages()
        await test_list_conversations()
        await test_conversation_survives_new_session()
        await test_analysis_result_caching()
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
