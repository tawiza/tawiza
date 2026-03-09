"""Tests for TAJINE core types."""

from datetime import datetime

import pytest

from src.infrastructure.agents.tajine.core.types import (
    AnalysisContext,
    AnalysisResult,
    AutonomyDecision,
    EvaluationDecision,
    EvaluationResult,
    HuntContext,
    RawData,
    Recommendation,
    Scenario,
    ScoredData,
    TheoryMatch,
)


class TestHuntContext:
    """Test HuntContext dataclass."""

    def test_create_basic_context(self):
        """Should create HuntContext with required fields."""
        ctx = HuntContext(
            query="entreprises BTP Haute-Garonne",
            territory="31",
            mode="normal",
        )
        assert ctx.query == "entreprises BTP Haute-Garonne"
        assert ctx.territory == "31"
        assert ctx.mode == "normal"

    def test_default_mode(self):
        """Should default to 'normal' mode."""
        ctx = HuntContext(query="test", territory="75")
        assert ctx.mode == "normal"


class TestRawData:
    """Test RawData dataclass."""

    def test_create_raw_data(self):
        """Should create RawData with all fields."""
        data = RawData(
            source="sirene",
            content={"siren": "123456789"},
            url="https://api.insee.fr/sirene",
            fetched_at=datetime.now(),
            quality_hint=0.9,
        )
        assert data.source == "sirene"
        assert data.quality_hint == 0.9


class TestEvaluationResult:
    """Test EvaluationResult dataclass."""

    def test_create_evaluation(self):
        """Should create EvaluationResult with auto-computed fields."""
        result = EvaluationResult(
            reliability=0.9,
            coherence=0.8,
            alpha=0.7,
        )
        assert result.reliability == 0.9
        assert result.coherence == 0.8
        assert result.alpha == 0.7
        # Verify auto-computation works
        assert result.composite_score > 0
        assert result.decision == EvaluationDecision.ACCEPT

    def test_composite_score_formula(self):
        """Composite = reliability^0.4 * coherence^0.3 * alpha^0.3."""
        result = EvaluationResult(
            reliability=0.9,
            coherence=0.8,
            alpha=0.7,
        )
        expected = (0.9**0.4) * (0.8**0.3) * (0.7**0.3)
        assert abs(result.composite_score - expected) < 0.01

    def test_decision_accept_threshold(self):
        """Score >= 0.7 should ACCEPT."""
        # Score exactly 0.7
        result = EvaluationResult(
            reliability=0.7,
            coherence=0.7,
            alpha=0.7,
        )
        assert result.composite_score >= 0.7
        assert result.decision == EvaluationDecision.ACCEPT

    def test_decision_verify_threshold(self):
        """Score exactly 0.4 should VERIFY."""
        result = EvaluationResult(
            reliability=0.4,
            coherence=0.4,
            alpha=0.4,
        )
        assert 0.4 <= result.composite_score < 0.7
        assert result.decision == EvaluationDecision.VERIFY

    def test_decision_reject_threshold(self):
        """Score below 0.4 should REJECT."""
        result = EvaluationResult(
            reliability=0.3,
            coherence=0.3,
            alpha=0.3,
        )
        assert result.composite_score < 0.4
        assert result.decision == EvaluationDecision.REJECT


class TestAutonomyDecision:
    """Test AutonomyDecision enum."""

    def test_all_levels_exist(self):
        """Should have 4 autonomy levels."""
        assert AutonomyDecision.AUTONOMOUS.value == "autonomous"
        assert AutonomyDecision.PROPOSE.value == "propose"
        assert AutonomyDecision.ASK.value == "ask"
        assert AutonomyDecision.ESCALATE.value == "escalate"


class TestScenario:
    """Test Scenario dataclass."""

    def test_create_scenario(self):
        """Should create Scenario with probability."""
        scenario = Scenario(
            name="optimiste",
            value=1500000.0,
            probability=0.2,
            description="Croissance soutenue",
        )
        assert scenario.probability == 0.2


class TestScoredData:
    """Test ScoredData dataclass."""

    def test_create_scored_data(self):
        """Should combine RawData + EvaluationResult."""
        raw = RawData(
            source="sirene",
            content={"siren": "123456789"},
            url="https://api.insee.fr/sirene",
            fetched_at=datetime.now(),
            quality_hint=0.9,
        )
        evaluation = EvaluationResult(
            reliability=0.9,
            coherence=0.8,
            alpha=0.7,
        )
        scored = ScoredData(raw=raw, evaluation=evaluation)

        assert scored.raw == raw
        assert scored.evaluation == evaluation
        assert scored.validated_at is not None

    def test_scored_data_has_timestamp(self):
        """Should have validated_at timestamp."""
        raw = RawData(
            source="test",
            content={},
            url="https://test.com",
            fetched_at=datetime.now(),
        )
        evaluation = EvaluationResult(
            reliability=0.5,
            coherence=0.5,
            alpha=0.5,
        )
        scored = ScoredData(raw=raw, evaluation=evaluation)

        assert isinstance(scored.validated_at, datetime)


class TestRecommendation:
    """Test Recommendation dataclass."""

    def test_create_recommendation(self):
        """Should create Recommendation with priority calculation."""
        rec = Recommendation(
            title="Optimiser le référencement",
            description="Améliorer le SEO du site",
            impact=0.8,
            effort=0.4,
        )
        assert rec.title == "Optimiser le référencement"
        assert rec.impact == 0.8
        assert rec.effort == 0.4

    def test_priority_calculation(self):
        """Priority should equal impact/effort."""
        rec = Recommendation(
            title="Test",
            description="Test recommendation",
            impact=0.8,
            effort=0.4,
        )
        expected_priority = 0.8 / 0.4
        assert abs(rec.priority - expected_priority) < 0.01

    def test_priority_handles_zero_effort(self):
        """Should handle zero effort gracefully."""
        rec = Recommendation(
            title="Test",
            description="Test recommendation",
            impact=0.8,
            effort=0.0,
        )
        # Should use max(effort, 0.01) to avoid division by zero
        assert rec.priority == 0.8 / 0.01


class TestTheoryMatch:
    """Test TheoryMatch dataclass."""

    def test_create_theory_match(self):
        """Should create TheoryMatch with all fields."""
        match = TheoryMatch(
            theory_id="porter_5_forces",
            theory_name="Porter's Five Forces",
            similarity=0.85,
            explanation="Strong match due to competitive analysis context",
        )
        assert match.theory_id == "porter_5_forces"
        assert match.theory_name == "Porter's Five Forces"
        assert match.similarity == 0.85
        assert match.explanation == "Strong match due to competitive analysis context"

    def test_theory_match_default_insights(self):
        """Should have empty insights list by default."""
        match = TheoryMatch(
            theory_id="test",
            theory_name="Test Theory",
            similarity=0.5,
            explanation="Test",
        )
        assert match.applicable_insights == []

    def test_theory_match_with_insights(self):
        """Should store applicable insights."""
        insights = ["Insight 1", "Insight 2"]
        match = TheoryMatch(
            theory_id="test",
            theory_name="Test Theory",
            similarity=0.5,
            explanation="Test",
            applicable_insights=insights,
        )
        assert match.applicable_insights == insights


class TestAnalysisContext:
    """Test AnalysisContext dataclass."""

    def test_create_analysis_context(self):
        """Should create AnalysisContext with required fields."""
        raw = RawData(
            source="test",
            content={},
            url="https://test.com",
            fetched_at=datetime.now(),
        )
        evaluation = EvaluationResult(
            reliability=0.5,
            coherence=0.5,
            alpha=0.5,
        )
        scored = ScoredData(raw=raw, evaluation=evaluation)

        ctx = AnalysisContext(
            data=[scored],
            query="test query",
            territory="31",
        )
        assert ctx.data == [scored]
        assert ctx.query == "test query"
        assert ctx.territory == "31"

    def test_add_warning_method(self):
        """Should add warnings using add_warning() method."""
        ctx = AnalysisContext(
            data=[],
            query="test",
        )
        assert len(ctx.warnings) == 0

        ctx.add_warning("Warning 1")
        assert len(ctx.warnings) == 1
        assert ctx.warnings[0] == "Warning 1"

        ctx.add_warning("Warning 2")
        assert len(ctx.warnings) == 2
        assert ctx.warnings[1] == "Warning 2"

    def test_analysis_context_default_fields(self):
        """Should initialize empty lists for optional fields."""
        ctx = AnalysisContext(
            data=[],
            query="test",
        )
        assert ctx.signals == []
        assert ctx.causal_effects == []
        assert ctx.scenarios == []
        assert ctx.recommendations == []
        assert ctx.theory_matches == []
        assert ctx.warnings == []


class TestAnalysisResult:
    """Test AnalysisResult dataclass."""

    def test_create_analysis_result(self):
        """Should create AnalysisResult with all fields."""
        ctx = AnalysisContext(
            data=[],
            query="test query",
        )
        result = AnalysisResult(
            context=ctx,
            summary="Analysis complete",
            confidence=0.85,
            depth_reached=3,
            processing_time_ms=1500,
        )
        assert result.context == ctx
        assert result.summary == "Analysis complete"
        assert result.confidence == 0.85
        assert result.depth_reached == 3
        assert result.processing_time_ms == 1500


class TestEvaluationDecision:
    """Test EvaluationDecision enum."""

    def test_all_decision_values(self):
        """Should have all three decision values."""
        assert EvaluationDecision.ACCEPT.value == "accept"
        assert EvaluationDecision.VERIFY.value == "verify"
        assert EvaluationDecision.REJECT.value == "reject"

    def test_decision_enum_members(self):
        """Should have exactly 3 enum members."""
        members = list(EvaluationDecision)
        assert len(members) == 3
        assert EvaluationDecision.ACCEPT in members
        assert EvaluationDecision.VERIFY in members
        assert EvaluationDecision.REJECT in members
