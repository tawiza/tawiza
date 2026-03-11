"""
Cross-source micro-signal detection algorithm.

The core intelligence: cross-references signals from multiple sources
(APIs + crawling) to detect territorial patterns:

- déclin territorial: fermetures SIRENE + emploi négatif FT + presse négatif
- dynamisme territorial: créations SIRENE + offres emploi FT + presse positif
- tension emploi: offres FT spike + presse recrutement
- crise sectorielle: fermetures cluster + licenciements + presse négatif
"""

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
from loguru import logger


@dataclass
class MicroSignal:
    """A detected micro-signal from cross-source analysis."""
    signal_type: str          # dynamisme_territorial, declin_territorial, etc.
    code_dept: str
    score: float              # 0-1 significance
    sources: list[str]        # contributing sources
    metrics: dict[str, float] # metric_name → z-score or value
    description: str = ""
    detected_at: date = field(default_factory=date.today)

    def to_anomaly_dict(self) -> dict[str, Any]:
        """Convert to anomaly table format."""
        return {
            "code_commune": self.code_dept,
            "anomaly_type": self.signal_type,
            "metrics": self.metrics,
            "sources": self.sources,
            "score": self.score,
            "description": self.description,
            "status": "new",
        }


# Cross-reference patterns
@dataclass
class CrossRefPattern:
    """A pattern that defines a micro-signal from multiple source conditions."""
    name: str
    signal_type: str
    description_template: str
    conditions: list[dict[str, Any]]
    # Each condition: {source, metric, direction: 'up'|'down', min_zscore: float}
    min_sources: int = 2  # minimum conditions that must match
    weight: float = 1.0


CROSSREF_PATTERNS: list[CrossRefPattern] = [
    CrossRefPattern(
        name="dynamisme_territorial",
        signal_type="dynamisme_territorial",
        description_template="Dynamisme territorial détecté dans le {dept}: convergence de signaux positifs ({sources})",
        conditions=[
            {"source": "sirene", "metric": "creation_entreprise", "direction": "up", "min_zscore": 1.5},
            {"source": "france_travail", "metric": "offres_emploi", "direction": "up", "min_zscore": 1.5},
            {"source": "presse_locale", "metric": "presse_creation", "direction": "up", "min_zscore": 1.0},
            {"source": "presse_locale", "metric": "presse_emploi_positif", "direction": "up", "min_zscore": 1.0},
            {"source": "presse_locale", "metric": "presse_investissement", "direction": "up", "min_zscore": 1.0},
        ],
        min_sources=2,
        weight=1.2,
    ),
    CrossRefPattern(
        name="declin_territorial",
        signal_type="declin_territorial",
        description_template="Déclin territorial détecté dans le {dept}: convergence de signaux négatifs ({sources})",
        conditions=[
            {"source": "sirene", "metric": "fermeture_entreprise", "direction": "up", "min_zscore": 1.5},
            {"source": "france_travail", "metric": "offres_emploi", "direction": "down", "min_zscore": -1.5},
            {"source": "presse_locale", "metric": "presse_fermeture", "direction": "up", "min_zscore": 1.0},
            {"source": "presse_locale", "metric": "presse_emploi_negatif", "direction": "up", "min_zscore": 1.0},
            {"source": "presse_locale", "metric": "presse_crise", "direction": "up", "min_zscore": 1.0},
        ],
        min_sources=2,
        weight=1.3,
    ),
    CrossRefPattern(
        name="tension_emploi",
        signal_type="tension_emploi",
        description_template="Tension sur l'emploi dans le {dept}: forte demande non satisfaite ({sources})",
        conditions=[
            {"source": "france_travail", "metric": "offres_emploi", "direction": "up", "min_zscore": 2.0},
            {"source": "presse_locale", "metric": "presse_emploi_positif", "direction": "up", "min_zscore": 1.0},
            {"source": "sirene", "metric": "creation_entreprise", "direction": "up", "min_zscore": 1.0},
        ],
        min_sources=2,
        weight=1.0,
    ),
    CrossRefPattern(
        name="crise_sectorielle",
        signal_type="crise_sectorielle",
        description_template="Crise sectorielle dans le {dept}: cluster de fermetures et licenciements ({sources})",
        conditions=[
            {"source": "sirene", "metric": "fermeture_entreprise", "direction": "up", "min_zscore": 2.0},
            {"source": "presse_locale", "metric": "presse_fermeture", "direction": "up", "min_zscore": 1.5},
            {"source": "presse_locale", "metric": "presse_emploi_negatif", "direction": "up", "min_zscore": 1.5},
        ],
        min_sources=2,
        weight=1.4,
    ),
    CrossRefPattern(
        name="attractivite",
        signal_type="attractivite",
        description_template="Attractivité croissante dans le {dept}: investissements et constructions ({sources})",
        conditions=[
            {"source": "presse_locale", "metric": "presse_investissement", "direction": "up", "min_zscore": 1.0},
            {"source": "presse_locale", "metric": "presse_construction", "direction": "up", "min_zscore": 1.0},
            {"source": "sirene", "metric": "creation_entreprise", "direction": "up", "min_zscore": 1.0},
        ],
        min_sources=2,
        weight=1.0,
    ),
    CrossRefPattern(
        name="desertification",
        signal_type="desertification",
        description_template="Risque de désertification dans le {dept}: services en recul ({sources})",
        conditions=[
            {"source": "presse_locale", "metric": "presse_desert", "direction": "up", "min_zscore": 1.0},
            {"source": "sirene", "metric": "fermeture_entreprise", "direction": "up", "min_zscore": 1.5},
            {"source": "france_travail", "metric": "offres_emploi", "direction": "down", "min_zscore": -1.0},
        ],
        min_sources=2,
        weight=1.2,
    ),
]


class CrossSourceDetector:
    """
    Cross-source anomaly detection engine.

    Algorithm:
    1. For each department, compute z-scores per (source, metric) over time window
    2. Match z-scores against CrossRefPatterns
    3. Score convergence: how many sources agree
    4. Emit MicroSignals for patterns with enough source convergence
    """

    def __init__(self, window_days: int = 30, baseline_days: int = 90) -> None:
        self._window = window_days
        self._baseline = baseline_days

    async def detect(
        self,
        signals_by_dept: dict[str, list[dict[str, Any]]],
    ) -> list[MicroSignal]:
        """
        Run cross-source detection on signals grouped by department.

        Args:
            signals_by_dept: {dept_code: [signal_dicts]} where each signal has
                source, metric_name, metric_value, event_date
        """
        results: list[MicroSignal] = []

        for dept, signals in signals_by_dept.items():
            if len(signals) < 5:
                continue

            try:
                dept_results = self._detect_for_dept(dept, signals)
                results.extend(dept_results)
            except Exception as e:
                logger.error(f"[crossref] Error on dept {dept}: {e}")

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        logger.info(f"[crossref] Detected {len(results)} micro-signals across {len(signals_by_dept)} departments")
        return results

    def _detect_for_dept(
        self, dept: str, signals: list[dict[str, Any]]
    ) -> list[MicroSignal]:
        """Detect patterns for a single department."""
        results = []

        # Group by (source, metric_name) and compute z-scores
        zscores = self._compute_zscores(signals)

        # Check each pattern
        for pattern in CROSSREF_PATTERNS:
            matched_conditions = []
            matched_sources = set()
            matched_metrics: dict[str, float] = {}

            for cond in pattern.conditions:
                key = (cond["source"], cond["metric"])
                if key not in zscores:
                    continue

                z = zscores[key]
                min_z = cond["min_zscore"]

                if cond["direction"] == "up" and z >= min_z or cond["direction"] == "down" and z <= min_z:
                    matched_conditions.append(cond)
                    matched_sources.add(cond["source"])
                    matched_metrics[cond["metric"]] = round(z, 2)

            # Pattern matches if enough conditions (from different sources) met
            if len(matched_conditions) >= pattern.min_sources and len(matched_sources) >= 2:
                # Score: ratio of matched conditions × max z-score × pattern weight
                z_values = [abs(v) for v in matched_metrics.values()]
                convergence = len(matched_conditions) / len(pattern.conditions)
                max_z = max(z_values) if z_values else 0
                score = min(convergence * (0.3 + 0.1 * max_z) * pattern.weight, 1.0)

                description = pattern.description_template.format(
                    dept=dept,
                    sources=", ".join(sorted(matched_sources)),
                )

                results.append(MicroSignal(
                    signal_type=pattern.signal_type,
                    code_dept=dept,
                    score=round(score, 3),
                    sources=sorted(matched_sources),
                    metrics=matched_metrics,
                    description=description,
                ))

        return results

    def _compute_zscores(
        self, signals: list[dict[str, Any]]
    ) -> dict[tuple[str, str], float]:
        """
        Compute z-scores for each (source, metric) pair.

        Uses the recent window vs baseline to detect anomalies.
        """
        today = date.today()
        window_start = today - timedelta(days=self._window)
        baseline_start = today - timedelta(days=self._baseline)

        # Group values by (source, metric)
        groups: dict[tuple[str, str], dict[str, list[float]]] = {}

        for s in signals:
            key = (s.get("source", ""), s.get("metric_name", ""))
            if key not in groups:
                groups[key] = {"window": [], "baseline": []}

            val = s.get("metric_value")
            if val is None:
                continue

            ev_date = s.get("event_date")
            if isinstance(ev_date, str):
                try:
                    ev_date = date.fromisoformat(ev_date)
                except ValueError:
                    continue

            if ev_date and ev_date >= window_start:
                groups[key]["window"].append(float(val))
            # Baseline = ONLY data BEFORE the window (excludes recent spike)
            if ev_date and ev_date >= baseline_start and ev_date < window_start:
                groups[key]["baseline"].append(float(val))

        # Compute z-scores
        zscores: dict[tuple[str, str], float] = {}

        for key, data in groups.items():
            baseline = data["baseline"]
            window = data["window"]

            if len(baseline) < 3 or not window:
                continue

            baseline_arr = np.array(baseline)
            mean = float(np.mean(baseline_arr))
            std = float(np.std(baseline_arr))

            if std < 1e-6:  # no variance
                continue

            window_mean = float(np.mean(window))
            z = (window_mean - mean) / std
            zscores[key] = z

        return zscores


class SpatialDetector:
    """
    Inter-department anomaly detection.

    Instead of comparing time windows (requires historical depth),
    compares each department against the national average for each metric.
    Detects outlier departments and cross-source convergences.
    """

    def __init__(self, min_zscore: float = 1.5, min_depts: int = 5) -> None:
        self._min_zscore = min_zscore
        self._min_depts = min_depts

    async def detect(
        self, signals_by_dept: dict[str, list[dict[str, Any]]]
    ) -> list[MicroSignal]:
        """Detect spatial anomalies across departments."""
        metric_by_dept: dict[tuple[str, str], dict[str, float]] = {}
        for dept, signals in signals_by_dept.items():
            groups: dict[tuple[str, str], list[float]] = {}
            for s in signals:
                val = s.get("metric_value")
                if val is None:
                    continue
                key = (s["source"], s["metric_name"])
                if key not in groups:
                    groups[key] = []
                groups[key].append(float(val))
            for key, values in groups.items():
                if key not in metric_by_dept:
                    metric_by_dept[key] = {}
                metric_by_dept[key][dept] = float(np.mean(values))

        # Find outlier departments per metric
        dept_anomalies: dict[str, list[dict[str, Any]]] = {}
        for (source, metric), dept_values in metric_by_dept.items():
            if len(dept_values) < self._min_depts:
                continue
            values = list(dept_values.values())
            mean = float(np.mean(values))
            std = float(np.std(values))
            if std < 1e-6:
                continue

            for dept, val in dept_values.items():
                z = (val - mean) / std
                if abs(z) >= self._min_zscore:
                    if dept not in dept_anomalies:
                        dept_anomalies[dept] = []
                    dept_anomalies[dept].append({
                        "source": source, "metric": metric,
                        "value": val, "mean": mean, "z": z,
                    })

        # Build micro-signals for departments with cross-source convergence
        results: list[MicroSignal] = []
        for dept, anomalies in dept_anomalies.items():
            sources = {a["source"] for a in anomalies}
            if len(sources) < 2:
                continue

            # Classify: mostly positive z → dynamisme, mostly negative → déclin
            z_values = [a["z"] for a in anomalies]
            avg_z = float(np.mean(z_values))
            max_abs_z = float(max(abs(z) for z in z_values))

            if avg_z > 0.5:
                signal_type = "dynamisme_territorial"
                desc = f"Dynamisme territorial dans le {dept}: {len(anomalies)} indicateurs au-dessus de la moyenne nationale"
            elif avg_z < -0.5:
                signal_type = "declin_territorial"
                desc = f"Déclin territorial dans le {dept}: {len(anomalies)} indicateurs en-dessous de la moyenne nationale"
            else:
                signal_type = "renouvellement"
                desc = f"Renouvellement économique dans le {dept}: signaux mixtes ({len(anomalies)} indicateurs atypiques)"

            score = min(len(anomalies) * 0.15 + max_abs_z * 0.1, 1.0)

            results.append(MicroSignal(
                signal_type=signal_type,
                code_dept=dept,
                score=round(score, 3),
                sources=sorted(sources),
                metrics={a["metric"]: round(a["z"], 2) for a in anomalies},
                description=desc,
            ))

        # === Ratio-based detection (liquidations vs créations) ===
        dept_counts: dict[str, dict[str, float]] = {}
        for dept, signals in signals_by_dept.items():
            dept_counts[dept] = {}
            for s in signals:
                m = s["metric_name"]
                v = s.get("metric_value")
                dept_counts[dept][m] = dept_counts[dept].get(m, 0) + (float(v) if v is not None else 1)

        # Liquidation/creation ratio
        ratios = {}
        for dept, counts in dept_counts.items():
            liq = counts.get("liquidation_judiciaire", 0)
            crea = counts.get("creation_entreprise", 0) + counts.get("immatriculation_rcs", 0)
            if crea > 0 and liq > 0:
                ratios[dept] = liq / crea

        if len(ratios) >= 3:
            vals = list(ratios.values())
            mean_r = float(np.mean(vals))
            std_r = float(np.std(vals))
            if std_r > 0.01:
                for dept, ratio in ratios.items():
                    z = (ratio - mean_r) / std_r
                    if z > 1.2:
                        # High liquidation ratio = economic distress
                        existing = [r for r in results if r.code_dept == dept and r.signal_type == "declin_territorial"]
                        if not existing:
                            results.append(MicroSignal(
                                signal_type="declin_territorial",
                                code_dept=dept,
                                score=round(min(0.5 + z * 0.15, 1.0), 3),
                                sources=["bodacc", "sirene"],
                                metrics={"ratio_liquidations_creations": round(ratio, 2), "z_score_ratio": round(z, 2)},
                                description=f"Détresse économique dans le {dept}: ratio liquidations/créations = {ratio:.1f} (moyenne nationale: {mean_r:.1f})",
                            ))
                    elif z < -1.2:
                        # Low liquidation ratio = dynamism
                        existing = [r for r in results if r.code_dept == dept and r.signal_type == "dynamisme_territorial"]
                        if not existing:
                            results.append(MicroSignal(
                                signal_type="dynamisme_territorial",
                                code_dept=dept,
                                score=round(min(0.5 + abs(z) * 0.15, 1.0), 3),
                                sources=["bodacc", "sirene"],
                                metrics={"ratio_liquidations_creations": round(ratio, 2), "z_score_ratio": round(z, 2)},
                                description=f"Dynamisme économique dans le {dept}: ratio liquidations/créations = {ratio:.1f} (nettement sous la moyenne {mean_r:.1f})",
                            ))

        results.sort(key=lambda r: r.score, reverse=True)
        logger.info(f"[crossref-spatial] Detected {len(results)} micro-signals across {len(signals_by_dept)} departments")
        return results


async def run_cross_source_detection(
    repo: Any,  # SignalRepository
    window_days: int = 7,
    baseline_days: int = 30,
) -> list[MicroSignal]:
    """
    High-level function: fetch signals from DB, run cross-source detection.

    Runs both temporal (if enough history) and spatial (inter-department) detection.
    """
    since = date.today() - timedelta(days=max(baseline_days, 3650))
    signals = await repo.get_signals(since=since, limit=50000)

    # Group by department
    by_dept: dict[str, list[dict[str, Any]]] = {}
    for s in signals:
        dept = s.code_dept or "unknown"
        if dept not in by_dept:
            by_dept[dept] = []
        by_dept[dept].append({
            "source": s.source,
            "metric_name": s.metric_name,
            "metric_value": s.metric_value,
            "event_date": s.event_date,
        })

    results: list[MicroSignal] = []

    # 1. Temporal detection (original)
    temporal = CrossSourceDetector(window_days=window_days, baseline_days=baseline_days)
    results.extend(await temporal.detect(by_dept))

    # 2. Spatial detection (inter-department comparison)
    spatial = SpatialDetector()
    results.extend(await spatial.detect(by_dept))

    # Deduplicate by (dept, signal_type), keep highest score
    seen: dict[tuple[str, str], MicroSignal] = {}
    for ms in results:
        key = (ms.code_dept, ms.signal_type)
        if key not in seen or ms.score > seen[key].score:
            seen[key] = ms

    final = sorted(seen.values(), key=lambda r: r.score, reverse=True)
    return final
