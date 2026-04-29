"""Unit tests for collector.factors — territorial alpha factors calculator.

Focused on pure-logic methods that don't require PostgreSQL or filesystem:
- SourceDataAvailability dataclass
- TerritorialFactors dataclass
- _winsorize_factor (statistical clipping)
- _calculate_composite_scores_v2 (percentile ranking + weighted scoring)
"""

from datetime import datetime

import numpy as np
import pytest

from src.collector.factors import (
    PostgreSQLDataCollector,
    SourceDataAvailability,
    TerritorialFactors,
    TerritorialFactorsCalculatorV2,
)


class TestSourceDataAvailability:
    """Tests for the SourceDataAvailability dataclass and confidence_score."""

    def test_default_no_sources(self):
        availability = SourceDataAvailability()
        assert availability.confidence_score == 0.0

    def test_all_sources_available(self):
        availability = SourceDataAvailability(
            sirene_creations=True,
            bodacc_liquidations=True,
            france_travail_offers=True,
            dvf_transactions=True,
            sitadel_permits=True,
            insee_population=True,
        )
        assert availability.confidence_score == 1.0

    def test_partial_sources(self):
        availability = SourceDataAvailability(
            sirene_creations=True,
            bodacc_liquidations=True,
            france_travail_offers=True,
        )
        assert availability.confidence_score == pytest.approx(0.5)

    def test_single_source(self):
        availability = SourceDataAvailability(insee_population=True)
        assert availability.confidence_score == pytest.approx(1.0 / 6.0)


class TestTerritorialFactors:
    """Tests for the TerritorialFactors dataclass instantiation."""

    def test_minimal_construction(self):
        factors = TerritorialFactors(
            code_dept="75",
            nom="Paris",
            calculated_at=datetime(2026, 4, 29),
            factor_tension_emploi=0.5,
            factor_dynamisme_immo=1.0,
            factor_sante_entreprises=2.0,
            factor_construction=0.3,
            factor_declin_ratio=0.1,
            score_composite=80.0,
        )
        assert factors.code_dept == "75"
        assert factors.nom == "Paris"
        assert factors.score_composite == 80.0
        assert factors.rang_national is None
        assert factors.confidence_score == 0.0
        assert factors.population == 0

    def test_full_construction(self):
        availability = SourceDataAvailability(
            sirene_creations=True, bodacc_liquidations=True
        )
        factors = TerritorialFactors(
            code_dept="13",
            nom="Bouches-du-Rhone",
            calculated_at=datetime.now(),
            factor_tension_emploi=0.5,
            factor_dynamisme_immo=1.0,
            factor_sante_entreprises=2.0,
            factor_construction=0.3,
            factor_declin_ratio=0.1,
            score_composite=80.0,
            rang_national=5,
            data_availability=availability,
            confidence_score=0.33,
            population=2000000,
            nb_entreprises_actives=150000,
            offres_emploi=8000,
        )
        assert factors.rang_national == 5
        assert factors.data_availability is availability
        assert factors.population == 2000000


class TestPostgreSQLDataCollectorInit:
    """Tests for PostgreSQLDataCollector constructor (no DB connection)."""

    def test_default_conn_params(self, monkeypatch):
        # Clear potentially set env vars to test defaults
        monkeypatch.delenv("SIGNALS_DB_NAME", raising=False)
        monkeypatch.delenv("DATABASE_USER", raising=False)
        monkeypatch.delenv("DATABASE_PASSWORD", raising=False)

        collector = PostgreSQLDataCollector()
        assert collector.conn_params["host"] == "localhost"
        assert collector.conn_params["port"] == 5432
        assert collector.conn_params["database"] == "tawiza_signals"
        assert collector.conn_params["user"] == "tawiza"
        assert collector.conn_params["password"] == ""

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("SIGNALS_DB_NAME", "custom_db")
        monkeypatch.setenv("DATABASE_USER", "alice")
        monkeypatch.setenv("DATABASE_PASSWORD", "test_password_value")

        collector = PostgreSQLDataCollector()
        assert collector.conn_params["database"] == "custom_db"
        assert collector.conn_params["user"] == "alice"
        assert collector.conn_params["password"] == "test_password_value"


class TestWinsorizeFactor:
    """Tests for _winsorize_factor — statistical outlier clipping."""

    @pytest.fixture
    def calc(self):
        return TerritorialFactorsCalculatorV2()

    def test_empty_list(self, calc):
        assert calc._winsorize_factor([]) == []

    def test_single_value(self, calc):
        # Less than 2 valid values => returned unchanged
        assert calc._winsorize_factor([5.0]) == [5.0]

    def test_all_nan(self, calc):
        values = [float("nan"), float("nan")]
        result = calc._winsorize_factor(values)
        assert all(np.isnan(v) for v in result)

    def test_no_outliers(self, calc):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calc._winsorize_factor(values, percentile=0.05)
        # With 5 values and 5% percentile, bounds are very close to min/max
        # so values should be roughly unchanged
        assert len(result) == 5
        for original, winsorized in zip(values, result):
            assert winsorized == pytest.approx(original, abs=1.0)

    def test_clips_high_outlier(self, calc):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 1000.0]
        result = calc._winsorize_factor(values, percentile=0.20)
        # The 1000 should be clipped down
        assert result[-1] < 1000.0
        # But other values within range should be unchanged or close
        assert result[0] == pytest.approx(1.0, abs=2.0)

    def test_clips_low_outlier(self, calc):
        values = [-1000.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        result = calc._winsorize_factor(values, percentile=0.20)
        assert result[0] > -1000.0

    def test_preserves_nan_positions(self, calc):
        values = [1.0, float("nan"), 3.0, 4.0, 5.0]
        result = calc._winsorize_factor(values)
        assert np.isnan(result[1])
        assert not np.isnan(result[0])
        assert not np.isnan(result[2])

    def test_custom_percentile(self, calc):
        values = list(range(100))
        result_5 = calc._winsorize_factor([float(v) for v in values], percentile=0.05)
        result_25 = calc._winsorize_factor([float(v) for v in values], percentile=0.25)
        # Tighter percentile (25%) should clip more aggressively => smaller range
        range_5 = max(result_5) - min(result_5)
        range_25 = max(result_25) - min(result_25)
        assert range_25 < range_5


class TestCalculateCompositeScores:
    """Tests for _calculate_composite_scores_v2 — the heart of the scoring algorithm."""

    @pytest.fixture
    def calc(self):
        return TerritorialFactorsCalculatorV2()

    def _make_factors(
        self,
        code_dept: str,
        tension: float = 0.5,
        dynamisme: float = 1.0,
        sante: float = 2.0,
        construction: float = 0.3,
        declin: float = 0.1,
        confidence: float = 0.5,
    ) -> TerritorialFactors:
        return TerritorialFactors(
            code_dept=code_dept,
            nom=f"Dept {code_dept}",
            calculated_at=datetime(2026, 4, 29),
            factor_tension_emploi=tension,
            factor_dynamisme_immo=dynamisme,
            factor_sante_entreprises=sante,
            factor_construction=construction,
            factor_declin_ratio=declin,
            score_composite=0.0,
            confidence_score=confidence,
        )

    def test_empty_list(self, calc):
        assert calc._calculate_composite_scores_v2([]) == []

    def test_single_factor_gets_median_score(self, calc):
        factors = [self._make_factors("75")]
        result = calc._calculate_composite_scores_v2(factors)
        # With n=1, percentile is 50, plus confidence bonus
        assert result[0].score_composite >= 50.0
        assert result[0].rang_national == 1

    def test_ranks_by_composite_score(self, calc):
        # Healthy department: high creations, low liquidations
        healthy = self._make_factors("01", sante=10.0, declin=0.05)
        # Sick department: low creations, high liquidations
        sick = self._make_factors("99", sante=0.1, declin=5.0)

        result = calc._calculate_composite_scores_v2([sick, healthy])

        # Healthy should rank #1
        ranks_by_dept = {f.code_dept: f.rang_national for f in result}
        assert ranks_by_dept["01"] == 1
        assert ranks_by_dept["99"] == 2
        scores_by_dept = {f.code_dept: f.score_composite for f in result}
        assert scores_by_dept["01"] > scores_by_dept["99"]

    def test_handles_nan_factors(self, calc):
        factors = [
            self._make_factors("01", tension=float("nan"), sante=5.0),
            self._make_factors("02", sante=3.0),
            self._make_factors("03", sante=1.0),
        ]
        result = calc._calculate_composite_scores_v2(factors)
        # All should have a valid composite score (no NaN propagation)
        for f in result:
            assert not np.isnan(f.score_composite)
            assert 0 <= f.score_composite <= 100

    def test_confidence_bonus_caps_at_100(self, calc):
        # Even with maxed confidence, score must not exceed 100
        factors = [
            self._make_factors("01", sante=10.0, confidence=1.0),
            self._make_factors("02", sante=5.0, confidence=1.0),
        ]
        result = calc._calculate_composite_scores_v2(factors)
        for f in result:
            assert f.score_composite <= 100.0

    def test_negative_declin_weight_lowers_score(self, calc):
        # Two departments identical except for declin_ratio
        low_declin = self._make_factors("01", declin=0.0, sante=2.0)
        high_declin = self._make_factors("02", declin=10.0, sante=2.0)

        result = calc._calculate_composite_scores_v2([low_declin, high_declin])
        ranks = {f.code_dept: f.rang_national for f in result}
        # Lower declin should rank better
        assert ranks["01"] < ranks["02"]
