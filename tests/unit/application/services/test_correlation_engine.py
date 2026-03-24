"""Tests for CorrelationEngine - dataclasses and basic logic."""

import numpy as np
import pytest

from src.application.services.correlation_engine import (
    CausalityStrength,
    CorrelationResult,
)
from src.infrastructure.persistence.models.territorial_timeseries import IndicatorType


class TestCausalityStrength:
    """Test CausalityStrength enum."""

    def test_values(self):
        assert CausalityStrength.NONE.value == "none"
        assert CausalityStrength.WEAK.value == "weak"
        assert CausalityStrength.MODERATE.value == "moderate"
        assert CausalityStrength.STRONG.value == "strong"
        assert CausalityStrength.VERY_STRONG.value == "very_strong"


class TestCorrelationResult:
    """Test CorrelationResult dataclass."""

    @pytest.fixture
    def significant_result(self):
        return CorrelationResult(
            source_indicator=IndicatorType.INSEE_CHOMAGE,
            target_indicator=IndicatorType.DVF_PRICE_M2_APT,
            correlation=0.75,
            lag_months=3,
            p_value=0.001,
            n_observations=48,
            confidence=0.95,
            territory_code="75",
        )

    @pytest.fixture
    def weak_result(self):
        return CorrelationResult(
            source_indicator=IndicatorType.INSEE_CHOMAGE,
            target_indicator=IndicatorType.INSEE_POPULATION,
            correlation=0.1,
            lag_months=0,
            p_value=0.5,
            n_observations=12,
            confidence=0.3,
        )

    def test_create(self, significant_result):
        assert significant_result.correlation == 0.75
        assert significant_result.lag_months == 3
        assert significant_result.territory_code == "75"

    def test_is_significant_true(self, significant_result):
        assert significant_result.is_significant is True

    def test_is_significant_false_high_pvalue(self, weak_result):
        assert weak_result.is_significant is False

    def test_is_significant_false_low_corr(self):
        result = CorrelationResult(
            source_indicator=IndicatorType.INSEE_CHOMAGE,
            target_indicator=IndicatorType.INSEE_POPULATION,
            correlation=0.1,  # too low
            lag_months=0,
            p_value=0.01,  # significant p-value
            n_observations=100,
            confidence=0.5,
        )
        assert result.is_significant is False

    def test_direction_positive(self, significant_result):
        assert significant_result.direction == "positive"

    def test_direction_negative(self):
        result = CorrelationResult(
            source_indicator=IndicatorType.INSEE_CHOMAGE,
            target_indicator=IndicatorType.SIRENE_CREATIONS,
            correlation=-0.6,
            lag_months=0,
            p_value=0.01,
            n_observations=48,
            confidence=0.8,
        )
        assert result.direction == "negative"

    def test_direction_neutral(self):
        result = CorrelationResult(
            source_indicator=IndicatorType.INSEE_CHOMAGE,
            target_indicator=IndicatorType.INSEE_POPULATION,
            correlation=0.05,
            lag_months=0,
            p_value=0.5,
            n_observations=12,
            confidence=0.2,
        )
        assert result.direction == "neutral"

    def test_territory_code_optional(self, weak_result):
        assert weak_result.territory_code is None
