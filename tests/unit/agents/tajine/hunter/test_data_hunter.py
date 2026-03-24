"""Tests for DataHunter orchestrator.

DataHunter v2 uses LinUCB (contextual bandit) as primary source selector
with UCB1 as fallback. Tests cover both paths.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.tajine.core.types import HuntContext, RawData
from src.infrastructure.agents.tajine.hunter.data_hunter import DataHunter, HuntResult


class TestDataHunter:
    """Test DataHunter orchestration."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components."""
        bandit = MagicMock()
        bandit.select.return_value = ["sirene", "bodacc"]

        hypothesis_gen = MagicMock()
        hypothesis_gen.generate.return_value = []

        graph_expander = MagicMock()
        graph_expander.find_gaps = AsyncMock(return_value=[])

        crawler = MagicMock()
        crawler.fetch = AsyncMock(
            return_value={
                "content": {"test": "data"},
                "url": "https://test.com",
            }
        )

        return bandit, hypothesis_gen, graph_expander, crawler

    @pytest.mark.asyncio
    @patch("src.infrastructure.agents.tajine.hunter.data_hunter.LINUCB_AVAILABLE", False)
    async def test_hunt_normal_mode(self, mock_components):
        """Should orchestrate normal mode hunt with UCB1 fallback."""
        bandit, hypothesis_gen, graph_expander, crawler = mock_components

        # Disable LinUCB to test UCB1 fallback
        hunter = DataHunter(
            bandit=bandit,
            hypothesis_generator=hypothesis_gen,
            graph_expander=graph_expander,
            crawler=crawler,
            linucb_scheduler=None,  # Force UCB1 fallback
        )

        context = HuntContext(
            query="entreprises BTP Toulouse",
            territory="31",
            mode="normal",
        )

        results = await hunter.hunt(context)

        assert isinstance(results, HuntResult)
        assert isinstance(results.data, list)
        # With LinUCB disabled, UCB1 bandit.select should be called
        bandit.select.assert_called()

    @pytest.mark.asyncio
    @patch("src.infrastructure.agents.tajine.hunter.data_hunter.LINUCB_AVAILABLE", False)
    async def test_hunt_updates_bandit(self, mock_components):
        """Should update UCB1 bandit with rewards after hunt (fallback path)."""
        bandit, hypothesis_gen, graph_expander, crawler = mock_components

        # Disable LinUCB to test UCB1 fallback
        hunter = DataHunter(
            bandit=bandit,
            hypothesis_generator=hypothesis_gen,
            graph_expander=graph_expander,
            crawler=crawler,
            linucb_scheduler=None,
        )

        context = HuntContext(query="test", territory="31")
        await hunter.hunt(context)

        # UCB1 bandit should be updated in fallback mode
        assert bandit.update.called or len(bandit.select.return_value) == 0

    @pytest.mark.asyncio
    async def test_hunt_with_linucb(self, mock_components):
        """Should use LinUCB when available (v2 primary path)."""
        bandit, hypothesis_gen, graph_expander, crawler = mock_components

        # Create mock LinUCB scheduler
        mock_linucb = MagicMock()
        mock_arm = MagicMock()
        mock_arm.source_id = "sirene"
        mock_linucb.select_batch.return_value = [mock_arm]

        hunter = DataHunter(
            bandit=bandit,
            hypothesis_generator=hypothesis_gen,
            graph_expander=graph_expander,
            crawler=crawler,
            linucb_scheduler=mock_linucb,
        )

        context = HuntContext(
            query="entreprises BTP Toulouse",
            territory="31",
            mode="normal",
        )

        results = await hunter.hunt(context)

        assert isinstance(results, HuntResult)
        # LinUCB should be used instead of UCB1
        mock_linucb.select_batch.assert_called()
        # UCB1 should NOT be called when LinUCB is available
        bandit.select.assert_not_called()

    @pytest.mark.asyncio
    async def test_hunt_question_mode_uses_hypotheses(self, mock_components):
        """Question mode should use hypothesis generator."""
        bandit, hypothesis_gen, graph_expander, crawler = mock_components

        from src.infrastructure.agents.tajine.hunter.hypothesis import Hypothesis

        hypothesis_gen.generate.return_value = [
            Hypothesis(statement="Test hypothesis", confidence=0.8)
        ]

        hunter = DataHunter(
            bandit=bandit,
            hypothesis_generator=hypothesis_gen,
            graph_expander=graph_expander,
            crawler=crawler,
        )

        context = HuntContext(
            query="Pourquoi les entreprises BTP croissent?",
            territory="31",
            mode="question",
        )

        await hunter.hunt(context)

        hypothesis_gen.generate.assert_called()

    @pytest.mark.asyncio
    async def test_hunt_combler_mode_uses_graph(self, mock_components):
        """Combler mode should prioritize graph gaps."""
        bandit, hypothesis_gen, graph_expander, crawler = mock_components

        from src.infrastructure.agents.tajine.hunter.graph_expander import GapType, KnowledgeGap

        graph_expander.find_gaps = AsyncMock(
            return_value=[
                KnowledgeGap(
                    gap_type=GapType.STALE_DATA,
                    entity_id="SIREN:123",
                    description="Stale",
                )
            ]
        )

        hunter = DataHunter(
            bandit=bandit,
            hypothesis_generator=hypothesis_gen,
            graph_expander=graph_expander,
            crawler=crawler,
        )

        context = HuntContext(
            query="",
            territory="31",
            mode="combler",
        )

        await hunter.hunt(context)

        graph_expander.find_gaps.assert_called()
