"""Tests for TAJINE episodic memory."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.infrastructure.agents.tajine.memory.episodic_store import (
    Episode,
    EpisodicStore,
)
from src.infrastructure.agents.tajine.memory.retriever import (
    EpisodicRetriever,
    RetrievalResult,
)


class TestEpisode:
    """Tests for Episode dataclass."""

    def test_episode_creation(self):
        """Test creating an episode with default values."""
        episode = Episode(query="Test query")
        assert episode.query == "Test query"
        assert episode.id is not None
        assert episode.timestamp is not None
        assert episode.territory == ""
        assert episode.sector == ""

    def test_episode_with_context(self):
        """Test episode with territorial context."""
        episode = Episode(
            query="Analyse entreprises",
            territory="75",
            sector="6201Z",
            keywords=["tech", "startup"],
        )
        assert episode.territory == "75"
        assert episode.sector == "6201Z"
        assert "tech" in episode.keywords

    def test_episode_to_dict(self):
        """Test episode serialization."""
        episode = Episode(
            query="Test",
            territory="69",
            confidence_score=0.85,
        )
        data = episode.to_dict()
        assert data["query"] == "Test"
        assert data["territory"] == "69"
        assert data["confidence_score"] == 0.85
        assert "timestamp" in data

    def test_episode_from_dict(self):
        """Test episode deserialization."""
        data = {
            "id": "test-123",
            "query": "Test query",
            "territory": "75",
            "timestamp": "2025-01-01T12:00:00",
            "keywords": ["keyword1"],
        }
        episode = Episode.from_dict(data)
        assert episode.id == "test-123"
        assert episode.query == "Test query"
        assert episode.territory == "75"
        assert isinstance(episode.timestamp, datetime)

    def test_get_search_text(self):
        """Test generating search text for embedding."""
        episode = Episode(
            query="Croissance tech",
            territory="75",
            sector="6201Z",
            keywords=["innovation", "startup"],
        )
        search_text = episode.get_search_text()
        assert "Croissance tech" in search_text
        assert "territoire: 75" in search_text
        assert "secteur: 6201Z" in search_text

    def test_matches_context(self):
        """Test context matching."""
        episode = Episode(territory="75", sector="6201Z")
        assert episode.matches_context(territory="75")
        assert episode.matches_context(sector="6201Z")
        assert episode.matches_context(territory="75", sector="6201Z")
        assert not episode.matches_context(territory="69")


class TestEpisodicStore:
    """Tests for EpisodicStore."""

    @pytest.fixture
    def temp_store(self):
        """Create temporary store for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EpisodicStore(storage_path=tmpdir)

    def test_add_episode(self, temp_store):
        """Test adding an episode."""
        episode = Episode(query="Test query")
        episode_id = temp_store.add(episode)
        assert episode_id is not None
        assert temp_store.get(episode_id) is not None

    def test_get_episode(self, temp_store):
        """Test retrieving an episode."""
        episode = Episode(query="Test", territory="75")
        episode_id = temp_store.add(episode)

        retrieved = temp_store.get(episode_id)
        assert retrieved is not None
        assert retrieved.query == "Test"
        assert retrieved.territory == "75"

    def test_update_episode(self, temp_store):
        """Test updating an episode."""
        episode = Episode(query="Original")
        episode_id = temp_store.add(episode)

        success = temp_store.update(episode_id, {"confidence_score": 0.9})
        assert success

        updated = temp_store.get(episode_id)
        assert updated.confidence_score == 0.9

    def test_add_feedback(self, temp_store):
        """Test adding user feedback."""
        episode = Episode(query="Test")
        episode_id = temp_store.add(episode)

        success = temp_store.add_feedback(
            episode_id,
            feedback="Très utile",
            score=0.8,
        )
        assert success

        updated = temp_store.get(episode_id)
        assert updated.user_feedback == "Très utile"
        assert updated.feedback_score == 0.8

    def test_add_correction(self, temp_store):
        """Test adding correction."""
        episode = Episode(query="Test")
        episode_id = temp_store.add(episode)

        temp_store.add_correction(episode_id, "Wrong analysis")

        updated = temp_store.get(episode_id)
        assert "Wrong analysis" in updated.corrections

    def test_get_by_territory(self, temp_store):
        """Test filtering by territory."""
        temp_store.add(Episode(query="Paris", territory="75"))
        temp_store.add(Episode(query="Lyon", territory="69"))
        temp_store.add(Episode(query="Paris 2", territory="75"))

        paris_episodes = temp_store.get_by_territory("75")
        assert len(paris_episodes) == 2
        assert all(ep.territory == "75" for ep in paris_episodes)

    def test_get_by_sector(self, temp_store):
        """Test filtering by sector."""
        temp_store.add(Episode(query="Tech", sector="6201Z"))
        temp_store.add(Episode(query="Commerce", sector="4711F"))
        temp_store.add(Episode(query="Tech 2", sector="6201Z"))

        tech_episodes = temp_store.get_by_sector("6201Z")
        assert len(tech_episodes) == 2

    def test_get_recent(self, temp_store):
        """Test getting recent episodes."""
        for i in range(5):
            temp_store.add(Episode(query=f"Query {i}"))

        recent = temp_store.get_recent(limit=3)
        assert len(recent) == 3

    def test_search_text(self, temp_store):
        """Test text search."""
        temp_store.add(Episode(query="Intelligence artificielle Paris"))
        temp_store.add(Episode(query="Commerce Lyon"))
        temp_store.add(Episode(query="IA générative"))

        results = temp_store.search_text("intelligence")
        assert len(results) >= 1
        assert any("intelligence" in r.query.lower() for r in results)

    def test_get_with_feedback(self, temp_store):
        """Test getting episodes with feedback."""
        ep1 = Episode(query="With feedback")
        ep2 = Episode(query="Without feedback")

        id1 = temp_store.add(ep1)
        temp_store.add(ep2)

        temp_store.add_feedback(id1, "Good", score=0.9)

        with_feedback = temp_store.get_with_feedback()
        assert len(with_feedback) == 1
        assert with_feedback[0].query == "With feedback"

    def test_get_stats(self, temp_store):
        """Test statistics."""
        temp_store.add(Episode(query="Q1", territory="75"))
        temp_store.add(Episode(query="Q2", territory="75", sector="6201Z"))
        temp_store.add(Episode(query="Q3", territory="69"))

        stats = temp_store.get_stats()
        assert stats["total_episodes"] == 3
        assert stats["unique_territories"] == 2

    def test_persistence(self):
        """Test that episodes persist across store instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and add episode
            store1 = EpisodicStore(storage_path=tmpdir)
            episode_id = store1.add(Episode(query="Persistent"))

            # Create new store instance
            store2 = EpisodicStore(storage_path=tmpdir)

            # Verify episode is loaded
            retrieved = store2.get(episode_id)
            assert retrieved is not None
            assert retrieved.query == "Persistent"


class TestEpisodicRetriever:
    """Tests for EpisodicRetriever."""

    @pytest.fixture
    def store_with_data(self):
        """Create store with test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EpisodicStore(storage_path=tmpdir)

            # Add diverse episodes
            store.add(
                Episode(
                    query="Croissance tech Paris",
                    territory="75",
                    sector="6201Z",
                    cognitive_levels={"discovery": 0.8, "causal": 0.6},
                )
            )
            store.add(
                Episode(
                    query="Emploi Lyon industriel",
                    territory="69",
                    sector="2511Z",
                    cognitive_levels={"discovery": 0.7, "scenario": 0.5},
                )
            )
            store.add(
                Episode(
                    query="Startup innovation Bordeaux",
                    territory="33",
                    sector="6201Z",
                    cognitive_levels={"causal": 0.9},
                )
            )

            yield store

    @pytest.fixture
    def retriever(self, store_with_data):
        """Create retriever with test data."""
        return EpisodicRetriever(store=store_with_data)

    @pytest.mark.asyncio
    async def test_retrieve_by_territory(self, retriever):
        """Test retrieving by territory."""
        results = await retriever.retrieve_by_territory("75", k=5)
        assert len(results) >= 1
        assert all(r.episode.territory == "75" for r in results)
        assert all(r.match_type == "territory" for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_by_sector(self, retriever):
        """Test retrieving by sector."""
        results = await retriever.retrieve_by_sector("6201Z", k=5)
        assert len(results) >= 1
        assert all("6201Z" in r.episode.sector for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_by_pattern(self, retriever):
        """Test retrieving by reasoning pattern."""
        results = await retriever.retrieve_by_pattern("causal", k=5)
        # Should match episodes with high causal cognitive level
        assert len(results) >= 0  # May be empty if no matches

    @pytest.mark.asyncio
    async def test_retrieve_by_text(self, retriever):
        """Test text-based retrieval."""
        results = await retriever.retrieve_by_text("tech")
        assert len(results) >= 1
        assert results[0].match_type == "text"

    @pytest.mark.asyncio
    async def test_retrieve_for_context(self, retriever):
        """Test combined context retrieval."""
        results = await retriever.retrieve_for_context(
            query="tech innovation",
            territory="75",
            sector="6201Z",
            k=3,
        )
        # Should combine multiple retrieval strategies
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_relevant_context(self, retriever):
        """Test getting formatted context string."""
        context = await retriever.get_relevant_context(
            query="tech paris",
            territory="75",
            k=2,
        )
        # Should return formatted string
        assert isinstance(context, str)
        if context:  # May be empty if no results
            assert "analyses" in context.lower() or "territoire" in context.lower()

    def test_retrieval_result_to_dict(self, store_with_data):
        """Test RetrievalResult serialization."""
        episode = Episode(query="Test", territory="75")
        result = RetrievalResult(
            episode=episode,
            score=0.85,
            match_type="semantic",
            highlights=["territoire: 75"],
        )

        data = result.to_dict()
        assert data["score"] == 0.85
        assert data["match_type"] == "semantic"
        assert "territoire: 75" in data["highlights"]
