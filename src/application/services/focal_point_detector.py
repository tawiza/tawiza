"""Focal Point Detection  -  cross-reference news with territorial actors.

Inspired by World Monitor's Focal Point Detection pattern.
Detects convergence when multiple sources report on the same entity.

Algorithm:
    1. Extract entities (ORG, LOC, PER) from news titles via NER
    2. Match entities against known actors in the relation graph
    3. Score focal points by convergence (# sources, # mentions, recency)
    4. Return ranked focal points with supporting evidence
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from src.application.services._db_pool import acquire_conn


class FocalPointDetector:
    """Detects entities that appear across multiple news sources.

    A "focal point" is an actor (enterprise, institution, territory)
    that appears in multiple independent news articles within a time window.
    High convergence = something significant is happening.
    """

    # Minimum mentions across distinct sources to qualify as focal point
    MIN_SOURCES = 2
    # Time window for convergence detection
    DEFAULT_HOURS = 48
    # Known noise entities to skip
    NOISE_ENTITIES = {
        "France",
        "Paris",
        "Europe",
        "UE",
        "Union européenne",
        "Le Monde",
        "Les Echos",
        "AFP",
        "Reuters",
        "BFM",
        "Gouvernement",
        "Assemblée nationale",
        "Sénat",
        # NER noise (partial words, punctuation artifacts)
        "qu'",
        "l'",
        "d'",
        "n'",
        "s'",
        "c'",
        "j'",
        "La",
        "Le",
        "Les",
        "Des",
        "Une",
        "Un",
    }

    async def detect(
        self,
        department_code: str | None = None,
        hours: int | None = None,
        min_sources: int | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Detect focal points from recent news articles.

        Args:
            department_code: Optional filter by department
            hours: Time window (default 48h)
            min_sources: Minimum distinct sources (default 2)
            limit: Max focal points to return

        Returns:
            Ranked list of focal points with evidence
        """
        hours = hours or self.DEFAULT_HOURS
        min_src = min_sources or self.MIN_SOURCES
        since = datetime.utcnow() - timedelta(hours=hours)

        # 1. Fetch recent articles from DB
        articles = await self._fetch_articles(since, department_code)
        if not articles:
            return []

        logger.info(f"[focal] Analyzing {len(articles)} articles for focal points")

        # 2. Extract entities from titles
        entity_mentions = self._extract_mentions(articles)

        # 3. Match against known actors
        actor_matches = await self._match_actors(entity_mentions, department_code)

        # 4. Score and rank focal points
        focal_points = self._score_focal_points(entity_mentions, actor_matches, min_src)

        # 5. Sort by score descending
        focal_points.sort(key=lambda fp: fp["score"], reverse=True)

        return focal_points[:limit]

    async def _fetch_articles(self, since: datetime, department_code: str | None) -> list[dict]:
        """Fetch recent news articles from database."""
        async with acquire_conn() as conn:
            query = """
                SELECT id, title, url, source, feed_name, feed_category,
                       published_at, domain, tags, regions
                FROM news
                WHERE created_at >= $1
            """
            params: list[Any] = [since]

            if department_code:
                query += " AND ($2 = ANY(regions) OR regions IS NULL)"
                params.append(department_code)

            query += " ORDER BY published_at DESC NULLS LAST LIMIT 500"
            rows = await conn.fetch(query, *params)

        return [dict(r) for r in rows]

    def _extract_mentions(self, articles: list[dict]) -> dict[str, list[dict]]:
        """Extract entity mentions from article titles.

        Returns:
            Dict mapping entity_name → list of article references
        """
        mentions: dict[str, list[dict]] = defaultdict(list)

        # Try NER first, fall back to regex
        nlp = self._get_nlp()

        for article in articles:
            title = article.get("title", "")
            entities = set()

            if nlp:
                # spaCy NER extraction
                ner_entities = nlp.extract_entities(title)
                for label in ("ORG", "LOC", "GPE", "PER"):
                    for ent in ner_entities.get(label, []):
                        if (
                            len(ent) > 3
                            and ent not in self.NOISE_ENTITIES
                            and not ent.endswith("'")
                        ):
                            entities.add(ent)
            else:
                # Regex fallback: extract capitalized multi-word phrases
                for match in re.finditer(r"\b([A-Z][a-zéèêë]+(?:\s+[A-Z][a-zéèêë]+)+)\b", title):
                    entity = match.group(1)
                    if entity not in self.NOISE_ENTITIES and len(entity) > 3:
                        entities.add(entity)

                # Also extract quoted names
                for match in re.finditer(r'"([^"]+)"', title):
                    entities.add(match.group(1))

            ref = {
                "id": article.get("id"),
                "title": title,
                "url": article.get("url"),
                "source": article.get("source"),
                "feed": article.get("feed_name"),
                "published_at": (
                    article["published_at"].isoformat() if article.get("published_at") else None
                ),
            }

            for entity in entities:
                mentions[entity].append(ref)

        return dict(mentions)

    async def _match_actors(
        self,
        entity_mentions: dict[str, list[dict]],
        department_code: str | None,
    ) -> dict[str, dict]:
        """Match entity names against known actors in the relation graph.

        Returns:
            Dict mapping entity_name → actor record (if found)
        """
        if not entity_mentions:
            return {}

        # Build ILIKE patterns for batch matching
        entity_names = list(entity_mentions.keys())
        matches: dict[str, dict] = {}

        async with acquire_conn() as conn:
            for name in entity_names[:100]:  # Limit to avoid huge queries
                query = """
                    SELECT id, type, external_id, name, department_code, metadata
                    FROM actors
                    WHERE name ILIKE $1
                """
                params: list[Any] = [f"%{name}%"]

                if department_code:
                    query += " AND (department_code = $2 OR department_code IS NULL)"
                    params.append(department_code)

                query += " LIMIT 3"
                rows = await conn.fetch(query, *params)

                if rows:
                    best = rows[0]
                    matches[name] = {
                        "actor_id": str(best["id"]),
                        "actor_type": best["type"],
                        "actor_name": best["name"],
                        "external_id": best["external_id"],
                        "department": best["department_code"],
                    }

        logger.info(f"[focal] Matched {len(matches)}/{len(entity_names)} entities to actors")
        return matches

    def _score_focal_points(
        self,
        entity_mentions: dict[str, list[dict]],
        actor_matches: dict[str, dict],
        min_sources: int,
    ) -> list[dict[str, Any]]:
        """Score and filter focal points.

        Score formula:
            score = source_count * 10 + mention_count * 3 + actor_bonus
            actor_bonus = 20 if matched to known actor
        """
        focal_points = []

        for entity, refs in entity_mentions.items():
            # Count distinct sources
            sources = set()
            for ref in refs:
                source_id = ref.get("feed") or ref.get("source") or "unknown"
                sources.add(source_id)

            if len(sources) < min_sources:
                continue

            # Calculate score
            source_count = len(sources)
            mention_count = len(refs)
            actor_match = actor_matches.get(entity)
            actor_bonus = 20 if actor_match else 0

            score = source_count * 10 + mention_count * 3 + actor_bonus

            fp = {
                "entity": entity,
                "score": score,
                "source_count": source_count,
                "mention_count": mention_count,
                "sources": sorted(sources),
                "articles": refs[:5],  # Top 5 articles as evidence
                "is_known_actor": actor_match is not None,
            }
            if actor_match:
                fp["actor"] = actor_match

            focal_points.append(fp)

        return focal_points

    def _get_nlp(self):
        """Lazy-load NLP instance."""
        if not hasattr(self, "_nlp_instance"):
            try:
                from src.collector.processing.nlp import FrenchNLP

                self._nlp_instance = FrenchNLP()
            except Exception:
                logger.warning("[focal] spaCy NLP not available, using regex fallback")
                self._nlp_instance = None
        return self._nlp_instance


# Global singleton
focal_detector = FocalPointDetector()
