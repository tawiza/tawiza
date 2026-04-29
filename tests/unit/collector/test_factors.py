"""Unit tests for collector.factors — territorial alpha factors calculator.

Two test layers:
1. Pure logic (no I/O): dataclasses, _winsorize_factor, _calculate_composite_scores_v2
2. Mocked I/O: PopulationManager (CSV + dict fallback),
   _get_department_names (sqlite3), _calculate_dept_factors_v2,
   _calculate_dept_factors_legacy, _calculate_from_sqlite, calculate_factors
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.collector.factors import (
    PopulationManager,
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


class TestPopulationManager:
    """Tests for PopulationManager.get_population — population lookup with fallbacks."""

    @pytest.fixture
    def manager(self):
        return PopulationManager(db_path="data/test.db")

    @pytest.mark.asyncio
    async def test_cache_hit(self, manager):
        manager._population_cache["75"] = 2161000
        # Even if read_csv would fail, cache should short-circuit
        with patch("src.collector.factors.pd.read_csv", side_effect=Exception("disk fail")):
            result = await manager.get_population("75")
        assert result == 2161000

    @pytest.mark.asyncio
    async def test_csv_lookup(self, manager):
        df = pd.DataFrame({"code_dept": ["75", "13"], "population": [2161000, 2043000]})
        with patch("src.collector.factors.pd.read_csv", return_value=df):
            result = await manager.get_population("13")
        assert result == 2043000
        # Cached for next call
        assert manager._population_cache["13"] == 2043000

    @pytest.mark.asyncio
    async def test_csv_missing_dept_falls_through_to_dict(self, manager):
        df = pd.DataFrame({"code_dept": ["01"], "population": [600000]})
        with patch("src.collector.factors.pd.read_csv", return_value=df):
            result = await manager.get_population("75")
        # 75 not in CSV → falls through to dict fallback
        assert result == 2161000

    @pytest.mark.asyncio
    async def test_dict_fallback_paris(self, manager):
        with patch("src.collector.factors.pd.read_csv", side_effect=FileNotFoundError):
            result = await manager.get_population("75")
        assert result == 2161000
        assert manager._population_cache["75"] == 2161000

    @pytest.mark.asyncio
    async def test_dict_fallback_other_dept(self, manager):
        with patch("src.collector.factors.pd.read_csv", side_effect=FileNotFoundError):
            result = await manager.get_population("69")
        assert result == 1844000

    @pytest.mark.asyncio
    async def test_default_estimation_for_unknown_dept(self, manager):
        with patch("src.collector.factors.pd.read_csv", side_effect=FileNotFoundError):
            result = await manager.get_population("01")
        # Default: 600000 for departments not in any source
        assert result == 600000


class TestGetDepartmentNames:
    """Tests for TerritorialFactorsCalculatorV2._get_department_names."""

    @pytest.fixture
    def calc(self):
        return TerritorialFactorsCalculatorV2()

    @pytest.mark.asyncio
    async def test_returns_dict_from_sqlite(self, calc):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("75", "Paris"), ("13", "Bouches-du-Rhone")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.collector.factors.sqlite3.connect", return_value=mock_conn):
            result = await calc._get_department_names()

        assert result == {"75": "Paris", "13": "Bouches-du-Rhone"}
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_exception(self, calc):
        with patch(
            "src.collector.factors.sqlite3.connect", side_effect=Exception("db error")
        ):
            result = await calc._get_department_names()
        assert result == {}


class TestCalculateDeptFactorsV2:
    """Tests for TerritorialFactorsCalculatorV2._calculate_dept_factors_v2."""

    @pytest.fixture
    def calc(self):
        c = TerritorialFactorsCalculatorV2()
        # Stub out population manager to avoid CSV / dict lookups
        c.pop_manager.get_population = AsyncMock(return_value=2161000)
        return c

    def _make_pg_data(self, **overrides):
        base = {
            "creations_sirene": 1000,
            "liquidations_bodacc": 100,
            "offres_france_travail": 5000,
            "transactions_dvf": 800,
            "prix_m2_dvf": 7000.0,
            "logements_sitadel": 200,
            "data_availability": SourceDataAvailability(
                sirene_creations=True,
                bodacc_liquidations=True,
                france_travail_offers=True,
                dvf_transactions=True,
                sitadel_permits=True,
            ),
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_full_data_returns_valid_factors(self, calc):
        result = await calc._calculate_dept_factors_v2("75", self._make_pg_data(), "Paris")
        assert result is not None
        assert result.code_dept == "75"
        assert result.nom == "Paris"
        # All 5 factors should be non-NaN with full data
        assert not np.isnan(result.factor_tension_emploi)
        assert not np.isnan(result.factor_dynamisme_immo)
        assert not np.isnan(result.factor_sante_entreprises)
        assert not np.isnan(result.factor_construction)
        assert not np.isnan(result.factor_declin_ratio)
        assert result.population == 2161000

    @pytest.mark.asyncio
    async def test_no_creations_yields_nan_factors(self, calc):
        data = self._make_pg_data(creations_sirene=0, liquidations_bodacc=0)
        result = await calc._calculate_dept_factors_v2("75", data, "Paris")
        # No creations and no liquidations → most factors are NaN
        assert np.isnan(result.factor_tension_emploi)
        assert np.isnan(result.factor_sante_entreprises)
        assert np.isnan(result.factor_declin_ratio)

    @pytest.mark.asyncio
    async def test_no_immo_data_keeps_immo_nan(self, calc):
        data = self._make_pg_data(transactions_dvf=0, prix_m2_dvf=0.0, logements_sitadel=0)
        result = await calc._calculate_dept_factors_v2("75", data, "Paris")
        assert np.isnan(result.factor_dynamisme_immo)
        assert np.isnan(result.factor_construction)
        # But sante and declin should still be valid
        assert not np.isnan(result.factor_sante_entreprises)

    @pytest.mark.asyncio
    async def test_population_fallback_when_pop_manager_returns_none(self, calc):
        calc.pop_manager.get_population = AsyncMock(return_value=None)
        result = await calc._calculate_dept_factors_v2("99", self._make_pg_data(), "Mayotte")
        assert result.population == 600000  # Default fallback in implementation

    @pytest.mark.asyncio
    async def test_missing_data_availability_returns_none(self, calc):
        # Trigger the except clause: drop the required data_availability key
        bad_data = self._make_pg_data()
        del bad_data["data_availability"]
        result = await calc._calculate_dept_factors_v2("75", bad_data, "Paris")
        assert result is None


class TestCalculateDeptFactorsLegacy:
    """Tests for TerritorialFactorsCalculatorV2._calculate_dept_factors_legacy."""

    @pytest.fixture
    def calc(self):
        return TerritorialFactorsCalculatorV2()

    @pytest.mark.asyncio
    async def test_with_full_legacy_data(self, calc):
        data_avail = SourceDataAvailability(
            sirene_creations=True, bodacc_liquidations=True, france_travail_offers=True
        )
        result = await calc._calculate_dept_factors_legacy(
            "75", "Paris", 1000, 100, 5000, 2161000, data_avail
        )
        assert result is not None
        assert result.code_dept == "75"
        assert result.population == 2161000
        assert not np.isnan(result.factor_tension_emploi)
        assert not np.isnan(result.factor_sante_entreprises)
        # Legacy doesn't compute immo/construction
        assert np.isnan(result.factor_dynamisme_immo)
        assert np.isnan(result.factor_construction)

    @pytest.mark.asyncio
    async def test_legacy_zero_creations(self, calc):
        data_avail = SourceDataAvailability(bodacc_liquidations=True)
        result = await calc._calculate_dept_factors_legacy(
            "01", "Ain", 0, 50, 0, 600000, data_avail
        )
        assert result is not None
        # No creations → tension_emploi NaN, sante NaN
        assert np.isnan(result.factor_tension_emploi)
        assert np.isnan(result.factor_sante_entreprises)
        # But declin_ratio is computed because liquidations > 0
        assert not np.isnan(result.factor_declin_ratio)


class TestCalculateFromSqlite:
    """Tests for TerritorialFactorsCalculatorV2._calculate_from_sqlite (fallback path)."""

    @pytest.fixture
    def calc(self):
        c = TerritorialFactorsCalculatorV2()
        c.pop_manager.get_population = AsyncMock(return_value=600000)
        return c

    @pytest.mark.asyncio
    async def test_returns_factors_for_each_row(self, calc):
        mock_cursor = MagicMock()
        # (code, name, avg_creations, avg_liquidations, avg_job_offers, nb_records)
        mock_cursor.fetchall.return_value = [
            ("75", "Paris", 100.0, 10.0, 500.0, 12),
            ("13", "Bouches-du-Rhone", 80.0, 8.0, 300.0, 12),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.collector.factors.sqlite3.connect", return_value=mock_conn):
            result = await calc._calculate_from_sqlite()

        assert len(result) == 2
        codes = {f.code_dept for f in result}
        assert codes == {"75", "13"}

    @pytest.mark.asyncio
    async def test_skips_dept_with_no_business_data(self, calc):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("01", "Ain", 0.0, 0.0, 0.0, 12),  # Should be skipped
            ("75", "Paris", 100.0, 10.0, 500.0, 12),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.collector.factors.sqlite3.connect", return_value=mock_conn):
            result = await calc._calculate_from_sqlite()

        assert len(result) == 1
        assert result[0].code_dept == "75"

    @pytest.mark.asyncio
    async def test_filters_by_code_dept(self, calc):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("75", "Paris", 100.0, 10.0, 500.0, 12)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.collector.factors.sqlite3.connect", return_value=mock_conn):
            result = await calc._calculate_from_sqlite(code_dept="75")

        assert len(result) == 1
        # Verify the WHERE clause was used (code_dept passed as param)
        call_args = mock_cursor.execute.call_args
        assert "WHERE territory_code = ?" in call_args[0][0]
        assert call_args[0][1] == ("75",)

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self, calc):
        with patch(
            "src.collector.factors.sqlite3.connect", side_effect=Exception("db gone")
        ):
            result = await calc._calculate_from_sqlite()
        assert result == []


class TestCalculateFactors:
    """Tests for TerritorialFactorsCalculatorV2.calculate_factors (main orchestration)."""

    @pytest.fixture
    def calc(self):
        c = TerritorialFactorsCalculatorV2()
        c.pop_manager.get_population = AsyncMock(return_value=2161000)
        return c

    @pytest.mark.asyncio
    async def test_falls_back_to_sqlite_when_pg_empty(self, calc):
        calc.pg_collector.collect_department_data = AsyncMock(return_value={})
        calc._calculate_from_sqlite = AsyncMock(return_value=["sqlite_result"])

        result = await calc.calculate_factors()

        assert result == ["sqlite_result"]
        calc._calculate_from_sqlite.assert_awaited_once_with(None)

    @pytest.mark.asyncio
    async def test_uses_pg_data_when_available(self, calc):
        pg_data = {
            "75": {
                "creations_sirene": 1000,
                "liquidations_bodacc": 100,
                "offres_france_travail": 5000,
                "transactions_dvf": 800,
                "prix_m2_dvf": 7000.0,
                "logements_sitadel": 200,
                "data_availability": SourceDataAvailability(sirene_creations=True),
            }
        }
        calc.pg_collector.collect_department_data = AsyncMock(return_value=pg_data)
        calc._get_department_names = AsyncMock(return_value={"75": "Paris"})

        result = await calc.calculate_factors()

        assert len(result) == 1
        assert result[0].code_dept == "75"
        assert result[0].nom == "Paris"
        # Composite score should be assigned
        assert result[0].rang_national == 1

    @pytest.mark.asyncio
    async def test_filters_by_code_dept_with_pg(self, calc):
        pg_data = {
            "75": {
                "creations_sirene": 1000,
                "liquidations_bodacc": 100,
                "offres_france_travail": 5000,
                "transactions_dvf": 800,
                "prix_m2_dvf": 7000.0,
                "logements_sitadel": 200,
                "data_availability": SourceDataAvailability(sirene_creations=True),
            },
            "13": {
                "creations_sirene": 800,
                "liquidations_bodacc": 80,
                "offres_france_travail": 3000,
                "transactions_dvf": 600,
                "prix_m2_dvf": 4000.0,
                "logements_sitadel": 150,
                "data_availability": SourceDataAvailability(sirene_creations=True),
            },
        }
        calc.pg_collector.collect_department_data = AsyncMock(return_value=pg_data)
        calc._get_department_names = AsyncMock(return_value={"75": "Paris"})

        result = await calc.calculate_factors(code_dept="75")

        assert len(result) == 1
        assert result[0].code_dept == "75"

    @pytest.mark.asyncio
    async def test_uses_default_name_when_not_in_dept_names(self, calc):
        pg_data = {
            "999": {
                "creations_sirene": 100,
                "liquidations_bodacc": 10,
                "offres_france_travail": 50,
                "transactions_dvf": 0,
                "prix_m2_dvf": 0.0,
                "logements_sitadel": 0,
                "data_availability": SourceDataAvailability(sirene_creations=True),
            }
        }
        calc.pg_collector.collect_department_data = AsyncMock(return_value=pg_data)
        calc._get_department_names = AsyncMock(return_value={})  # Empty mapping

        result = await calc.calculate_factors()

        assert result[0].nom == "Département 999"


class TestPostgreSQLCollectDepartmentData:
    """Tests for PostgreSQLDataCollector.collect_department_data with mocked psycopg2."""

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_connection_error(self):
        collector = PostgreSQLDataCollector()
        with patch(
            "src.collector.factors.psycopg2.connect", side_effect=Exception("conn refused")
        ):
            result = await collector.collect_department_data()
        assert result == {}

    @pytest.mark.asyncio
    async def test_aggregates_signal_rows_by_dept(self):
        collector = PostgreSQLDataCollector()
        mock_cursor = MagicMock()
        # (code_dept, source, metric_name, count, total, avg, last_collected)
        mock_cursor.fetchall.return_value = [
            ("75", "sirene", "creation", 1000, 1000, 1.0, datetime(2026, 4, 1)),
            ("75", "bodacc", "liquidation", 100, 100, 1.0, datetime(2026, 4, 1)),
            ("75", "france_travail", "offres", 5000, 5000, 1.0, datetime(2026, 4, 1)),
            ("75", "dvf", "transaction", 800, 800, 1.0, datetime(2026, 4, 1)),
            ("75", "dvf", "prix", 1, 7000.0, 7000.0, datetime(2026, 4, 1)),
            ("75", "sitadel", "logements", 200, 200, 1.0, datetime(2026, 4, 1)),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.collector.factors.psycopg2.connect", return_value=mock_conn):
            result = await collector.collect_department_data()

        assert "75" in result
        d = result["75"]
        assert d["creations_sirene"] == 1000
        assert d["liquidations_bodacc"] == 100
        assert d["offres_france_travail"] == 5000
        assert d["transactions_dvf"] == 800
        assert d["prix_m2_dvf"] == 7000.0
        assert d["logements_sitadel"] == 200
        assert d["data_availability"].sirene_creations is True
        assert d["data_availability"].bodacc_liquidations is True
        assert d["data_availability"].dvf_transactions is True
        assert d["data_availability"].sitadel_permits is True
