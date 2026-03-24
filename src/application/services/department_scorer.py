"""Department Health Index — adapted from World Monitor's Country Instability Index.

Scores French departments on a 0-100 scale using multiple data signals:

Formula (adapted from World Monitor):
    score = min(100, max(floor, baseline * 0.4 + event_score * 0.6 + boosts))

Components:
    - baseline (40%): structural indicators (enterprise density, employment, finances)
    - event_score (60%): recent events (BODACC, news volume, spikes)
    - boosts: exceptional events (major closures, spikes)

Higher score = more economic activity/dynamism (NOT instability).
We invert the World Monitor logic: high = good for territorial attractiveness.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from src.application.services._db_pool import acquire_conn
from src.infrastructure.datasources.spike_detector import spike_detector


class DepartmentScorer:
    """Computes a health index (0-100) for French departments.

    Combines structural data from the relations graph with
    real-time signals from news and BODACC events.
    """

    # Floor: no department scores below this
    FLOOR = 15
    # Weights
    W_BASELINE = 0.4
    W_EVENTS = 0.6

    async def score(self, department_code: str) -> dict[str, Any]:
        """Compute the health index for a department.

        Returns:
            Dict with overall score and component breakdown
        """
        baseline = await self._compute_baseline(department_code)
        events = await self._compute_events(department_code)
        boosts = self._compute_boosts(department_code)

        raw = (
            baseline["score"] * self.W_BASELINE + events["score"] * self.W_EVENTS + boosts["total"]
        )
        final = min(100, max(self.FLOOR, math.floor(raw)))

        return {
            "department": department_code,
            "score": final,
            "grade": self._grade(final),
            "computed_at": datetime.utcnow().isoformat(),
            "components": {
                "baseline": baseline,
                "events": events,
                "boosts": boosts,
            },
        }

    async def score_all(self, department_codes: list[str] | None = None) -> list[dict]:
        """Score multiple departments.

        Args:
            department_codes: List of codes, or None for all departments with data
        """
        if not department_codes:
            department_codes = await self._get_active_departments()

        results = []
        for code in department_codes:
            try:
                result = await self.score(code)
                results.append(result)
            except Exception as e:
                logger.warning(f"[scorer] Failed to score dept {code}: {e}")
                results.append(
                    {
                        "department": code,
                        "score": self.FLOOR,
                        "grade": "F",
                        "error": str(e),
                    }
                )

        results.sort(key=lambda r: r.get("score", 0), reverse=True)
        return results

    async def _compute_baseline(self, dept: str) -> dict:
        """Baseline score from structural indicators (0-100).

        Components:
        - enterprise_density: actors per 10k population (approx)
        - actor_diversity: how many different actor types
        - relation_density: relations per actor (connectivity)
        """
        async with acquire_conn() as conn:
            # Count actors
            actor_count = (
                await conn.fetchval("SELECT COUNT(*) FROM actors WHERE department_code = $1", dept)
                or 0
            )

            # Count actor types
            type_count = (
                await conn.fetchval(
                    "SELECT COUNT(DISTINCT type) FROM actors WHERE department_code = $1", dept
                )
                or 0
            )

            # Count relations involving this department's actors
            relation_count = (
                await conn.fetchval(
                    """
                SELECT COUNT(*) FROM relations r
                JOIN actors a1 ON r.source_actor_id = a1.id
                WHERE a1.department_code = $1
            """,
                    dept,
                )
                or 0
            )

        # Normalize to 0-100 scale
        # enterprise_density: 100+ actors = 30pts, 500+ = 60pts, 1000+ = 80pts
        density_score = min(80, (actor_count / 1000) * 80) if actor_count > 0 else 0

        # diversity: 1 type = 10pts, 4+ types = 40pts, 7 = 70pts
        diversity_score = min(70, type_count * 10)

        # connectivity: relations / actors ratio, capped
        connectivity = (relation_count / max(actor_count, 1)) * 20
        connectivity_score = min(50, connectivity)

        # Weighted combination
        score = density_score * 0.4 + diversity_score * 0.3 + connectivity_score * 0.3

        return {
            "score": round(min(100, score), 1),
            "actor_count": actor_count,
            "type_count": type_count,
            "relation_count": relation_count,
            "density_score": round(density_score, 1),
            "diversity_score": round(diversity_score, 1),
            "connectivity_score": round(connectivity_score, 1),
        }

    async def _compute_events(self, dept: str) -> dict:
        """Event score from recent activity (0-100).

        Components:
        - news_volume: articles mentioning this dept in last 48h
        - bodacc_activity: recent BODACC announcements
        - news_freshness: how recent is the latest article
        """
        since_48h = datetime.utcnow() - timedelta(hours=48)
        since_7d = datetime.utcnow() - timedelta(days=7)

        async with acquire_conn() as conn:
            # News volume (48h)
            news_48h = (
                await conn.fetchval(
                    """
                SELECT COUNT(*) FROM news
                WHERE created_at >= $1
                AND ($2 = ANY(regions) OR feed_category IN ('eco_regional'))
            """,
                    since_48h,
                    dept,
                )
                or 0
            )

            # News volume (7d) for baseline
            news_7d = (
                await conn.fetchval(
                    """
                SELECT COUNT(*) FROM news
                WHERE created_at >= $1
                AND ($2 = ANY(regions) OR feed_category IN ('eco_regional'))
            """,
                    since_7d,
                    dept,
                )
                or 0
            )

            # BODACC events (7d) — from relation sources
            bodacc_count = 0
            try:
                bodacc_count = (
                    await conn.fetchval(
                        """
                    SELECT COUNT(*) FROM relation_sources rs
                    JOIN relations r ON rs.relation_id = r.id
                    JOIN actors a ON r.source_actor_id = a.id
                    WHERE a.department_code = $1
                    AND rs.source_type = 'bodacc'
                    AND rs.observed_at >= $2
                """,
                        dept,
                        since_7d,
                    )
                    or 0
                )
            except Exception:
                pass  # relation_sources may not exist

        # Score components
        # news_volume: 0-20 articles → 0-50pts, 20+ → up to 80pts
        news_score = min(80, news_48h * 4) if news_48h > 0 else 0

        # BODACC activity: 0-10 events → 0-30pts
        bodacc_score = min(30, bodacc_count * 3)

        # News acceleration: 48h vs 7d average
        daily_avg_7d = news_7d / 7 if news_7d > 0 else 0
        daily_48h = news_48h / 2
        acceleration = daily_48h / max(daily_avg_7d, 0.1)
        accel_score = min(20, (acceleration - 1) * 10) if acceleration > 1 else 0

        score = news_score * 0.5 + bodacc_score * 0.3 + accel_score * 0.2

        return {
            "score": round(min(100, score), 1),
            "news_48h": news_48h,
            "news_7d": news_7d,
            "bodacc_7d": bodacc_count,
            "acceleration": round(acceleration, 2),
            "news_score": round(news_score, 1),
            "bodacc_score": round(bodacc_score, 1),
            "accel_score": round(accel_score, 1),
        }

    def _compute_boosts(self, dept: str) -> dict:
        """Boost/penalty from exceptional events.

        Checks spike detector for department-related streams.
        """
        total = 0.0
        details = []

        # Check news spikes for this department
        stream_name = f"news_{dept}"
        stats = spike_detector.get_stream_stats(stream_name)
        if stats and stats.get("z_score", 0) >= 2.0:
            boost = min(15, stats["z_score"] * 5)
            total += boost
            details.append(
                {
                    "type": "news_spike",
                    "stream": stream_name,
                    "z_score": stats["z_score"],
                    "boost": round(boost, 1),
                }
            )

        # Check category spikes
        for cat in ("eco_regional", "eco_national", "startups", "industry"):
            cat_stream = f"news_{cat}"
            cat_stats = spike_detector.get_stream_stats(cat_stream)
            if cat_stats and cat_stats.get("z_score", 0) >= 3.0:
                boost = min(10, cat_stats["z_score"] * 3)
                total += boost
                details.append(
                    {
                        "type": "category_spike",
                        "stream": cat_stream,
                        "z_score": cat_stats["z_score"],
                        "boost": round(boost, 1),
                    }
                )

        return {
            "total": round(min(25, total), 1),  # Cap boosts at 25
            "details": details,
        }

    async def _get_active_departments(self) -> list[str]:
        """Get department codes that have actors in the graph."""
        async with acquire_conn() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT department_code
                FROM actors
                WHERE department_code IS NOT NULL
                ORDER BY department_code
            """)
        return [r["department_code"] for r in rows]

    @staticmethod
    def _grade(score: int) -> str:
        """Convert numeric score to letter grade."""
        if score >= 80:
            return "A"
        elif score >= 65:
            return "B"
        elif score >= 50:
            return "C"
        elif score >= 35:
            return "D"
        return "F"


# Global singleton
department_scorer = DepartmentScorer()
