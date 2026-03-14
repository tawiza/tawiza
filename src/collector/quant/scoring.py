"""Composite territorial health scoring system.

Combines alpha factors into a single territorial health score per department.
Uses z-score normalization and equal weighting initially.
"""

import os
from statistics import mean, stdev
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from .factors import compute_normalized_factors


class TerritorialScorer:
    """Territorial health scoring system."""

    def __init__(self, factors_data: dict[str, dict[str, float | None]]):
        """Initialize with factors data.

        Args:
            factors_data: Dict mapping dept -> factor_name -> value
        """
        self.factors_data = factors_data
        self.factor_names = [
            "factor_sante_entreprises",
            "factor_tension_emploi",
            "factor_dynamisme_immo",
            "factor_construction",
            "factor_declin_ratio",
            "factor_presse_sentiment",
        ]

    def compute_z_scores(self) -> dict[str, dict[str, float | None]]:
        """Compute z-scores for each factor across all departments.

        Returns:
            Dict mapping dept -> factor_name -> z_score
        """
        logger.info("Computing z-scores for all factors")

        z_scores = {}

        # For each factor, collect all non-null values across departments
        for factor_name in self.factor_names:
            values = []
            dept_values = {}

            # Collect non-null values
            for dept, factors in self.factors_data.items():
                value = factors.get(factor_name)
                if value is not None:
                    values.append(value)
                    dept_values[dept] = value

            if len(values) < 2:
                logger.warning(
                    f"Not enough data for z-score calculation of {factor_name}: {len(values)} values"
                )
                # Set all z-scores to None for this factor
                for dept in self.factors_data:
                    if dept not in z_scores:
                        z_scores[dept] = {}
                    z_scores[dept][factor_name] = None
                continue

            # Calculate mean and standard deviation
            factor_mean = mean(values)
            factor_std = stdev(values) if len(values) > 1 else 1.0

            if factor_std == 0:
                factor_std = 1.0  # Avoid division by zero

            logger.debug(
                f"Factor {factor_name}: mean={factor_mean:.3f}, std={factor_std:.3f}, n={len(values)}"
            )

            # Calculate z-scores for each department
            for dept in self.factors_data:
                if dept not in z_scores:
                    z_scores[dept] = {}

                if dept in dept_values:
                    z_score = (dept_values[dept] - factor_mean) / factor_std
                    z_scores[dept][factor_name] = z_score
                else:
                    z_scores[dept][factor_name] = None

        return z_scores

    def compute_composite_scores(self) -> dict[str, dict[str, any]]:
        """Compute composite territorial health scores.

        Returns:
            Dict mapping dept -> {composite_score, factor_count, individual_scores}
        """
        logger.info("Computing composite territorial health scores")

        # Get z-scores
        z_scores = self.compute_z_scores()

        composite_scores = {}

        for dept, factor_zscores in z_scores.items():
            # Collect valid z-scores
            valid_scores = []
            individual_scores = {}

            for factor_name, z_score in factor_zscores.items():
                if z_score is not None:
                    # Invert decline ratio (higher decline = lower score)
                    if factor_name == "factor_declin_ratio":
                        adjusted_score = -z_score
                    else:
                        adjusted_score = z_score

                    valid_scores.append(adjusted_score)
                    individual_scores[factor_name] = {
                        "z_score": z_score,
                        "adjusted_score": adjusted_score,
                        "raw_value": self.factors_data[dept].get(factor_name),
                    }
                else:
                    individual_scores[factor_name] = {
                        "z_score": None,
                        "adjusted_score": None,
                        "raw_value": None,
                    }

            # Calculate composite score (equal weighting)
            if valid_scores:
                # Average of z-scores
                raw_composite = mean(valid_scores)

                # Transform to 0-100 scale (50 = average, std dev ≈ 15)
                # Z-score of 0 -> 50, Z-score of +2 -> 80, Z-score of -2 -> 20
                composite_score = 50 + (raw_composite * 15)

                # Clamp to 0-100 range
                composite_score = max(0, min(100, composite_score))
            else:
                composite_score = None
                raw_composite = None

            composite_scores[dept] = {
                "composite_score": composite_score,
                "raw_composite": raw_composite,
                "factor_count": len(valid_scores),
                "total_factors": len(self.factor_names),
                "individual_scores": individual_scores,
                "confidence": len(valid_scores) / len(self.factor_names),
            }

        return composite_scores

    def get_department_ranking(self) -> list[tuple[str, float, int]]:
        """Get departments ranked by composite score.

        Returns:
            List of tuples (dept_code, composite_score, factor_count)
        """
        scores = self.compute_composite_scores()

        # Filter departments with valid scores and sort by score
        ranked = [
            (dept, data["composite_score"], data["factor_count"])
            for dept, data in scores.items()
            if data["composite_score"] is not None
        ]

        # Sort by composite score (descending)
        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked

    def get_health_category(self, composite_score: float) -> str:
        """Categorize territorial health based on composite score.

        Args:
            composite_score: Score from 0-100

        Returns:
            Health category string
        """
        if composite_score >= 70:
            return "Healthy"
        elif composite_score >= 55:
            return "Above Average"
        elif composite_score >= 45:
            return "Average"
        elif composite_score >= 30:
            return "Below Average"
        else:
            return "Distress"


async def compute_territorial_scores(database_url: str) -> dict[str, dict[str, any]]:
    """Main function to compute territorial health scores.

    Args:
        database_url: PostgreSQL connection URL

    Returns:
        Dict mapping department -> score data
    """
    logger.info("Computing territorial health scores")

    # Get normalized factors
    factors_data = await compute_normalized_factors(database_url)

    # Create scorer and compute composite scores
    scorer = TerritorialScorer(factors_data)
    scores = scorer.compute_composite_scores()

    # Add health categories
    for dept, data in scores.items():
        if data["composite_score"] is not None:
            data["health_category"] = scorer.get_health_category(data["composite_score"])
        else:
            data["health_category"] = "Unknown"

    logger.info(f"Computed territorial scores for {len(scores)} departments")

    return scores


async def get_department_rankings(database_url: str) -> list[dict[str, any]]:
    """Get ranked list of departments by territorial health.

    Args:
        database_url: PostgreSQL connection URL

    Returns:
        List of department data sorted by composite score
    """
    scores = await compute_territorial_scores(database_url)
    scorer = TerritorialScorer({})  # Just for categorization

    # Convert to ranked list
    ranked = []
    for dept, data in scores.items():
        if data["composite_score"] is not None:
            ranked.append(
                {
                    "department": dept,
                    "composite_score": data["composite_score"],
                    "health_category": data["health_category"],
                    "factor_count": data["factor_count"],
                    "confidence": data["confidence"],
                    "individual_scores": data["individual_scores"],
                }
            )

    # Sort by composite score (descending)
    ranked.sort(key=lambda x: x["composite_score"], reverse=True)

    return ranked


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) > 1:
        database_url = sys.argv[1]
    else:
        database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost:5433/tawiza")

    # Test the scoring system
    scores = asyncio.run(compute_territorial_scores(database_url))

    # Show top 10 departments
    ranked = [
        (dept, data["composite_score"], data["health_category"])
        for dept, data in scores.items()
        if data["composite_score"] is not None
    ]
    ranked.sort(key=lambda x: x[1], reverse=True)

    print("Top 10 departments by territorial health score:")
    print("-" * 50)
    for i, (dept, score, category) in enumerate(ranked[:10], 1):
        print(f"{i:2d}. {dept}: {score:.1f} ({category})")

    print("\nBottom 5 departments:")
    print("-" * 50)
    for i, (dept, score, category) in enumerate(ranked[-5:], len(ranked) - 4):
        print(f"{i:2d}. {dept}: {score:.1f} ({category})")

    print(f"\nTotal departments with scores: {len(ranked)}")
    avg_score = mean([score for _, score, _ in ranked])
    print(f"Average territorial health score: {avg_score:.1f}")
