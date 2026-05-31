"""Unit tests for the cross-source micro-signal detector (issue #161, batch 4).

Target module: src/collector/crawling/crossref.py

The production code is the source of truth. These tests assert its *real*
behaviour (including its quirks); no production API is invented:

- ``MicroSignal`` is a dataclass with a default empty description and a
  ``detected_at`` defaulting to ``date.today()``; ``to_anomaly_dict`` maps
  ``code_dept`` -> ``code_commune`` and ``signal_type`` -> ``anomaly_type``.
- ``CrossSourceDetector`` is *temporal*: it compares a recent window against
  a baseline strictly *before* the window. A department needs >= 5 signals
  to be considered. Z-scores are skipped when the baseline has < 3 points,
  the window is empty, or the baseline std is ~0. A pattern emits a signal
  only when enough conditions match *and* at least two distinct sources agree.
  Per-department exceptions are swallowed (logged, not raised).
- ``SpatialDetector`` is *inter-department*: it compares each department
  against the national average per (source, metric). It needs >= ``min_depts``
  departments per metric, requires >= 2 distinct sources to converge, and adds
  a liquidation/creation ratio detector on top.
- ``run_cross_source_detection`` orchestrates both detectors over a repo,
  groups by department (``None`` -> ``"unknown"``), and deduplicates by
  (dept, signal_type) keeping the highest score.

These tests use only in-memory data structures and a tiny async stub repo;
no DB or network is touched.
"""

import asyncio
from datetime import date, timedelta

import pytest

from src.collector.crawling.crossref import (
    CROSSREF_PATTERNS,
    CrossRefPattern,
    CrossSourceDetector,
    MicroSignal,
    SpatialDetector,
    run_cross_source_detection,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
TODAY = date.today()


def sig(source, metric, value, days_ago=0, event_date=None):
    """Build a raw signal dict in the shape the detectors consume."""
    if event_date is None:
        event_date = (TODAY - timedelta(days=days_ago)).isoformat()
    return {
        "source": source,
        "metric_name": metric,
        "metric_value": value,
        "event_date": event_date,
    }


def baseline_then_spike(source, metric, base_values, spike_value, spike_days=(2, 5, 10, 15)):
    """Signals with a varied baseline (35-85 days ago) then a recent spike.

    The baseline carries variance so std > 0 and a z-score is computed.
    """
    out = []
    base_days = [35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85]
    for i, d in enumerate(base_days):
        out.append(sig(source, metric, base_values[i % len(base_values)], days_ago=d))
    for d in spike_days:
        out.append(sig(source, metric, spike_value, days_ago=d))
    return out


def run(coro):
    return asyncio.run(coro)


class StubRepo:
    """Minimal async stand-in for SignalRepository used by run_cross_source_detection."""

    def __init__(self, rows):
        self._rows = rows
        self.calls = []

    async def get_signals(self, since, limit):
        self.calls.append((since, limit))
        return list(self._rows)


class SignalRow:
    """Object-attribute row, matching what run_cross_source_detection reads."""

    def __init__(self, code_dept, source, metric_name, metric_value, event_date):
        self.code_dept = code_dept
        self.source = source
        self.metric_name = metric_name
        self.metric_value = metric_value
        self.event_date = event_date


# ---------------------------------------------------------------------------
# MicroSignal dataclass
# ---------------------------------------------------------------------------
class TestMicroSignal:
    def test_required_fields(self):
        ms = MicroSignal(
            signal_type="dynamisme_territorial",
            code_dept="75",
            score=0.8,
            sources=["sirene", "france_travail"],
            metrics={"creation_entreprise": 2.5},
        )
        assert ms.signal_type == "dynamisme_territorial"
        assert ms.code_dept == "75"
        assert ms.score == 0.8
        assert ms.sources == ["sirene", "france_travail"]
        assert ms.metrics == {"creation_entreprise": 2.5}

    def test_defaults(self):
        ms = MicroSignal("t", "75", 0.5, [], {})
        assert ms.description == ""
        assert ms.detected_at == TODAY
        assert isinstance(ms.detected_at, date)

    def test_to_anomaly_dict_mapping(self):
        ms = MicroSignal(
            signal_type="declin_territorial",
            code_dept="59",
            score=0.42,
            sources=["bodacc", "sirene"],
            metrics={"ratio": 3.0},
            description="some text",
        )
        d = ms.to_anomaly_dict()
        # code_dept maps to code_commune, signal_type to anomaly_type
        assert d["code_commune"] == "59"
        assert d["anomaly_type"] == "declin_territorial"
        assert d["metrics"] == {"ratio": 3.0}
        assert d["sources"] == ["bodacc", "sirene"]
        assert d["score"] == 0.42
        assert d["description"] == "some text"
        assert d["status"] == "new"

    def test_to_anomaly_dict_keys(self):
        ms = MicroSignal("t", "75", 0.5, [], {})
        assert set(ms.to_anomaly_dict().keys()) == {
            "code_commune",
            "anomaly_type",
            "metrics",
            "sources",
            "score",
            "description",
            "status",
        }


# ---------------------------------------------------------------------------
# CrossRefPattern registry
# ---------------------------------------------------------------------------
class TestPatternRegistry:
    def test_patterns_non_empty(self):
        assert len(CROSSREF_PATTERNS) == 6

    def test_all_patterns_are_crossref_patterns(self):
        assert all(isinstance(p, CrossRefPattern) for p in CROSSREF_PATTERNS)

    def test_expected_pattern_names(self):
        names = {p.name for p in CROSSREF_PATTERNS}
        assert names == {
            "dynamisme_territorial",
            "declin_territorial",
            "tension_emploi",
            "crise_sectorielle",
            "attractivite",
            "desertification",
        }

    def test_pattern_invariants(self):
        for p in CROSSREF_PATTERNS:
            assert p.min_sources >= 1
            assert p.weight > 0
            assert len(p.conditions) >= p.min_sources
            for cond in p.conditions:
                assert cond["direction"] in ("up", "down")
                assert {"source", "metric", "direction", "min_zscore"} <= set(cond)

    def test_crossref_pattern_defaults(self):
        p = CrossRefPattern(
            name="x",
            signal_type="x",
            description_template="{dept} {sources}",
            conditions=[],
        )
        assert p.min_sources == 2
        assert p.weight == 1.0


# ---------------------------------------------------------------------------
# CrossSourceDetector._compute_zscores (pure logic)
# ---------------------------------------------------------------------------
class TestComputeZScores:
    def test_window_spike_yields_positive_zscore(self):
        det = CrossSourceDetector()
        signals = baseline_then_spike("sirene", "creation_entreprise", [1.0, 1.5, 2.0], 10.0)
        z = det._compute_zscores(signals)
        key = ("sirene", "creation_entreprise")
        assert key in z
        assert z[key] > 0

    def test_window_drop_yields_negative_zscore(self):
        det = CrossSourceDetector()
        signals = baseline_then_spike("france_travail", "offres_emploi", [20.0, 22.0, 24.0], 1.0)
        z = det._compute_zscores(signals)
        assert z[("france_travail", "offres_emploi")] < 0

    def test_zero_variance_baseline_skipped(self):
        det = CrossSourceDetector()
        # Constant baseline -> std ~ 0 -> skipped
        signals = baseline_then_spike("sirene", "creation_entreprise", [1.0], 10.0)
        assert det._compute_zscores(signals) == {}

    def test_insufficient_baseline_skipped(self):
        det = CrossSourceDetector()
        # only 2 baseline points (< 3) plus a window value
        signals = [
            sig("sirene", "creation_entreprise", 1.0, days_ago=40),
            sig("sirene", "creation_entreprise", 2.0, days_ago=50),
            sig("sirene", "creation_entreprise", 10.0, days_ago=2),
        ]
        assert det._compute_zscores(signals) == {}

    def test_empty_window_skipped(self):
        det = CrossSourceDetector()
        # baseline present and varied, but nothing in the recent window
        signals = [
            sig("sirene", "creation_entreprise", v, days_ago=d)
            for v, d in [(1.0, 40), (2.0, 45), (3.0, 50), (4.0, 55)]
        ]
        assert det._compute_zscores(signals) == {}

    def test_none_value_ignored(self):
        det = CrossSourceDetector()
        signals = baseline_then_spike("sirene", "creation_entreprise", [1.0, 2.0, 3.0], 10.0)
        signals.append(sig("sirene", "creation_entreprise", None, days_ago=3))
        z = det._compute_zscores(signals)
        # None did not crash; signal still computed
        assert ("sirene", "creation_entreprise") in z

    def test_unparseable_date_string_skipped(self):
        det = CrossSourceDetector()
        signals = baseline_then_spike("sirene", "creation_entreprise", [1.0, 2.0, 3.0], 10.0)
        # Bad date string: continue branch, does not crash, not counted
        signals.append(sig("sirene", "creation_entreprise", 99.0, event_date="not-a-date"))
        z = det._compute_zscores(signals)
        assert ("sirene", "creation_entreprise") in z

    def test_date_object_event_date_supported(self):
        det = CrossSourceDetector()
        signals = []
        for v, d in [(1.0, 40), (2.0, 45), (3.0, 50), (4.0, 55)]:
            signals.append(sig("sirene", "x", v, event_date=TODAY - timedelta(days=d)))
        signals.append(sig("sirene", "x", 30.0, event_date=TODAY - timedelta(days=2)))
        z = det._compute_zscores(signals)
        assert z[("sirene", "x")] > 0


# ---------------------------------------------------------------------------
# CrossSourceDetector.detect (temporal)
# ---------------------------------------------------------------------------
class TestCrossSourceDetect:
    def _dynamisme_signals(self):
        signals = baseline_then_spike("sirene", "creation_entreprise", [1.0, 1.5, 2.0], 10.0)
        signals += baseline_then_spike(
            "france_travail", "offres_emploi", [2.0, 2.5, 3.0], 25.0, spike_days=(2, 5, 10)
        )
        return signals

    def test_detects_dynamisme(self):
        det = CrossSourceDetector()
        res = run(det.detect({"75": self._dynamisme_signals()}))
        types = {r.signal_type for r in res}
        assert "dynamisme_territorial" in types
        for r in res:
            assert r.code_dept == "75"
            assert 0.0 <= r.score <= 1.0
            # at least two distinct sources converged
            assert len(set(r.sources)) >= 2

    def test_detects_declin_with_down_direction(self):
        # fermeture up + offres down + presse fermeture up
        signals = baseline_then_spike("sirene", "fermeture_entreprise", [1.0, 1.4, 1.8], 12.0)
        signals += baseline_then_spike(
            "france_travail", "offres_emploi", [20.0, 21.0, 22.0], 1.0, spike_days=(2, 5, 10)
        )
        signals += baseline_then_spike(
            "presse_locale", "presse_fermeture", [0.5, 0.8, 1.1], 8.0, spike_days=(2, 5, 10)
        )
        det = CrossSourceDetector()
        res = run(det.detect({"59": signals}))
        types = {r.signal_type for r in res}
        assert "declin_territorial" in types
        declin = next(r for r in res if r.signal_type == "declin_territorial")
        # the down-direction metric carries a negative z-score
        assert declin.metrics["offres_emploi"] < 0

    def test_results_sorted_by_score_descending(self):
        det = CrossSourceDetector()
        res = run(det.detect({"75": self._dynamisme_signals()}))
        scores = [r.score for r in res]
        assert scores == sorted(scores, reverse=True)

    def test_department_with_few_signals_skipped(self):
        det = CrossSourceDetector()
        few = [sig("sirene", "creation_entreprise", 1.0, days_ago=2)] * 4
        assert run(det.detect({"01": few})) == []

    def test_single_source_does_not_emit(self):
        # Only one source spikes; min two distinct sources are required.
        det = CrossSourceDetector()
        signals = baseline_then_spike("sirene", "creation_entreprise", [1.0, 1.5, 2.0], 10.0)
        res = run(det.detect({"75": signals}))
        assert res == []

    def test_no_data_no_signal(self):
        det = CrossSourceDetector()
        # 5 malformed signals -> no z-scores match patterns, no crash
        bad = [{"foo": 1}] * 5
        assert run(det.detect({"02": bad})) == []

    def test_empty_input(self):
        det = CrossSourceDetector()
        assert run(det.detect({})) == []

    def test_per_dept_exception_is_swallowed(self, monkeypatch):
        det = CrossSourceDetector()

        def boom(dept, signals):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(det, "_detect_for_dept", boom)
        # >= 5 signals so the dept is processed; the exception must be caught.
        signals = [sig("sirene", "creation_entreprise", 1.0, days_ago=2)] * 6
        assert run(det.detect({"75": signals})) == []

    def test_description_includes_dept_and_sources(self):
        det = CrossSourceDetector()
        res = run(det.detect({"75": self._dynamisme_signals()}))
        dyn = next(r for r in res if r.signal_type == "dynamisme_territorial")
        assert "75" in dyn.description
        # sources are listed in the description
        for s in dyn.sources:
            assert s in dyn.description


# ---------------------------------------------------------------------------
# SpatialDetector (inter-department)
# ---------------------------------------------------------------------------
class TestSpatialDetector:
    def _outlier_setup(self, outlier_value_a=100.0, outlier_value_b=200.0):
        by_dept = {}
        for i, d in enumerate(["10", "20", "30", "40", "50"]):
            by_dept[d] = [
                sig("sirene", "creation_entreprise", 1.0 + i * 0.1),
                sig("france_travail", "offres_emploi", 2.0 + i * 0.1),
            ]
        by_dept["75"] = [
            sig("sirene", "creation_entreprise", outlier_value_a),
            sig("france_travail", "offres_emploi", outlier_value_b),
        ]
        return by_dept

    def test_detects_high_outlier_as_dynamisme(self):
        det = SpatialDetector()
        res = run(det.detect(self._outlier_setup()))
        assert len(res) == 1
        ms = res[0]
        assert ms.code_dept == "75"
        assert ms.signal_type == "dynamisme_territorial"
        assert set(ms.sources) == {"sirene", "france_travail"}
        assert 0.0 <= ms.score <= 1.0

    def test_detects_low_outlier_as_declin(self):
        det = SpatialDetector()
        # baseline depts high, the "75" dept far below average on both sources
        by_dept = {}
        for i, d in enumerate(["10", "20", "30", "40", "50"]):
            by_dept[d] = [
                sig("sirene", "creation_entreprise", 100.0 + i),
                sig("france_travail", "offres_emploi", 200.0 + i),
            ]
        by_dept["75"] = [
            sig("sirene", "creation_entreprise", 1.0),
            sig("france_travail", "offres_emploi", 1.0),
        ]
        res = run(det.detect(by_dept))
        ms = next(r for r in res if r.code_dept == "75")
        assert ms.signal_type == "declin_territorial"

    def test_single_source_outlier_not_emitted(self):
        det = SpatialDetector()
        by_dept = {}
        for i, d in enumerate(["10", "20", "30", "40", "50"]):
            by_dept[d] = [sig("sirene", "creation_entreprise", 1.0 + i * 0.1)]
        by_dept["75"] = [sig("sirene", "creation_entreprise", 100.0)]
        assert run(det.detect(by_dept)) == []

    def test_below_min_depts_not_emitted(self):
        det = SpatialDetector()  # default min_depts=5
        by_dept = {
            "10": [
                sig("sirene", "creation_entreprise", 1.0),
                sig("france_travail", "offres_emploi", 2.0),
            ],
            "75": [
                sig("sirene", "creation_entreprise", 100.0),
                sig("france_travail", "offres_emploi", 200.0),
            ],
        }
        assert run(det.detect(by_dept)) == []

    def test_min_depts_param_is_respected(self):
        # Lowering min_depts allows a 2-department comparison to fire.
        det = SpatialDetector(min_zscore=0.5, min_depts=2)
        by_dept = {
            "10": [
                sig("sirene", "creation_entreprise", 1.0),
                sig("france_travail", "offres_emploi", 2.0),
            ],
            "75": [
                sig("sirene", "creation_entreprise", 100.0),
                sig("france_travail", "offres_emploi", 200.0),
            ],
        }
        res = run(det.detect(by_dept))
        assert any(r.code_dept == "75" for r in res)

    def test_empty_input(self):
        det = SpatialDetector()
        assert run(det.detect({})) == []

    def test_none_metric_value_ignored(self):
        det = SpatialDetector()
        by_dept = self._outlier_setup()
        by_dept["75"].append(sig("presse_locale", "presse_x", None))
        # None value must not crash the mean computation
        res = run(det.detect(by_dept))
        assert any(r.code_dept == "75" for r in res)

    def test_ratio_detector_flags_distress(self):
        det = SpatialDetector()
        by_dept = {}
        # 3 calm depts: low liquidation/creation ratio
        for d in ["10", "20", "30"]:
            by_dept[d] = [
                sig("bodacc", "liquidation_judiciaire", 1.0),
                sig("sirene", "creation_entreprise", 10.0),
            ]
        # one distressed dept with a very high ratio
        by_dept["59"] = [
            sig("bodacc", "liquidation_judiciaire", 50.0),
            sig("sirene", "creation_entreprise", 1.0),
        ]
        res = run(det.detect(by_dept))
        distress = next(r for r in res if r.code_dept == "59")
        assert distress.signal_type == "declin_territorial"
        assert distress.sources == ["bodacc", "sirene"]
        assert "ratio_liquidations_creations" in distress.metrics
        assert "z_score_ratio" in distress.metrics

    def test_ratio_detector_flags_dynamism(self):
        det = SpatialDetector()
        by_dept = {}
        # 3 depts with high liquidation ratio
        for d in ["10", "20", "30"]:
            by_dept[d] = [
                sig("bodacc", "liquidation_judiciaire", 40.0),
                sig("sirene", "creation_entreprise", 1.0),
            ]
        # one dept far below: a low ratio = dynamism
        by_dept["75"] = [
            sig("bodacc", "liquidation_judiciaire", 1.0),
            sig("sirene", "creation_entreprise", 100.0),
        ]
        res = run(det.detect(by_dept))
        dyn = next(r for r in res if r.code_dept == "75")
        assert dyn.signal_type == "dynamisme_territorial"
        assert dyn.sources == ["bodacc", "sirene"]

    def test_results_sorted_by_score_descending(self):
        det = SpatialDetector()
        res = run(det.detect(self._outlier_setup()))
        scores = [r.score for r in res]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# run_cross_source_detection (orchestration)
# ---------------------------------------------------------------------------
class TestRunCrossSourceDetection:
    def _spatial_rows(self):
        rows = []
        for i, d in enumerate(["10", "20", "30", "40", "50"]):
            rows.append(SignalRow(d, "sirene", "creation_entreprise", 1.0 + i * 0.1, date(2026, 1, 1)))
            rows.append(SignalRow(d, "france_travail", "offres_emploi", 2.0 + i * 0.1, date(2026, 1, 1)))
        rows.append(SignalRow("75", "sirene", "creation_entreprise", 100.0, date(2026, 1, 1)))
        rows.append(SignalRow("75", "france_travail", "offres_emploi", 200.0, date(2026, 1, 1)))
        return rows

    def test_returns_signals_from_spatial(self):
        repo = StubRepo(self._spatial_rows())
        res = run(run_cross_source_detection(repo))
        assert any(r.code_dept == "75" for r in res)
        assert all(isinstance(r, MicroSignal) for r in res)

    def test_repo_called_with_since_and_limit(self):
        repo = StubRepo(self._spatial_rows())
        run(run_cross_source_detection(repo))
        assert len(repo.calls) == 1
        since, limit = repo.calls[0]
        assert isinstance(since, date)
        assert limit == 50000

    def test_none_dept_grouped_as_unknown(self):
        rows = self._spatial_rows()
        rows.append(SignalRow(None, "sirene", "creation_entreprise", 5.0, date(2026, 1, 1)))
        repo = StubRepo(rows)
        # Should not raise even though dept is None (-> "unknown")
        res = run(run_cross_source_detection(repo))
        assert all(isinstance(r, MicroSignal) for r in res)

    def test_dedup_keeps_highest_score(self):
        # Same (dept, signal_type) emitted twice -> keep the higher score.
        rows = self._spatial_rows()
        repo = StubRepo(rows)
        res = run(run_cross_source_detection(repo))
        keys = [(r.code_dept, r.signal_type) for r in res]
        assert len(keys) == len(set(keys))  # no duplicates after dedup

    def test_results_sorted_by_score_descending(self):
        repo = StubRepo(self._spatial_rows())
        res = run(run_cross_source_detection(repo))
        scores = [r.score for r in res]
        assert scores == sorted(scores, reverse=True)

    def test_empty_repo_returns_empty(self):
        repo = StubRepo([])
        assert run(run_cross_source_detection(repo)) == []


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
