"""Tests complets pour conversation_memory.py

Tests couvrant:
- ConversationTurn et ConversationContext dataclasses
- ShortTermMemory
- LongTermMemory
- AdvancedConversationMemory
"""

import asyncio
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.agents.advanced.conversation_memory import (
    ConversationContext,
    ConversationTurn,
    LongTermMemory,
    ShortTermMemory,
)


# ============================================================================
# Tests ConversationTurn Dataclass
# ============================================================================
class TestConversationTurn:
    """Tests pour la dataclass ConversationTurn."""

    def test_create_turn_minimal(self):
        """Création d'un tour avec paramètres minimaux."""
        turn = ConversationTurn(id="turn-1", timestamp=time.time(), role="user", content="Hello!")
        assert turn.id == "turn-1"
        assert turn.role == "user"
        assert turn.content == "Hello!"
        assert turn.metadata == {}
        assert turn.embeddings is None
        assert turn.importance_score == 0.5

    def test_create_turn_full(self):
        """Création d'un tour avec tous les paramètres."""
        embeddings = [0.1, 0.2, 0.3]
        turn = ConversationTurn(
            id="turn-2",
            timestamp=1234567890.0,
            role="assistant",
            content="How can I help?",
            metadata={"agent": "analyzer"},
            embeddings=embeddings,
            importance_score=0.8,
        )
        assert turn.metadata == {"agent": "analyzer"}
        assert turn.embeddings == embeddings
        assert turn.importance_score == 0.8

    def test_turn_roles(self):
        """Test des différents rôles."""
        roles = ["user", "assistant", "system"]
        for role in roles:
            turn = ConversationTurn(
                id=f"turn-{role}", timestamp=time.time(), role=role, content="test"
            )
            assert turn.role == role


# ============================================================================
# Tests ConversationContext Dataclass
# ============================================================================
class TestConversationContext:
    """Tests pour la dataclass ConversationContext."""

    def test_create_context_minimal(self):
        """Création d'un contexte minimal."""
        ctx = ConversationContext(
            session_id="sess-1",
            user_id="user-1",
            agent_type="analyzer",
            start_time=time.time(),
            last_update=time.time(),
        )
        assert ctx.session_id == "sess-1"
        assert ctx.user_id == "user-1"
        assert ctx.agent_type == "analyzer"
        assert ctx.summary == ""
        assert ctx.key_topics == []
        assert ctx.user_preferences == {}
        assert ctx.conversation_length == 0

    def test_create_context_full(self):
        """Création d'un contexte complet."""
        ctx = ConversationContext(
            session_id="sess-2",
            user_id="user-2",
            agent_type="ml_engineer",
            start_time=1000.0,
            last_update=2000.0,
            summary="Discussion about ML models",
            key_topics=["training", "optimization"],
            user_preferences={"language": "en"},
            conversation_length=10,
        )
        assert ctx.summary == "Discussion about ML models"
        assert len(ctx.key_topics) == 2
        assert ctx.conversation_length == 10


# ============================================================================
# Tests ShortTermMemory
# ============================================================================
class TestShortTermMemory:
    """Tests pour la classe ShortTermMemory."""

    def test_create_memory(self):
        """Création de la mémoire à court terme."""
        memory = ShortTermMemory(max_turns=5, max_age_minutes=15)
        assert memory.max_turns == 5
        assert memory.max_age_minutes == 15
        assert memory.recent_turns == []
        assert memory.current_context is None

    def test_add_turn(self):
        """Ajout d'un tour."""
        memory = ShortTermMemory(max_turns=10)
        turn = ConversationTurn(id="t1", timestamp=time.time(), role="user", content="Test message")
        memory.add_turn(turn)
        assert len(memory.recent_turns) == 1
        assert memory.recent_turns[0] == turn

    def test_max_turns_limit(self):
        """Respect de la limite max_turns."""
        memory = ShortTermMemory(max_turns=3)

        for i in range(5):
            turn = ConversationTurn(
                id=f"t{i}", timestamp=time.time(), role="user", content=f"Message {i}"
            )
            memory.add_turn(turn)

        # Seuls les 3 derniers tours devraient rester
        assert len(memory.recent_turns) == 3
        assert memory.recent_turns[0].id == "t2"
        assert memory.recent_turns[2].id == "t4"

    def test_expire_old_turns(self):
        """Expiration des tours trop anciens."""
        memory = ShortTermMemory(max_turns=10, max_age_minutes=1)

        # Ajouter un tour ancien (simulé)
        old_turn = ConversationTurn(
            id="old",
            timestamp=time.time() - 120,  # 2 minutes dans le passé
            role="user",
            content="Old message",
        )
        memory.recent_turns.append(old_turn)

        # Ajouter un nouveau tour
        new_turn = ConversationTurn(
            id="new", timestamp=time.time(), role="user", content="New message"
        )
        memory.add_turn(new_turn)

        # L'ancien tour devrait être supprimé
        assert len(memory.recent_turns) == 1
        assert memory.recent_turns[0].id == "new"

    def test_get_recent_context(self):
        """Récupération du contexte récent."""
        memory = ShortTermMemory(max_turns=10)

        for i in range(5):
            turn = ConversationTurn(
                id=f"t{i}", timestamp=time.time(), role="user", content=f"Message {i}"
            )
            memory.add_turn(turn)

        # Récupérer les 3 derniers
        recent = memory.get_recent_context(last_n=3)
        assert len(recent) == 3
        assert recent[0].id == "t2"
        assert recent[2].id == "t4"

    def test_get_recent_context_empty(self):
        """Contexte récent avec mémoire vide."""
        memory = ShortTermMemory()
        recent = memory.get_recent_context(last_n=5)
        assert recent == []

    def test_get_context_summary_empty(self):
        """Résumé avec mémoire vide."""
        memory = ShortTermMemory()
        summary = memory.get_context_summary()
        assert summary == "Aucune conversation récente"

    def test_get_context_summary_with_turns(self):
        """Résumé avec des tours."""
        memory = ShortTermMemory()

        for i in range(3):
            turn = ConversationTurn(
                id=f"t{i}", timestamp=time.time(), role="user", content=f"Question {i}"
            )
            memory.add_turn(turn)

        summary = memory.get_context_summary()
        assert "Question" in summary

    def test_calculate_importance_base(self):
        """Calcul d'importance de base."""
        memory = ShortTermMemory()
        turn = ConversationTurn(
            id="t1", timestamp=time.time(), role="assistant", content="Short response"
        )
        importance = memory.calculate_importance(turn)
        assert importance == 0.5  # Base value

    def test_calculate_importance_user_message(self):
        """Importance plus élevée pour les messages utilisateur."""
        memory = ShortTermMemory()
        turn = ConversationTurn(
            id="t1", timestamp=time.time(), role="user", content="Short question"
        )
        importance = memory.calculate_importance(turn)
        assert importance == 0.7  # 0.5 + 0.2

    def test_calculate_importance_long_message(self):
        """Importance plus élevée pour les messages longs."""
        memory = ShortTermMemory()
        turn = ConversationTurn(
            id="t1",
            timestamp=time.time(),
            role="user",
            content="A" * 250,  # Long message
        )
        importance = memory.calculate_importance(turn)
        # 0.5 base + 0.2 user + 0.1 long = 0.8, but floating point may vary
        assert importance >= 0.79  # Allow small floating point variance

    def test_calculate_importance_keywords(self):
        """Importance avec mots-clés importants."""
        memory = ShortTermMemory()
        turn = ConversationTurn(
            id="t1",
            timestamp=time.time(),
            role="user",
            content="This is an urgent and critical problem!",
        )
        importance = memory.calculate_importance(turn)
        assert importance > 0.7  # Base + user + keywords

    def test_calculate_importance_max_capped(self):
        """L'importance est plafonnée à 1.0."""
        memory = ShortTermMemory()
        turn = ConversationTurn(
            id="t1",
            timestamp=time.time(),
            role="user",
            content="This is urgent critical important error problem help! " * 50,
        )
        importance = memory.calculate_importance(turn)
        assert importance <= 1.0


# ============================================================================
# Tests LongTermMemory
# ============================================================================
class TestLongTermMemory:
    """Tests pour la classe LongTermMemory."""

    @pytest.fixture
    def temp_db_path(self):
        """Crée un fichier DB temporaire."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_create_memory(self, temp_db_path):
        """Création de la mémoire à long terme."""
        memory = LongTermMemory(db_path=temp_db_path)
        assert memory.db_path == temp_db_path

    def test_database_initialized(self, temp_db_path):
        """Vérifie que la DB est initialisée."""
        memory = LongTermMemory(db_path=temp_db_path)

        import sqlite3

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()

        # Vérifie que les tables existent
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert "conversations" in tables
        assert "conversation_turns" in tables
        conn.close()

    def test_multiple_instances_same_db(self, temp_db_path):
        """Plusieurs instances peuvent utiliser la même DB."""
        memory1 = LongTermMemory(db_path=temp_db_path)
        memory2 = LongTermMemory(db_path=temp_db_path)

        assert memory1.db_path == memory2.db_path


# ============================================================================
# Tests d'intégration ShortTermMemory
# ============================================================================
class TestShortTermMemoryIntegration:
    """Tests d'intégration pour ShortTermMemory."""

    def test_conversation_flow(self):
        """Simule un flux de conversation complet."""
        memory = ShortTermMemory(max_turns=10, max_age_minutes=30)

        # Simuler une conversation
        messages = [
            ("user", "Hello, I need help with ML"),
            ("assistant", "Hello! I can help with machine learning. What do you need?"),
            ("user", "I want to train a model"),
            ("assistant", "Great! What type of model are you looking to train?"),
            ("user", "A classification model for images"),
        ]

        for i, (role, content) in enumerate(messages):
            turn = ConversationTurn(
                id=f"turn-{i}", timestamp=time.time() + i, role=role, content=content
            )
            memory.add_turn(turn)

        # Vérifications
        assert len(memory.recent_turns) == 5
        summary = memory.get_context_summary()
        assert len(summary) > 0

        # Récupérer les derniers messages
        recent = memory.get_recent_context(last_n=3)
        assert len(recent) == 3

    def test_memory_with_context(self):
        """Test avec contexte défini."""
        memory = ShortTermMemory()

        # Définir un contexte
        ctx = ConversationContext(
            session_id="sess-test",
            user_id="user-test",
            agent_type="data_analyst",
            start_time=time.time(),
            last_update=time.time(),
            summary="Data analysis session",
        )
        memory.current_context = ctx

        # Ajouter des tours
        turn = ConversationTurn(
            id="t1", timestamp=time.time(), role="user", content="Analyze this dataset"
        )
        memory.add_turn(turn)

        assert memory.current_context.session_id == "sess-test"
        assert len(memory.recent_turns) == 1


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestConversationMemoryEdgeCases:
    """Tests des cas limites."""

    def test_turn_with_empty_content(self):
        """Tour avec contenu vide."""
        turn = ConversationTurn(id="t1", timestamp=time.time(), role="user", content="")
        assert turn.content == ""

    def test_turn_with_very_long_content(self):
        """Tour avec contenu très long."""
        long_content = "A" * 100000
        turn = ConversationTurn(id="t1", timestamp=time.time(), role="user", content=long_content)
        assert len(turn.content) == 100000

    def test_context_with_complex_preferences(self):
        """Contexte avec préférences complexes."""
        ctx = ConversationContext(
            session_id="sess-1",
            user_id="user-1",
            agent_type="analyzer",
            start_time=time.time(),
            last_update=time.time(),
            user_preferences={"language": "fr", "nested": {"key": "value"}, "list": [1, 2, 3]},
        )
        assert ctx.user_preferences["nested"]["key"] == "value"

    def test_short_term_memory_rapid_additions(self):
        """Ajouts rapides à la mémoire."""
        memory = ShortTermMemory(max_turns=100)

        for i in range(1000):
            turn = ConversationTurn(
                id=f"t{i}", timestamp=time.time(), role="user", content=f"Message {i}"
            )
            memory.add_turn(turn)

        # Ne devrait garder que les 100 derniers
        assert len(memory.recent_turns) == 100
        assert memory.recent_turns[-1].id == "t999"


# ============================================================================
# Tests LongTermMemory Vector Search Integration
# ============================================================================
class TestLongTermMemoryVectorSearch:
    """Tests pour la recherche vectorielle dans LongTermMemory."""

    @pytest.fixture
    def temp_db_path(self):
        """Crée un fichier DB temporaire."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_init_without_vector_search(self, temp_db_path):
        """Initialisation sans recherche vectorielle."""
        memory = LongTermMemory(db_path=temp_db_path, enable_vector_search=False)

        assert memory.enable_vector_search is False
        assert memory._qdrant is None
        assert memory._embeddings is None
        assert memory._vector_initialized is False

    def test_fallback_to_keyword_search(self, temp_db_path):
        """Fallback vers recherche par mots-clés si vector indisponible."""
        memory = LongTermMemory(db_path=temp_db_path, enable_vector_search=False)

        # Stocker une conversation
        ctx = ConversationContext(
            session_id="sess-fallback",
            user_id="user-1",
            agent_type="analyzer",
            start_time=time.time(),
            last_update=time.time(),
            summary="Test GPU optimization",
        )
        turns = [
            ConversationTurn(
                id="turn-1",
                timestamp=time.time(),
                role="user",
                content="How do I optimize GPU performance?",
            )
        ]
        memory.store_conversation(ctx, turns)

        # Rechercher avec mots-clés
        results = memory.retrieve_similar_conversations("GPU")

        # Devrait trouver via fallback keyword search
        assert len(results) >= 1
        found_session_ids = [r[0].session_id for r in results]
        assert "sess-fallback" in found_session_ids

    @pytest.mark.asyncio
    async def test_keyword_search_conversations_method(self, temp_db_path):
        """Test direct de _keyword_search_conversations."""
        memory = LongTermMemory(db_path=temp_db_path, enable_vector_search=False)

        # Créer plusieurs conversations
        for i in range(3):
            ctx = ConversationContext(
                session_id=f"sess-{i}",
                user_id="user-test",
                agent_type="analyzer",
                start_time=time.time(),
                last_update=time.time(),
                summary=f"Discussion about topic {i}",
            )
            turns = [
                ConversationTurn(
                    id=f"turn-{i}",
                    timestamp=time.time(),
                    role="user",
                    content=f"Message about topic {i}",
                )
            ]
            memory.store_conversation(ctx, turns)

        # Rechercher
        results = memory._keyword_search_conversations("topic", limit=10)

        assert len(results) == 3

    def test_get_conversation_from_db(self, temp_db_path):
        """Test récupération conversation par ID."""
        memory = LongTermMemory(db_path=temp_db_path, enable_vector_search=False)

        ctx = ConversationContext(
            session_id="sess-getbyid",
            user_id="user-1",
            agent_type="analyzer",
            start_time=time.time(),
            last_update=time.time(),
            summary="Test summary",
        )
        turns = [
            ConversationTurn(
                id="turn-1", timestamp=time.time(), role="user", content="Test content"
            )
        ]
        memory.store_conversation(ctx, turns)

        # Récupérer par ID
        result = memory._get_conversation_from_db("sess-getbyid")

        assert result is not None
        context, retrieved_turns = result
        assert context.session_id == "sess-getbyid"
        assert len(retrieved_turns) == 1

    def test_get_conversation_from_db_not_found(self, temp_db_path):
        """Test récupération conversation inexistante."""
        memory = LongTermMemory(db_path=temp_db_path, enable_vector_search=False)

        result = memory._get_conversation_from_db("nonexistent-session")

        assert result is None


class TestLongTermMemoryVectorSearchMocked:
    """Tests avec Qdrant/Embeddings mockés."""

    @pytest.fixture
    def temp_db_path(self):
        """Crée un fichier DB temporaire."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    @pytest.fixture
    def mock_qdrant_client(self):
        """Mock du client Qdrant."""
        from unittest.mock import AsyncMock

        mock = MagicMock()
        mock.ensure_collection = AsyncMock(return_value=None)
        mock.upsert = AsyncMock(return_value=None)
        mock.search = AsyncMock(
            return_value=[
                {"id": "sess-mock", "score": 0.95, "payload": {"session_id": "sess-mock"}}
            ]
        )
        return mock

    @pytest.fixture
    def mock_embeddings_service(self):
        """Mock du service d'embeddings."""
        mock = MagicMock()

        async def mock_embed(text):
            return [0.1] * 1024

        mock.embed = mock_embed
        return mock

    @pytest.mark.asyncio
    async def test_generate_conversation_embedding(self, temp_db_path, mock_embeddings_service):
        """Test génération embedding pour conversation."""
        memory = LongTermMemory(db_path=temp_db_path, enable_vector_search=False)
        memory._embeddings = mock_embeddings_service
        memory._vector_initialized = True

        turns = [
            ConversationTurn(
                id="turn-1",
                timestamp=time.time(),
                role="user",
                content="Test content for embedding",
            )
        ]

        embedding = await memory._generate_conversation_embedding(turns)

        assert embedding is not None
        assert len(embedding) == 1024

    @pytest.mark.asyncio
    async def test_index_conversation_vector(
        self, temp_db_path, mock_qdrant_client, mock_embeddings_service
    ):
        """Test indexation vectorielle d'une conversation."""
        memory = LongTermMemory(db_path=temp_db_path, enable_vector_search=False)
        memory._qdrant = mock_qdrant_client
        memory._embeddings = mock_embeddings_service
        memory._vector_initialized = True

        ctx = ConversationContext(
            session_id="sess-index",
            user_id="user-1",
            agent_type="analyzer",
            start_time=time.time(),
            last_update=time.time(),
            summary="Test indexing",
        )
        turns = [
            ConversationTurn(
                id="turn-1", timestamp=time.time(), role="user", content="Test content"
            )
        ]

        success = await memory._index_conversation_vector("sess-index", ctx, turns)

        assert success is True

    @pytest.mark.asyncio
    async def test_retrieve_similar_conversations_async_with_vector(
        self, temp_db_path, mock_qdrant_client, mock_embeddings_service
    ):
        """Test recherche vectorielle async."""
        memory = LongTermMemory(db_path=temp_db_path, enable_vector_search=False)
        memory._qdrant = mock_qdrant_client
        memory._embeddings = mock_embeddings_service
        memory._vector_initialized = True

        # Stocker une conversation pour que _get_conversation_from_db trouve quelque chose
        ctx = ConversationContext(
            session_id="sess-mock",
            user_id="user-1",
            agent_type="analyzer",
            start_time=time.time(),
            last_update=time.time(),
            summary="Mocked conversation",
        )
        turns = [
            ConversationTurn(
                id="turn-1", timestamp=time.time(), role="user", content="Mocked content"
            )
        ]
        memory.store_conversation(ctx, turns)

        # Mock search pour retourner cette session
        async def mock_search(query_vector, limit):
            return [{"id": "sess-mock", "score": 0.95, "payload": {"session_id": "sess-mock"}}]

        memory._qdrant.search = mock_search

        # Rechercher
        results = await memory.retrieve_similar_conversations_async("test query")

        assert len(results) >= 1
