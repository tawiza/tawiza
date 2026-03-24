"""
Competitor Analyzer - Benchmarking territorial.

Compare un territoire à:
- Ses voisins géographiques
- Des territoires similaires (même catégorie)
- La moyenne nationale
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger

from .attractiveness_scorer import (
    AttractiveAxis,
    AttractivenessScore,
    AttractivenessScorer,
)

# Voisins par département
NEIGHBORS: dict[str, list[str]] = {
    "01": ["38", "69", "71", "39", "73", "74"],
    "06": ["83", "04", "05"],
    "13": ["84", "30", "83", "04"],
    "31": ["32", "82", "81", "11", "09", "65"],
    "33": ["17", "16", "24", "47", "40"],
    "34": ["30", "11", "81", "12"],
    "38": ["73", "69", "01", "26", "05"],
    "44": ["85", "49", "35", "56"],
    "59": ["62", "80", "02"],
    "67": ["57", "54", "88", "68"],
    "69": ["01", "38", "42", "71"],
    "75": ["92", "93", "94"],
    "92": ["75", "93", "94", "78", "91"],
    "93": ["75", "92", "94", "77", "95"],
    "94": ["75", "92", "93", "77", "91"],
}

# Groupes de comparaison
COMPARISON_GROUPS: dict[str, list[str]] = {
    "metropoles": ["75", "69", "13", "31", "33", "44", "59", "67", "06", "34"],
    "idf": ["75", "77", "78", "91", "92", "93", "94", "95"],
    "grandes_villes": ["69", "13", "31", "33", "44", "59", "67", "06", "34", "35"],
    "ouest": ["44", "35", "29", "56", "22", "49", "85"],
    "sud_est": ["13", "06", "83", "84", "30", "34"],
    "aura": ["69", "38", "42", "01", "73", "74", "07", "26", "63", "43", "03", "15"],
}


@dataclass
class StrengthWeakness:
    """Force ou faiblesse relative."""

    axis: str
    score_territory: float
    score_comparators: float
    delta: float  # positif = force, négatif = faiblesse
    delta_pct: float
    is_strength: bool


@dataclass
class TerritoryComparison:
    """Comparaison avec un territoire."""

    code: str
    name: str
    global_score: float
    delta_global: float
    axes_deltas: dict[str, float]


@dataclass
class CompetitorAnalysis:
    """Analyse concurrentielle complète."""

    territory_code: str
    territory_name: str
    territory_score: AttractivenessScore
    computed_at: datetime

    # Comparaisons
    neighbors_comparison: list[TerritoryComparison]
    similar_comparison: list[TerritoryComparison]
    national_average: float

    # Forces/Faiblesses
    strengths: list[StrengthWeakness]
    weaknesses: list[StrengthWeakness]

    # Ranking
    rank_in_group: int
    group_size: int
    comparison_group: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "territory_code": self.territory_code,
            "territory_name": self.territory_name,
            "computed_at": self.computed_at.isoformat(),
            "global_score": round(self.territory_score.global_score, 1),
            "national_average": round(self.national_average, 1),
            "delta_national": round(self.territory_score.global_score - self.national_average, 1),
            "rank_in_group": self.rank_in_group,
            "group_size": self.group_size,
            "comparison_group": self.comparison_group,
            "neighbors": [
                {
                    "code": n.code,
                    "name": n.name,
                    "score": round(n.global_score, 1),
                    "delta": round(n.delta_global, 1),
                }
                for n in self.neighbors_comparison
            ],
            "similar_territories": [
                {
                    "code": s.code,
                    "name": s.name,
                    "score": round(s.global_score, 1),
                    "delta": round(s.delta_global, 1),
                }
                for s in self.similar_comparison
            ],
            "strengths": [
                {
                    "axis": s.axis,
                    "delta": round(s.delta, 1),
                    "delta_pct": f"+{s.delta_pct:.0f}%",
                    "territory_score": round(s.score_territory, 1),
                    "comparators_avg": round(s.score_comparators, 1),
                }
                for s in self.strengths
            ],
            "weaknesses": [
                {
                    "axis": w.axis,
                    "delta": round(w.delta, 1),
                    "delta_pct": f"{w.delta_pct:.0f}%",
                    "territory_score": round(w.score_territory, 1),
                    "comparators_avg": round(w.score_comparators, 1),
                }
                for w in self.weaknesses
            ],
            "radar_comparison": {
                "territory": {
                    axis.value: round(self.territory_score.axes[axis].score, 1)
                    for axis in AttractiveAxis
                },
                "average_comparators": self._compute_average_radar(),
            },
        }

    def _compute_average_radar(self) -> dict[str, float]:
        """Compute average radar from similar territories."""
        if not self.similar_comparison:
            return {axis.value: 50.0 for axis in AttractiveAxis}

        # Placeholder - would need actual axes data
        return {axis.value: self.national_average for axis in AttractiveAxis}

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            f"# Analyse Concurrentielle - {self.territory_name} ({self.territory_code})",
            "",
            f"**Date:** {self.computed_at.strftime('%d/%m/%Y %H:%M')}",
            "",
            "---",
            "",
            "## 📊 Position Globale",
            "",
            "| Indicateur | Valeur |",
            "|------------|--------|",
            f"| **Score global** | {self.territory_score.global_score:.1f}/100 |",
            f"| **Moyenne nationale** | {self.national_average:.1f}/100 |",
            f"| **Écart** | {self.territory_score.global_score - self.national_average:+.1f} |",
            f"| **Rang dans le groupe** | {self.rank_in_group}/{self.group_size} |",
            f"| **Groupe de comparaison** | {self.comparison_group} |",
            "",
            "---",
            "",
            "## 💪 Forces Relatives",
            "",
        ]

        if self.strengths:
            for s in self.strengths:
                lines.append(
                    f"- **{s.axis}**: {s.score_territory:.1f} vs {s.score_comparators:.1f} "
                    f"(+{s.delta:.1f}, +{s.delta_pct:.0f}%)"
                )
        else:
            lines.append("*Aucune force significative identifiée.*")

        lines.extend(
            [
                "",
                "---",
                "",
                "## ⚠️ Faiblesses Relatives",
                "",
            ]
        )

        if self.weaknesses:
            for w in self.weaknesses:
                lines.append(
                    f"- **{w.axis}**: {w.score_territory:.1f} vs {w.score_comparators:.1f} "
                    f"({w.delta:.1f}, {w.delta_pct:.0f}%)"
                )
        else:
            lines.append("*Aucune faiblesse significative identifiée.*")

        lines.extend(
            [
                "",
                "---",
                "",
                "## 🗺️ Voisins Géographiques",
                "",
                "| Territoire | Score | Écart |",
                "|------------|-------|-------|",
            ]
        )

        for n in self.neighbors_comparison:
            delta_str = f"+{n.delta_global:.1f}" if n.delta_global > 0 else f"{n.delta_global:.1f}"
            lines.append(f"| {n.name} ({n.code}) | {n.global_score:.1f} | {delta_str} |")

        lines.extend(
            [
                "",
                "---",
                "",
                "## 🏆 Territoires Similaires",
                "",
                "| Territoire | Score | Écart |",
                "|------------|-------|-------|",
            ]
        )

        for s in self.similar_comparison:
            delta_str = f"+{s.delta_global:.1f}" if s.delta_global > 0 else f"{s.delta_global:.1f}"
            lines.append(f"| {s.name} ({s.code}) | {s.global_score:.1f} | {delta_str} |")

        lines.extend(
            [
                "",
                "---",
                "",
                "*Rapport généré par TAJINE Territorial Analyzer*",
            ]
        )

        return "\n".join(lines)


class CompetitorAnalyzer:
    """
    Analyse concurrentielle territoriale.

    Compare un territoire à ses voisins et territoires similaires,
    identifie forces et faiblesses relatives.
    """

    def __init__(self) -> None:
        """Initialize the analyzer."""
        self._scorer = AttractivenessScorer()
        self._score_cache: dict[str, AttractivenessScore] = {}

    async def compare(
        self,
        territory_code: str,
        include_neighbors: bool = True,
        include_similar: bool = True,
        comparison_group: str | None = None,
    ) -> CompetitorAnalysis:
        """
        Compare a territory to its competitors.

        Args:
            territory_code: Code département
            include_neighbors: Include geographic neighbors
            include_similar: Include similar territories
            comparison_group: Force specific comparison group

        Returns:
            Complete CompetitorAnalysis
        """
        logger.info(f"Running competitor analysis for {territory_code}")

        # Score the target territory
        territory_score = await self._get_score(territory_code)

        # Determine comparison group
        group = comparison_group or self._determine_group(territory_code)
        group_codes = COMPARISON_GROUPS.get(group, COMPARISON_GROUPS["metropoles"])

        # Score all relevant territories in parallel
        codes_to_score = set()
        if include_neighbors:
            codes_to_score.update(NEIGHBORS.get(territory_code, []))
        if include_similar:
            codes_to_score.update(group_codes)
        codes_to_score.discard(territory_code)

        # Parallel scoring
        tasks = [self._get_score(code) for code in codes_to_score]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scored: dict[str, AttractivenessScore] = {}
        for code, result in zip(codes_to_score, results, strict=False):
            if isinstance(result, AttractivenessScore):
                scored[code] = result
            else:
                logger.warning(f"Failed to score {code}: {result}")

        # Build neighbor comparisons
        neighbors_comparison = []
        neighbor_codes = NEIGHBORS.get(territory_code, [])
        for code in neighbor_codes:
            if code in scored:
                s = scored[code]
                neighbors_comparison.append(
                    TerritoryComparison(
                        code=code,
                        name=s.territory_name,
                        global_score=s.global_score,
                        delta_global=territory_score.global_score - s.global_score,
                        axes_deltas={
                            axis.value: territory_score.axes[axis].score - s.axes[axis].score
                            for axis in AttractiveAxis
                        },
                    )
                )

        # Build similar territory comparisons
        similar_comparison = []
        for code in group_codes:
            if code in scored and code != territory_code:
                s = scored[code]
                similar_comparison.append(
                    TerritoryComparison(
                        code=code,
                        name=s.territory_name,
                        global_score=s.global_score,
                        delta_global=territory_score.global_score - s.global_score,
                        axes_deltas={
                            axis.value: territory_score.axes[axis].score - s.axes[axis].score
                            for axis in AttractiveAxis
                        },
                    )
                )

        # Sort by score
        similar_comparison.sort(key=lambda x: x.global_score, reverse=True)

        # Calculate national average (from scored territories)
        all_scores = [territory_score.global_score] + [s.global_score for s in scored.values()]
        national_average = sum(all_scores) / len(all_scores) if all_scores else 50.0

        # Identify strengths and weaknesses
        strengths, weaknesses = self._identify_strengths_weaknesses(territory_score, scored)

        # Calculate rank
        all_in_group = [territory_score.global_score] + [
            s.global_score for code, s in scored.items() if code in group_codes
        ]
        all_in_group.sort(reverse=True)
        rank = all_in_group.index(territory_score.global_score) + 1

        return CompetitorAnalysis(
            territory_code=territory_code,
            territory_name=territory_score.territory_name,
            territory_score=territory_score,
            computed_at=datetime.now(),
            neighbors_comparison=neighbors_comparison,
            similar_comparison=similar_comparison[:5],  # Top 5
            national_average=national_average,
            strengths=strengths,
            weaknesses=weaknesses,
            rank_in_group=rank,
            group_size=len(all_in_group),
            comparison_group=group,
        )

    async def _get_score(self, code: str) -> AttractivenessScore:
        """Get score from cache or compute."""
        if code not in self._score_cache:
            self._score_cache[code] = await self._scorer.score(code)
        return self._score_cache[code]

    def _determine_group(self, code: str) -> str:
        """Determine comparison group for territory."""
        if code in COMPARISON_GROUPS["idf"]:
            return "idf"
        elif code in COMPARISON_GROUPS["metropoles"]:
            return "metropoles"
        elif code in COMPARISON_GROUPS["aura"]:
            return "aura"
        elif code in COMPARISON_GROUPS["ouest"]:
            return "ouest"
        elif code in COMPARISON_GROUPS["sud_est"]:
            return "sud_est"
        else:
            return "metropoles"  # Default

    def _identify_strengths_weaknesses(
        self,
        territory: AttractivenessScore,
        comparators: dict[str, AttractivenessScore],
    ) -> tuple[list[StrengthWeakness], list[StrengthWeakness]]:
        """Identify relative strengths and weaknesses."""
        strengths = []
        weaknesses = []

        if not comparators:
            return strengths, weaknesses

        for axis in AttractiveAxis:
            territory_score = territory.axes[axis].score

            # Average of comparators
            comparator_scores = [s.axes[axis].score for s in comparators.values()]
            avg_comparators = (
                sum(comparator_scores) / len(comparator_scores) if comparator_scores else 50.0
            )

            delta = territory_score - avg_comparators
            delta_pct = (delta / avg_comparators * 100) if avg_comparators else 0

            sw = StrengthWeakness(
                axis=axis.value.replace("_", " ").title(),
                score_territory=territory_score,
                score_comparators=avg_comparators,
                delta=delta,
                delta_pct=delta_pct,
                is_strength=delta > 0,
            )

            # Significant difference threshold: 5 points
            if delta >= 5:
                strengths.append(sw)
            elif delta <= -5:
                weaknesses.append(sw)

        # Sort by absolute delta
        strengths.sort(key=lambda x: abs(x.delta), reverse=True)
        weaknesses.sort(key=lambda x: abs(x.delta), reverse=True)

        return strengths[:3], weaknesses[:3]  # Top 3 each

    async def rank_territories(
        self, codes: list[str], by_axis: AttractiveAxis | None = None
    ) -> list[tuple[str, float]]:
        """
        Rank territories by score.

        Args:
            codes: List of territory codes
            by_axis: Optional axis to rank by (default: global)

        Returns:
            List of (code, score) tuples sorted descending
        """
        # Score all in parallel
        tasks = [self._get_score(code) for code in codes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        rankings = []
        for code, result in zip(codes, results, strict=False):
            if isinstance(result, AttractivenessScore):
                if by_axis:
                    score = result.axes[by_axis].score
                else:
                    score = result.global_score
                rankings.append((code, score))

        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings
