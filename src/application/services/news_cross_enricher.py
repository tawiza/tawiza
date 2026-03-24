"""Cross-enrichment: bridge news focal points with the relation graph.

When a focal point matches a known actor, creates an 'inferred' relation
with subtype 'mentioned_in_news' linking the actor to its territory.
This enriches the knowledge graph with real-time news signals.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from loguru import logger

from src.application.services._db_pool import acquire_conn


async def enrich_relations_from_focal_points(
    focal_points: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create relations for focal points that match known actors.

    For each focal point with a matched actor:
    1. Find the actor's territory (department)
    2. Find or create a territory actor for that department
    3. Create a 'mentioned_in_news' relation: actor → territory

    Returns:
        Stats dict with counts of created/skipped relations
    """
    if not focal_points:
        return {"created": 0, "skipped": 0}

    created = 0
    skipped = 0

    async with acquire_conn() as conn:
        for fp in focal_points:
            if not fp.get("is_known_actor") or not fp.get("actor"):
                continue

            # Only create relations for high-confidence focal points
            if fp.get("score", 0) < 40:
                skipped += 1
                continue

            actor = fp["actor"]
            actor_id = actor.get("actor_id")
            actor_name = actor.get("actor_name", "")
            department = actor.get("department")

            # Verify the entity name actually matches the actor name
            # (ILIKE %name% can produce false positives like "iran" in "miranda")
            if not _is_genuine_match(fp["entity"], actor_name):
                skipped += 1
                continue

            if not actor_id or not department:
                skipped += 1
                continue

            # Find the territory actor for this department
            territory_row = await conn.fetchrow(
                """
                SELECT id FROM actors
                WHERE type = 'territory' AND department_code = $1
                LIMIT 1
                """,
                department,
            )

            if not territory_row:
                skipped += 1
                continue

            territory_id = territory_row["id"]
            actor_uuid = uuid.UUID(actor_id)

            # Build evidence from focal point data
            evidence = {
                "focal_entity": fp["entity"],
                "score": fp["score"],
                "source_count": fp["source_count"],
                "mention_count": fp["mention_count"],
                "sources": fp.get("sources", [])[:5],
                "detected_at": datetime.utcnow().isoformat(),
                "top_article": (fp["articles"][0]["title"] if fp.get("articles") else None),
            }

            # Confidence based on focal point score (normalized 0-1)
            confidence = min(fp["score"] / 100.0, 1.0)

            # Check for existing recent relation to avoid duplicates
            existing = await conn.fetchval(
                """
                SELECT id FROM relations
                WHERE source_actor_id = $1 AND target_actor_id = $2
                  AND subtype = 'mentioned_in_news'
                  AND detected_at > NOW() - INTERVAL '24 hours'
                """,
                actor_uuid,
                territory_id,
            )

            if existing:
                # Update confidence if higher
                await conn.execute(
                    """
                    UPDATE relations
                    SET confidence = GREATEST(confidence, $1),
                        evidence = evidence || $2::jsonb
                    WHERE id = $3
                    """,
                    confidence,
                    _json(evidence),
                    existing,
                )
                skipped += 1
                continue

            # Create new relation
            rel_id = uuid.uuid4()
            try:
                await conn.execute(
                    """
                    INSERT INTO relations
                        (id, source_actor_id, target_actor_id, relation_type,
                         subtype, confidence, weight, evidence)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, 'inferred'::relation_type,
                            'mentioned_in_news', $4, $5, $6::jsonb)
                    """,
                    rel_id,
                    actor_uuid,
                    territory_id,
                    confidence,
                    float(fp["source_count"]),
                    _json(evidence),
                )

                # Track source provenance
                await conn.execute(
                    """
                    INSERT INTO relation_sources
                        (relation_id, source_type, source_ref, contributed_confidence)
                    VALUES ($1::uuid, 'news'::source_type, $2, $3)
                    ON CONFLICT DO NOTHING
                    """,
                    rel_id,
                    f"focal:{fp['entity']}",
                    confidence,
                )

                created += 1
                logger.info(
                    f"[cross-enrich] Created mentioned_in_news: "
                    f"{actor['actor_name']} → dept {department} "
                    f"(score={fp['score']}, conf={confidence:.2f})"
                )

            except Exception:
                logger.exception(f"[cross-enrich] Failed to create relation for {fp['entity']}")
                skipped += 1

    logger.info(f"[cross-enrich] Done: {created} created, {skipped} skipped")
    return {"created": created, "skipped": skipped}


def _is_genuine_match(entity: str, actor_name: str) -> bool:
    """Check if entity genuinely matches the actor name (word boundary matching).

    Prevents false positives like 'Iran' matching 'Miranda' or 'Cuba' matching 'Incubateur'.
    """
    import re

    entity_lower = entity.lower().strip()
    name_lower = actor_name.lower().strip()

    # Direct containment with word boundaries
    pattern = r"\b" + re.escape(entity_lower) + r"\b"
    if re.search(pattern, name_lower):
        return True

    # Reverse: actor name word in entity
    # Split actor name into significant words (>3 chars)
    name_words = [w for w in re.split(r"\W+", name_lower) if len(w) > 3]
    return any(re.search(r"\b" + re.escape(word) + r"\b", entity_lower) for word in name_words)


def _json(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, default=str)
