"""Tests for 3D Evaluator."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agents.tajine.core.types import (
    EvaluationDecision,
    EvaluationResult,
    RawData,
)
from src.infrastructure.agents.tajine.evaluator.evaluator import Evaluator


class TestEvaluator:
    """Test 3D evaluation."""

    @pytest.fixture
    def raw_data(self):
        """Sample raw data."""
        return RawData(
            source="sirene",
            content={"siren": "123456789", "denomination": "Test SARL"},
            url="https://api.insee.fr/sirene",
            fetched_at=datetime.now(),
            quality_hint=0.9,
        )

    @pytest.fixture
    def mock_kg_validator(self):
        """Mock KG validator."""
        validator = MagicMock()
        validator.check = AsyncMock(return_value=0.8)
        return validator

    @pytest.fixture
    def mock_alpha_tester(self):
        """Mock alpha tester."""
        tester = MagicMock()
        tester.test = AsyncMock(return_value=0.7)
        return tester

    @pytest.mark.asyncio
    async def test_evaluate_returns_3d_score(self, raw_data, mock_kg_validator, mock_alpha_tester):
        """Should return EvaluationResult with 3 dimensions."""
        evaluator = Evaluator(
            kg_validator=mock_kg_validator,
            alpha_tester=mock_alpha_tester,
        )

        result = await evaluator.evaluate(raw_data)

        assert isinstance(result, EvaluationResult)
        assert 0 <= result.reliability <= 1
        assert 0 <= result.coherence <= 1
        assert 0 <= result.alpha <= 1

    @pytest.mark.asyncio
    async def test_high_score_accepts(self, raw_data, mock_kg_validator, mock_alpha_tester):
        """High composite score should result in ACCEPT."""
        mock_kg_validator.check = AsyncMock(return_value=0.95)
        mock_alpha_tester.test = AsyncMock(return_value=0.95)

        evaluator = Evaluator(
            kg_validator=mock_kg_validator,
            alpha_tester=mock_alpha_tester,
        )

        result = await evaluator.evaluate(raw_data)

        assert result.decision == EvaluationDecision.ACCEPT

    @pytest.mark.asyncio
    async def test_low_score_rejects(self, mock_kg_validator, mock_alpha_tester):
        """Low composite score should result in REJECT."""
        low_quality_data = RawData(
            source="blog",
            content={"text": "random blog post"},
            url="https://random-blog.com",
            fetched_at=datetime.now(),
            quality_hint=0.2,
        )

        mock_kg_validator.check = AsyncMock(return_value=0.1)
        mock_alpha_tester.test = AsyncMock(return_value=0.1)

        evaluator = Evaluator(
            kg_validator=mock_kg_validator,
            alpha_tester=mock_alpha_tester,
        )

        result = await evaluator.evaluate(low_quality_data)

        assert result.decision == EvaluationDecision.REJECT

    @pytest.mark.asyncio
    async def test_medium_score_verifies(self, mock_kg_validator, mock_alpha_tester):
        """Medium composite score should result in VERIFY."""
        medium_data = RawData(
            source="rss_presse",
            content={"article": "News about company"},
            url="https://news.example.com",
            fetched_at=datetime.now(),
            quality_hint=0.6,
        )

        mock_kg_validator.check = AsyncMock(return_value=0.5)
        mock_alpha_tester.test = AsyncMock(return_value=0.5)

        evaluator = Evaluator(
            kg_validator=mock_kg_validator,
            alpha_tester=mock_alpha_tester,
        )

        result = await evaluator.evaluate(medium_data)

        assert result.decision == EvaluationDecision.VERIFY
