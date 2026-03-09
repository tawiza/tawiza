"""RelationService -- orchestration layer for actor/relation discovery.

Provides four public async methods:

* **discover(department_code, sources)** -- run extractors, UPSERT results
* **get_graph(department_code, min_confidence, actor_types)** -- D3.js payload
* **get_coverage(department_code)** -- relation breakdown by type + coverage score
* **get_gaps(department_code)** -- detect missing data and capability gaps
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg
from loguru import logger

from src.application.services._db_pool import acquire_conn
from src.application.services.relation_extractors import EXTRACTORS
from src.application.services.relation_inferrers import INFERRERS
from src.application.services.relation_predictors import PREDICTORS, simulate_whatif
from src.infrastructure.caching.redis_cache import get_redis_cache

# ---------------------------------------------------------------------------
# Capability matrix -- what we CAN vs. CANNOT detect today
# ---------------------------------------------------------------------------

CAPABILITY_MATRIX: list[dict[str, Any]] = [
    {
        "capability": "Localisation entreprise",
        "level": 7,
        "missing": "Rien, SIRENE suffit",
        "source": "SIRENE (L1)",
        "method": "Extraction directe",
    },
    {
        "capability": "Secteur d'activite",
        "level": 7,
        "missing": "Sous-traitance invisible",
        "source": "SIRENE (L1)",
        "method": "Code NAF",
    },
    {
        "capability": "Concentration sectorielle",
        "level": 5,
        "missing": "Pas de benchmark national",
        "source": "Infereur L2",
        "method": "Part statistique > 10%",
    },
    {
        "capability": "Poids dans l'emploi",
        "level": 5,
        "missing": "Tranches, pas effectifs exacts",
        "source": "Infereur L2",
        "method": "Estimation tranche_effectif INSEE",
    },
    {
        "capability": "Clusters geographiques",
        "level": 4,
        "missing": "Granularite code postal seulement",
        "source": "Infereur L2",
        "method": "Groupement NAF + code postal",
    },
    {
        "capability": "Evenements juridiques",
        "level": 6,
        "missing": "Delai publication BODACC",
        "source": "BODACC (L1)",
        "method": "Extraction annonces",
    },
    {
        "capability": "Marches publics attribues",
        "level": 6,
        "missing": "Titulaire parfois absent ou anonymise, montants non disponibles",
        "source": "BOAMP (L1)",
        "method": "Extraction avis d'attribution BOAMP (acheteur -> titulaire)",
    },
    {
        "capability": "Activite associative territoriale",
        "level": 6,
        "missing": "Echantillon 100/dept, objet associatif non disponible via API",
        "source": "RNA (L1)",
        "method": "API recherche-entreprises (NJ codes 92xx, associations actives)",
    },
    {
        "capability": "Subventions publiques territoriales",
        "level": 5,
        "missing": "Montants et beneficiaires individuels non disponibles, recherche par nom de departement",
        "source": "Subventions data.gouv.fr (L1)",
        "method": "API data.gouv.fr datasets (financeurs publics -> territoire)",
    },
    {
        "capability": "Liens dirigeants",
        "level": 4,
        "missing": "Limite aux noms de personnes BODACC (commercant format NOM, Prenom + listepersonnes)",
        "source": "Infereur L2 (DirectorLinkInferrer)",
        "method": "Correspondance noms normalises dans signaux BODACC (shared_director)",
    },
    {
        "capability": "Chaine fournisseurs",
        "level": 3,
        "missing": "Inference CPV seulement, pas de donnees fournisseurs reelles",
        "source": "Infereur L2 (SupplyChainInferrer)",
        "method": "Compatibilite codes CPV marches publics (BOAMP)",
    },
    {
        "capability": "Impact defaillance",
        "level": 3,
        "missing": "Modele simplifie, pas de donnees fournisseurs",
        "source": "Predicteur L3",
        "method": "cascade_risk + territorial_impact",
    },
    {
        "capability": "Lien institutions",
        "level": 4,
        "missing": "Subventions partielles (datasets, pas beneficiaires individuels), marches publics via BOAMP",
        "source": "SIRENE NJ + BOAMP + Subventions + Predicteur L3",
        "method": "nature_juridique (codes 71-74) + BOAMP attribution + subventions data.gouv + likely_institution",
    },
    {
        "capability": "Effet domino territorial",
        "level": 2,
        "missing": "Estimation par tranche, pas d'impact reel mesure",
        "source": "Predicteur L3",
        "method": "territorial_impact score composite",
    },
    {
        "capability": "Detection associations",
        "level": 7,
        "missing": "Echantillon limite a 100 associations par departement",
        "source": "RNA (L1) + SIRENE NJ (L1)",
        "method": "API recherche-entreprises (NJ 92xx) + nature_juridique reclassification",
    },
    {
        "capability": "Detection organismes de formation",
        "level": 4,
        "missing": "Pas de verification Qualiopi/DataDock",
        "source": "SIRENE NJ (L1)",
        "method": "nature_juridique codes 73xx/85xx",
    },
    {
        "capability": "Detection acteurs financiers",
        "level": 4,
        "missing": "Pas de distinction banque de detail vs. investissement",
        "source": "SIRENE NJ (L1)",
        "method": "nature_juridique codes 64xx-66xx",
    },
    {
        "capability": "Liens sociaux association-secteur",
        "level": 3,
        "missing": "Infere par NAF, pas par activite reelle de l'association",
        "source": "Infereur L2",
        "method": "social_link + social_proximity",
    },
    {
        "capability": "Liens financiers banque-entreprise",
        "level": 3,
        "missing": "Taille != relation bancaire, pas de donnees reelles",
        "source": "Infereur L2",
        "method": "likely_finances (taille entreprise >= 15)",
    },
    {
        "capability": "Liens formation-emploi",
        "level": 3,
        "missing": "Demande sectorielle inferee, pas l'offre de formation reelle",
        "source": "Infereur L2",
        "method": "trains_sector + likely_trains",
    },
    {
        "capability": "Proximite geographique",
        "level": 4,
        "missing": "Geocodage BAN limite a 50 acteurs/dept, adresses parfois incompletes",
        "source": "Infereur L2 (ProximityInferrer)",
        "method": "Geocodage BAN + distance Haversine < 500m",
    },
]

# Node sizes by actor type (for D3.js rendering)
_NODE_SIZE: dict[str, float] = {
    "territory": 25.0,
    "institution": 20.0,
    "collectivity": 18.0,
    "competitiveness_pole": 17.0,
    "incubator": 16.0,
    "sector": 15.0,
    "financial": 14.0,
    "association": 12.0,
    "formation": 12.0,
    "enterprise": 10.0,
}


async def _cache_get(key: str) -> dict | None:
    try:
        cache = await get_redis_cache()
        return await cache.get(key)
    except Exception:
        logger.debug("Cache miss/error for {}", key)
        return None


async def _cache_set(key: str, value: dict, ttl: int = 600) -> None:
    try:
        cache = await get_redis_cache()
        await cache.set(key, value, ttl=ttl)
    except Exception:
        logger.debug("Cache set error for {}", key)


async def _cache_invalidate(department_code: str) -> None:
    try:
        cache = await get_redis_cache()
        for suffix in ("graph", "coverage", "gaps", "analytics", "analytics:timeline"):
            await cache.delete(f"relations:{department_code}:{suffix}")
        await cache.delete("relations:all:graph")
    except Exception:
        logger.debug("Cache invalidation error for dept {}", department_code)


class RelationService:
    """Stateless orchestration service for territorial relation graphs."""

    # ------------------------------------------------------------------
    # 1. discover -- run extractors and persist
    # ------------------------------------------------------------------

    async def discover(
        self,
        department_code: str,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run extractors (L1) then inferrers (L2) for *department_code*.

        Pipeline:
        1. Run L1 extractors → UPSERT actors & structural relations
        2. Run L2 inferrers → UPSERT inferred relations (query persisted data)
        3. Return summary counts

        Returns summary counts of actors and relations created/updated.
        """
        if sources is None:
            sources = [
                "sirene",
                "bodacc",
                "boamp",
                "rna",
                "subventions",
                "ademe",
                "qualiopi",
                "ofgl",
                "dvf",
                "france_travail",
                "insee_local",
                "nature_juridique",
                "epci",
                "incubator",
                "poles",
                "territorial",
                "sirene_enrich",
                "sirene_dirigeants",
                "urssaf",
            ]
        elif "nature_juridique" not in sources:
            # nature_juridique must run after sirene (needs existing actors)
            sources = list(sources) + ["nature_juridique"]

        # Separate sources that need persisted actors (post-persist extractors)
        # from those that can run first (pre-persist extractors).
        _POST_PERSIST_EXTRACTORS = {
            "nature_juridique",
            "territorial",
            "sirene_enrich",
            "sirene_dirigeants",
            "urssaf",
        }
        pre_sources = [s for s in sources if s not in _POST_PERSIST_EXTRACTORS]
        post_sources = [s for s in sources if s in _POST_PERSIST_EXTRACTORS]

        all_actors: list[dict[str, Any]] = []
        all_relations: list[dict[str, Any]] = []

        # -- Phase 1a: L1 Extractors (pre-persist: sirene, bodacc) --
        for src in pre_sources:
            extractor_cls = EXTRACTORS.get(src)
            if extractor_cls is None:
                logger.warning("Unknown extractor source: {}", src)
                continue

            extractor = extractor_cls()
            try:
                result = await extractor.extract(department_code)
                all_actors.extend(result.get("actors", []))
                all_relations.extend(result.get("relations", []))
            except Exception:
                logger.exception("Extractor {} failed for dept {}", src, department_code)

        # Persist L1a results (post-persist extractors need them in the DB)
        actors_upserted = 0
        relations_upserted = 0

        if all_actors:
            async with acquire_conn() as conn:
                actors_upserted = await self._upsert_actors(conn, all_actors)
                relations_upserted = await self._upsert_relations(conn, all_relations)

        # -- Phase 1b: L1 Extractors (post-persist: nature_juridique) --
        # These extractors read from the actors table and need Phase 1a data.
        for src in post_sources:
            extractor_cls = EXTRACTORS.get(src)
            if extractor_cls is None:
                logger.warning("Unknown extractor source: {}", src)
                continue

            extractor = extractor_cls()
            try:
                result = await extractor.extract(department_code)
                post_actors = result.get("actors", [])
                post_relations = result.get("relations", [])
                if post_actors or post_relations:
                    async with acquire_conn() as conn:
                        actors_upserted += await self._upsert_actors(conn, post_actors)
                        relations_upserted += await self._upsert_relations(conn, post_relations)
            except Exception:
                logger.exception("Extractor {} failed for dept {}", src, department_code)

        # -- Phase 2: L2 Inferrers (run on persisted data) --
        l2_actors: list[dict[str, Any]] = []
        l2_relations: list[dict[str, Any]] = []
        inferrers_run: list[str] = []

        for name, inferrer_cls in INFERRERS.items():
            inferrer = inferrer_cls()
            try:
                result = await inferrer.infer(department_code)
                l2_actors.extend(result.get("actors", []))
                l2_relations.extend(result.get("relations", []))
                inferrers_run.append(name)
            except Exception:
                logger.exception("Inferrer {} failed for dept {}", name, department_code)

        # Persist L2 results
        l2_actors_upserted = 0
        l2_relations_upserted = 0

        if l2_actors or l2_relations:
            async with acquire_conn() as conn:
                l2_actors_upserted = await self._upsert_actors(conn, l2_actors)
                l2_relations_upserted = await self._upsert_relations(conn, l2_relations)

        # -- Phase 3: L3 Predictors (hypothetical relations) --
        l3_actors: list[dict[str, Any]] = []
        l3_relations: list[dict[str, Any]] = []
        predictors_run: list[str] = []

        for name, predictor_cls in PREDICTORS.items():
            predictor = predictor_cls()
            try:
                result = await predictor.predict(department_code)
                l3_actors.extend(result.get("actors", []))
                l3_relations.extend(result.get("relations", []))
                predictors_run.append(name)
            except Exception:
                logger.exception("Predictor {} failed for dept {}", name, department_code)

        # Persist L3 results
        l3_actors_upserted = 0
        l3_relations_upserted = 0

        if l3_actors or l3_relations:
            async with acquire_conn() as conn:
                l3_actors_upserted = await self._upsert_actors(conn, l3_actors)
                l3_relations_upserted = await self._upsert_relations(conn, l3_relations)

        total_actors = actors_upserted + l2_actors_upserted + l3_actors_upserted
        total_relations = relations_upserted + l2_relations_upserted + l3_relations_upserted

        logger.info(
            "discover dept={}: L1={} actors + {} rels, L2={} actors + {} rels, L3={} actors + {} rels",
            department_code,
            actors_upserted,
            relations_upserted,
            l2_actors_upserted,
            l2_relations_upserted,
            l3_actors_upserted,
            l3_relations_upserted,
        )
        result = {
            "department_code": department_code,
            "actors_upserted": total_actors,
            "relations_upserted": total_relations,
            "l1_relations": relations_upserted,
            "l2_relations": l2_relations_upserted,
            "l3_relations": l3_relations_upserted,
            "sources_run": sources,
            "inferrers_run": inferrers_run,
            "predictors_run": predictors_run,
        }

        # -- Save timeline snapshot --
        try:
            from src.application.services.network_analytics_service import save_snapshot

            await save_snapshot(department_code, result)
        except Exception as e:
            logger.warning("Snapshot save failed for dept {}: {}", department_code, e)

        await _cache_invalidate(department_code)

        return result

    # ------------------------------------------------------------------
    # 2. get_graph -- D3.js force-graph payload
    # ------------------------------------------------------------------

    async def get_graph(
        self,
        department_code: str | None,
        min_confidence: float = 0.0,
        actor_types: list[str] | None = None,
        max_links: int = 1500,
    ) -> dict[str, Any]:
        """Build a D3.js-compatible graph payload.

        If *department_code* is ``None``, returns ALL actors across every
        department (cross-department view).  *max_links* caps edges
        returned (by confidence DESC) to keep the frontend responsive.

        Returns ``{"nodes": [...], "links": [...], "total_actors": N,
        "total_relations": N, "total_relations_unfiltered": N}``.
        """
        cache_key = None
        if min_confidence == 0.0 and not actor_types:
            cache_key = f"relations:{department_code or 'all'}:graph"
            cached = await _cache_get(cache_key)
            if cached is not None:
                return cached

        async with acquire_conn() as conn:
            # -- Fetch actors --
            if department_code is None:
                # Cross-department: all actors
                if actor_types:
                    actor_rows = await conn.fetch(
                        """
                        SELECT id, type::text, external_id, name, department_code, metadata
                        FROM actors
                        WHERE type::text = ANY($1)
                        ORDER BY name
                        """,
                        actor_types,
                    )
                else:
                    actor_rows = await conn.fetch(
                        """
                        SELECT id, type::text, external_id, name, department_code, metadata
                        FROM actors
                        ORDER BY name
                        """
                    )
            elif actor_types:
                actor_rows = await conn.fetch(
                    """
                    SELECT id, type::text, external_id, name, department_code, metadata
                    FROM actors
                    WHERE department_code = $1 OR department_code IS NULL
                    AND type::text = ANY($2)
                    ORDER BY name
                    """,
                    department_code,
                    actor_types,
                )
            else:
                actor_rows = await conn.fetch(
                    """
                    SELECT id, type::text, external_id, name, department_code, metadata
                    FROM actors
                    WHERE department_code = $1 OR department_code IS NULL
                    ORDER BY name
                    """,
                    department_code,
                )

            actor_ids = {row["id"] for row in actor_rows}
            actor_id_str_set = {str(row["id"]) for row in actor_rows}

            if not actor_ids:
                return {"nodes": [], "links": [], "total_actors": 0, "total_relations": 0}

            # -- Fetch relations where BOTH endpoints are in our actor set --
            actor_id_list = list(actor_ids)

            # Count total (unfiltered by max_links) for UI feedback
            total_unfiltered = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM relations r
                WHERE r.confidence >= $1
                  AND r.source_actor_id = ANY($2::uuid[])
                  AND r.target_actor_id = ANY($2::uuid[])
                """,
                min_confidence,
                actor_id_list,
            )

            relation_rows = await conn.fetch(
                """
                SELECT r.id, r.source_actor_id, r.target_actor_id,
                       r.relation_type::text, r.subtype, r.confidence, r.weight
                FROM relations r
                WHERE r.confidence >= $1
                  AND r.source_actor_id = ANY($2::uuid[])
                  AND r.target_actor_id = ANY($2::uuid[])
                ORDER BY r.confidence DESC
                LIMIT $3
                """,
                min_confidence,
                actor_id_list,
                max_links,
            )

            # -- Build nodes --
            nodes = []
            for row in actor_rows:
                actor_type = row["type"]
                meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
                nodes.append(
                    {
                        "id": str(row["id"]),
                        "label": row["name"],
                        "type": actor_type,
                        "external_id": row["external_id"],
                        "department_code": row["department_code"],
                        "size": _NODE_SIZE.get(actor_type, 10.0),
                        "metadata": meta,
                    }
                )

            # -- Build links --
            links = []
            for row in relation_rows:
                src = str(row["source_actor_id"])
                tgt = str(row["target_actor_id"])
                # Only include links whose both ends are in our node set
                if src in actor_id_str_set and tgt in actor_id_str_set:
                    links.append(
                        {
                            "source": src,
                            "target": tgt,
                            "relation_type": row["relation_type"],
                            "subtype": row["subtype"],
                            "confidence": float(row["confidence"]),
                            "weight": float(row["weight"] or 1.0),
                        }
                    )

            # Filter out isolated nodes (no visible edges)
            connected_ids: set[str] = set()
            for lnk in links:
                connected_ids.add(lnk["source"])
                connected_ids.add(lnk["target"])
            nodes = [n for n in nodes if n["id"] in connected_ids]

            result = {
                "nodes": nodes,
                "links": links,
                "total_actors": len(nodes),
                "total_relations": len(links),
                "total_relations_unfiltered": total_unfiltered,
            }

            if cache_key:
                await _cache_set(cache_key, result, ttl=600)

            return result

    # ------------------------------------------------------------------
    # 3. get_coverage -- relation breakdown
    # ------------------------------------------------------------------

    async def get_coverage(self, department_code: str) -> dict[str, Any]:
        """Count relations by type, compute structural/inferred/hypothetical %."""
        cache_key = f"relations:{department_code}:coverage"
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached

        async with acquire_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT r.relation_type::text AS rtype, COUNT(*) AS cnt
                FROM relations r
                JOIN actors a_src ON r.source_actor_id = a_src.id
                JOIN actors a_tgt ON r.target_actor_id = a_tgt.id
                WHERE a_src.department_code = $1 OR a_tgt.department_code = $1
                GROUP BY r.relation_type
                """,
                department_code,
            )

            counts = {row["rtype"]: row["cnt"] for row in rows}
            total = sum(counts.values())

            structural = counts.get("structural", 0)
            inferred = counts.get("inferred", 0)
            hypothetical = counts.get("hypothetical", 0)

            def _pct(n: int) -> float:
                return round((n / total) * 100, 1) if total > 0 else 0.0

            # Coverage score: weighted average.
            # Structural relations count more (weight 1.0), inferred less (0.6),
            # hypothetical very little (0.2).
            if total > 0:
                coverage_score = round(
                    (structural * 1.0 + inferred * 0.6 + hypothetical * 0.2) / total,
                    3,
                )
            else:
                coverage_score = 0.0

            result = {
                "total_relations": total,
                "structural_count": structural,
                "structural_pct": _pct(structural),
                "inferred_count": inferred,
                "inferred_pct": _pct(inferred),
                "hypothetical_count": hypothetical,
                "hypothetical_pct": _pct(hypothetical),
                "coverage_score": coverage_score,
            }

            await _cache_set(cache_key, result, ttl=300)
            return result

    # ------------------------------------------------------------------
    # 4. get_gaps -- detect missing relations / capability gaps
    # ------------------------------------------------------------------

    async def get_gaps(self, department_code: str) -> dict[str, Any]:
        """Detect missing relations for *department_code*.

        Enhanced in Phase 2: also checks L2 coverage and inferred relation quality.
        """
        cache_key = f"relations:{department_code}:gaps"
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached

        async with acquire_conn() as conn:
            gaps: list[dict[str, Any]] = []

            total_enterprises = await conn.fetchval(
                "SELECT COUNT(*) FROM actors WHERE department_code = $1 AND type = 'enterprise'",
                department_code,
            )

            # -- Gap 1: enterprises without institutional links --
            # Note: NatureJuridiqueExtractor now detects some institutions
            # (administers_in) but real subvention/marche links are still missing.
            total_institutions = await conn.fetchval(
                "SELECT COUNT(*) FROM actors WHERE department_code = $1 AND type = 'institution'",
                department_code,
            )
            no_institution = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT a.id)
                FROM actors a
                WHERE a.department_code = $1
                  AND a.type = 'enterprise'
                  AND NOT EXISTS (
                      SELECT 1 FROM relations r
                      JOIN actors tgt ON r.target_actor_id = tgt.id
                      WHERE r.source_actor_id = a.id
                        AND tgt.type = 'institution'
                  )
                """,
                department_code,
            )
            if no_institution and no_institution > 0:
                inst_note = ""
                if total_institutions and total_institutions > 0:
                    inst_note = (
                        f" ({total_institutions} institutions detectees par NJ, "
                        "mais les liens subventions/marches restent absents)"
                    )
                gaps.append(
                    {
                        "gap_type": "partial_coverage",
                        "description": (
                            f"{no_institution}/{total_enterprises} entreprises "
                            "sans lien direct vers une institution" + inst_note
                        ),
                        "affected_actors": no_institution,
                        "potential_source": "Subventions (data.gouv.fr), BOAMP, marches publics",
                        "priority": "high",
                    }
                )

            # -- Gap 2: supply-chain coverage --
            supply_chain_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM relations r
                JOIN actors a ON r.source_actor_id = a.id OR r.target_actor_id = a.id
                WHERE a.department_code = $1
                  AND r.subtype = 'likely_supplier'
                """,
                department_code,
            )
            if (supply_chain_count or 0) == 0 and total_enterprises and total_enterprises > 0:
                gaps.append(
                    {
                        "gap_type": "missing_source",
                        "description": (
                            "Aucune relation fournisseur/client detectee. "
                            "Les chaines d'approvisionnement sont invisibles. "
                            "Relancer discover() pour activer l'infereur CPV."
                        ),
                        "affected_actors": total_enterprises,
                        "potential_source": "Douanes, factures electroniques, declarations TVA, CPV BOAMP",
                        "priority": "high",
                    }
                )
            elif total_enterprises and total_enterprises > 0:
                gaps.append(
                    {
                        "gap_type": "partial_coverage",
                        "description": (
                            f"{supply_chain_count} relations fournisseur inferees par CPV, "
                            "mais pas de donnees fournisseurs reelles."
                        ),
                        "affected_actors": total_enterprises,
                        "potential_source": "Douanes, factures electroniques, declarations TVA",
                        "priority": "medium",
                    }
                )

            # -- Gap 3: no director/shareholder links --
            no_directors = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT a.id)
                FROM actors a
                WHERE a.department_code = $1
                  AND a.type = 'enterprise'
                  AND NOT EXISTS (
                      SELECT 1 FROM relations r
                      WHERE (r.source_actor_id = a.id OR r.target_actor_id = a.id)
                        AND r.subtype IN ('director_of', 'shareholder_of', 'managed_by', 'shared_director')
                  )
                """,
                department_code,
            )
            if no_directors and no_directors > 0:
                gaps.append(
                    {
                        "gap_type": "missing_source",
                        "description": (
                            f"{no_directors}/{total_enterprises} entreprises "
                            "sans lien dirigeant/actionnaire (Infogreffe non disponible)"
                        ),
                        "affected_actors": no_directors,
                        "potential_source": "Infogreffe, Pappers, RNCS",
                        "priority": "medium",
                    }
                )

            # -- Gap 4: cascade / domino prediction limitations --
            # L3 predictors now exist (cascade_risk, territorial_impact) but
            # remain simplistic without real supply-chain data.
            l3_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM relations r
                JOIN actors a ON r.source_actor_id = a.id OR r.target_actor_id = a.id
                WHERE a.department_code = $1
                  AND r.relation_type = 'hypothetical'
                """,
                department_code,
            )
            if (l3_count or 0) == 0:
                gaps.append(
                    {
                        "gap_type": "missing_model",
                        "description": (
                            "Aucune prediction L3 (cascade, impact territorial). "
                            "Relancer discover() pour activer les predicteurs."
                        ),
                        "affected_actors": total_enterprises or 0,
                        "potential_source": "Predicteurs L3 (cascade, institution, impact)",
                        "priority": "medium",
                    }
                )
            else:
                gaps.append(
                    {
                        "gap_type": "model_limitation",
                        "description": (
                            f"{l3_count} predictions L3 presentes, mais le modele "
                            "de cascade reste simplifie (pas de donnees fournisseurs reelles, "
                            "estimation par tranches d'effectifs)"
                        ),
                        "affected_actors": total_enterprises or 0,
                        "potential_source": "Donnees fournisseurs, factures, chaines d'approvisionnement",
                        "priority": "low",
                    }
                )

            # -- Gap 5: enterprises without sector assignment --
            no_sector = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT a.id)
                FROM actors a
                WHERE a.department_code = $1
                  AND a.type = 'enterprise'
                  AND NOT EXISTS (
                      SELECT 1 FROM relations r
                      JOIN actors tgt ON r.target_actor_id = tgt.id
                      WHERE r.source_actor_id = a.id
                        AND r.subtype = 'belongs_to_sector'
                  )
                """,
                department_code,
            )
            if no_sector and no_sector > 0:
                gaps.append(
                    {
                        "gap_type": "low_coverage",
                        "description": (
                            f"{no_sector}/{total_enterprises} entreprises "
                            "sans secteur d'activite assigne (code NAF manquant)"
                        ),
                        "affected_actors": no_sector,
                        "potential_source": "Enrichissement SIRENE, scraping sites entreprises",
                        "priority": "medium",
                    }
                )

            # -- Gap 6: enterprises without employment weight --
            no_employment = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT a.id)
                FROM actors a
                WHERE a.department_code = $1
                  AND a.type = 'enterprise'
                  AND NOT EXISTS (
                      SELECT 1 FROM relations r
                      WHERE r.source_actor_id = a.id
                        AND r.subtype = 'employment_anchor'
                  )
                  AND (a.metadata->>'tranche_effectif' IS NULL
                       OR a.metadata->>'tranche_effectif' = ''
                       OR a.metadata->>'tranche_effectif' = '00')
                """,
                department_code,
            )
            if no_employment and no_employment > 0:
                gaps.append(
                    {
                        "gap_type": "low_coverage",
                        "description": (
                            f"{no_employment}/{total_enterprises} entreprises "
                            "sans donnees d'effectifs (tranche_effectif absente ou nulle)"
                        ),
                        "affected_actors": no_employment,
                        "potential_source": "SIRENE V3 API, INSEE DADS",
                        "priority": "low",
                    }
                )

            # -- Gap 7: L2 inferred relations quality check --
            l2_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM relations r
                JOIN actors a ON r.source_actor_id = a.id OR r.target_actor_id = a.id
                WHERE a.department_code = $1
                  AND r.relation_type = 'inferred'
                """,
                department_code,
            )
            if (l2_count or 0) == 0 and (total_enterprises or 0) > 0:
                gaps.append(
                    {
                        "gap_type": "missing_model",
                        "description": (
                            "Aucune relation inferee (L2). "
                            "Relancer discover() pour activer les infereurs statistiques."
                        ),
                        "affected_actors": total_enterprises or 0,
                        "potential_source": "Infereurs L2 (concentration, emploi, clusters)",
                        "priority": "medium",
                    }
                )

            # -- Gap 8: stale data check --
            stale_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM actors
                WHERE department_code = $1
                  AND updated_at < NOW() - INTERVAL '90 days'
                """,
                department_code,
            )
            if stale_count and stale_count > 0:
                gaps.append(
                    {
                        "gap_type": "stale_data",
                        "description": (
                            f"{stale_count} acteurs n'ont pas ete mis a jour "
                            "depuis plus de 90 jours"
                        ),
                        "affected_actors": stale_count,
                        "potential_source": "Re-execution discover() avec sources actualisees",
                        "priority": "low",
                    }
                )

            # -- Build algorithmic honesty table --
            honesty = await self._build_honesty_table(conn, department_code)

            result = {
                "department_code": department_code,
                "total_gaps": len(gaps),
                "gaps": gaps,
                "capability_matrix": CAPABILITY_MATRIX,
                "algorithmic_honesty": honesty,
            }

            await _cache_set(cache_key, result, ttl=300)
            return result

    # ==================================================================
    # Private helpers -- UPSERT logic
    # ==================================================================

    async def _upsert_actors(
        self,
        conn: asyncpg.Connection,
        actors: list[dict[str, Any]],
    ) -> int:
        """UPSERT actors into the ``actors`` table. Returns count."""
        if not actors:
            return 0

        # Deduplicate by external_id (keep last)
        seen: dict[str, dict[str, Any]] = {}
        for a in actors:
            seen[a["external_id"]] = a
        unique_actors = list(seen.values())

        upserted = 0
        for actor in unique_actors:
            try:
                metadata_json = json.dumps(actor.get("metadata") or {})
                await conn.execute(
                    """
                    INSERT INTO actors (id, type, external_id, name, department_code, metadata)
                    VALUES ($1::uuid, $2::actor_type, $3, $4, $5, $6::jsonb)
                    ON CONFLICT (external_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        metadata = actors.metadata || EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    uuid.UUID(actor["id"]),
                    actor["type"],
                    actor["external_id"],
                    actor["name"],
                    actor.get("department_code"),
                    metadata_json,
                )
                upserted += 1
            except Exception:
                logger.exception(
                    "Failed to upsert actor external_id={}",
                    actor.get("external_id"),
                )
        return upserted

    # ------------------------------------------------------------------
    # 5. what-if simulation
    # ------------------------------------------------------------------

    async def whatif(
        self,
        actor_external_id: str,
        department_code: str,
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """Simulate the cascade effect if *actor_external_id* fails."""
        return await simulate_whatif(actor_external_id, department_code, max_depth)

    # ------------------------------------------------------------------
    # 6. GraphML export (Gephi-compatible)
    # ------------------------------------------------------------------

    def _to_graphml(self, graph_data: dict) -> str:
        """Convert graph to GraphML XML format (Gephi-compatible)."""
        import xml.etree.ElementTree as ET

        graphml = ET.Element("graphml", xmlns="http://graphml.graphstruct.org/xmlns")

        # Attribute declarations
        for attr_id, attr_name, attr_for, attr_type in [
            ("d0", "label", "node", "string"),
            ("d1", "type", "node", "string"),
            ("d2", "external_id", "node", "string"),
            ("d3", "department_code", "node", "string"),
            ("d4", "size", "node", "double"),
            ("d5", "relation_type", "edge", "string"),
            ("d6", "subtype", "edge", "string"),
            ("d7", "confidence", "edge", "double"),
            ("d8", "weight", "edge", "double"),
        ]:
            key_el = ET.SubElement(graphml, "key", id=attr_id)
            key_el.set("attr.name", attr_name)
            key_el.set("attr.type", attr_type)
            key_el.set("for", attr_for)

        graph_el = ET.SubElement(graphml, "graph", id="relations", edgedefault="directed")

        # Nodes
        for node in graph_data.get("nodes", []):
            n = ET.SubElement(graph_el, "node", id=node["id"])
            ET.SubElement(n, "data", key="d0").text = node.get("label", "")
            ET.SubElement(n, "data", key="d1").text = node.get("type", "")
            ET.SubElement(n, "data", key="d2").text = node.get("external_id", "")
            ET.SubElement(n, "data", key="d3").text = node.get("department_code", "") or ""
            ET.SubElement(n, "data", key="d4").text = str(node.get("size", 10.0))

        # Edges
        for i, link in enumerate(graph_data.get("links", [])):
            e = ET.SubElement(
                graph_el, "edge", id=f"e{i}", source=link["source"], target=link["target"]
            )
            ET.SubElement(e, "data", key="d5").text = link.get("relation_type", "")
            ET.SubElement(e, "data", key="d6").text = link.get("subtype", "")
            ET.SubElement(e, "data", key="d7").text = str(link.get("confidence", 0.0))
            ET.SubElement(e, "data", key="d8").text = str(link.get("weight", 1.0))

        return ET.tostring(graphml, encoding="unicode", xml_declaration=True)

    # ------------------------------------------------------------------
    # 7. export graph data
    # ------------------------------------------------------------------

    async def export_graph(
        self,
        department_code: str,
        fmt: str = "json",
    ) -> dict[str, Any] | str:
        """Export the relation graph for *department_code*.

        Supported formats: 'json' (D3.js payload), 'csv' (flat tables),
        'graphml' (Gephi-compatible GraphML XML).
        """
        graph = await self.get_graph(department_code, min_confidence=0.0)
        coverage = await self.get_coverage(department_code)

        if fmt == "graphml":
            return self._to_graphml(graph)

        if fmt == "csv":
            # Build CSV-like rows
            actor_rows = []
            for node in graph["nodes"]:
                actor_rows.append(
                    {
                        "id": node["id"],
                        "label": node["label"],
                        "type": node["type"],
                        "external_id": node["external_id"],
                        "department_code": node.get("department_code", ""),
                    }
                )

            relation_rows = []
            # Build a node id → label map
            id_to_label = {n["id"]: n["label"] for n in graph["nodes"]}
            for link in graph["links"]:
                relation_rows.append(
                    {
                        "source_id": link["source"],
                        "source_label": id_to_label.get(link["source"], ""),
                        "target_id": link["target"],
                        "target_label": id_to_label.get(link["target"], ""),
                        "relation_type": link["relation_type"],
                        "subtype": link["subtype"],
                        "confidence": link["confidence"],
                        "weight": link["weight"],
                    }
                )

            return {
                "format": "csv",
                "department_code": department_code,
                "actors": actor_rows,
                "relations": relation_rows,
                "coverage": coverage,
            }

        # Default: JSON (same as get_graph but with coverage)
        return {
            "format": "json",
            "department_code": department_code,
            **graph,
            "coverage": coverage,
        }

    # ------------------------------------------------------------------
    # Algorithmic honesty -- transparency about what we detect and how
    # ------------------------------------------------------------------

    async def _build_honesty_table(
        self,
        conn: asyncpg.Connection,
        department_code: str,
    ) -> list[dict[str, Any]]:
        """Build the algorithmic honesty table for *department_code*.

        For each relation subtype detected, reports:
        - The method used to detect it
        - The confidence range
        - Known limitations
        - Number of relations of this type in the department
        """
        subtype_counts = await conn.fetch(
            """
            SELECT r.subtype, r.relation_type::text AS rtype,
                   COUNT(*) AS cnt,
                   ROUND(AVG(r.confidence)::numeric, 3) AS avg_confidence,
                   ROUND(MIN(r.confidence)::numeric, 3) AS min_confidence,
                   ROUND(MAX(r.confidence)::numeric, 3) AS max_confidence
            FROM relations r
            JOIN actors a ON r.source_actor_id = a.id OR r.target_actor_id = a.id
            WHERE a.department_code = $1
            GROUP BY r.subtype, r.relation_type
            ORDER BY r.relation_type, cnt DESC
            """,
            department_code,
        )

        subtype_info: dict[str, dict[str, str]] = {
            "headquarter_in": {
                "method": "Extraction directe SIRENE (siege social)",
                "limitation": "Entreprises multi-sites non detectees",
                "data_source": "API SIRENE / signals table",
            },
            "belongs_to_sector": {
                "method": "Code NAF principal de l'entreprise",
                "limitation": "Activite secondaire non prise en compte",
                "data_source": "API SIRENE / signals table",
            },
            "sector_present_in": {
                "method": "Agregation des entreprises par NAF dans le departement",
                "limitation": "Poids brut, pas de normalisation nationale",
                "data_source": "API SIRENE / signals table",
            },
            "event_creation": {
                "method": "Annonces BODACC de creation / immatriculation",
                "limitation": "Delai de publication (1-2 semaines)",
                "data_source": "BODACC (bodacc-datadila.opendatasoft.com)",
            },
            "event_liquidation": {
                "method": "Annonces BODACC de liquidation judiciaire",
                "limitation": "Ne couvre que les procedures publiees",
                "data_source": "BODACC",
            },
            "event_redressement": {
                "method": "Annonces BODACC de redressement judiciaire",
                "limitation": "Pas de suivi de l'issue du plan",
                "data_source": "BODACC",
            },
            "event_procedure_collective": {
                "method": "Annonces BODACC de procedures collectives",
                "limitation": "Pas de distinction entre types de procedures",
                "data_source": "BODACC",
            },
            "event_vente": {
                "method": "Annonces BODACC de cession de fonds de commerce",
                "limitation": "Prix et acheteur non toujours disponibles",
                "data_source": "BODACC",
            },
            "event_radiation": {
                "method": "Annonces BODACC de radiation RCS",
                "limitation": "Delai de publication",
                "data_source": "BODACC",
            },
            "sector_dominance": {
                "method": "Part statistique du secteur > 10% des entreprises du departement",
                "limitation": "Seuil arbitraire, pas de benchmark national",
                "data_source": "Infereur L2 (SectorConcentrationInferrer)",
            },
            "employment_anchor": {
                "method": "Estimation effectifs via tranche_effectif INSEE (> 2% emploi dept)",
                "limitation": "Estimation par tranche, pas effectifs exacts",
                "data_source": "Infereur L2 (EmploymentWeightInferrer)",
            },
            "cluster_member": {
                "method": "Groupement NAF-section + code postal (>= 3 entreprises)",
                "limitation": "Granularite code postal, pas IRIS ou commune",
                "data_source": "Infereur L2 (GeographicClusterInferrer)",
            },
            # -- L1: BoampExtractor subtypes --
            "awarded_contract": {
                "method": "Extraction avis d'attribution BOAMP (acheteur public -> titulaire)",
                "limitation": "Champ titulaire parfois absent ou anonymise ; montants non disponibles",
                "data_source": "BOAMP (boamp-datadila.opendatasoft.com)",
            },
            # -- L1: SubventionsExtractor subtypes --
            "funded_by": {
                "method": "Extraction datasets subventions data.gouv.fr (organisation -> territoire)",
                "limitation": "Recherche par nom de departement, pas de montants ni beneficiaires individuels",
                "data_source": "data.gouv.fr API (datasets subventions)",
            },
            # -- L1: NatureJuridiqueExtractor subtypes --
            "operates_in": {
                "method": "RNA: API recherche-entreprises (NJ 92xx) + NJ: reclassification SIRENE",
                "limitation": "RNA: echantillon 100/dept ; NJ: code NJ peut etre obsolete",
                "data_source": "RNA API (recherche-entreprises.api.gouv.fr) + SIRENE nature_juridique",
            },
            "trains_in": {
                "method": "Classification nature_juridique (codes 73xx/85xx formation)",
                "limitation": "Tous les codes NJ formation ne sont pas des OF actifs",
                "data_source": "SIRENE nature_juridique",
            },
            "finances_in": {
                "method": "Classification nature_juridique (codes 64xx-66xx finance)",
                "limitation": "Intermediation financiere != banque de detail",
                "data_source": "SIRENE nature_juridique",
            },
            "administers_in": {
                "method": "Classification nature_juridique (codes 71xx-74xx institutions)",
                "limitation": "Perimetre administratif imprecis",
                "data_source": "SIRENE nature_juridique",
            },
            # -- L2: SupplyChainInferrer subtype --
            "likely_supplier": {
                "method": "Inference chaine fournisseurs par compatibilite CPV (marches publics BOAMP)",
                "limitation": "CPV prefix 2 chiffres seulement, pas de relation commerciale reelle verifiee",
                "data_source": "BOAMP cpv_code dans metadata acteurs + _CPV_SUPPLY_CHAIN mapping",
            },
            # -- L2: DirectorLinkInferrer subtype --
            "shared_director": {
                "method": "Correspondance noms de personnes normalises dans signaux BODACC (commercant + listepersonnes)",
                "limitation": "Limite aux EI/personnes physiques BODACC, faux positifs sur homonymes courants",
                "data_source": "Signaux BODACC (commercant format NOM, Prenom + listepersonnes)",
            },
            # -- L2: ProximityInferrer subtype --
            "geographic_proximity": {
                "method": "Geocodage BAN (api-adresse.data.gouv.fr) + distance Haversine entre acteurs",
                "limitation": "Cap 50 geocodages/dept, score BAN >= 0.4, adresses incompletes ignorees",
                "data_source": "BAN API + metadata acteurs (ville, commune, code_postal, adresse)",
            },
            # -- L2: SocialLinkInferrer subtypes --
            "social_link": {
                "method": "Correspondance NAF association/secteur (>= 2 entreprises)",
                "limitation": "Lien associatif infere par secteur, pas par activite reelle",
                "data_source": "SIRENE NAF + actors table",
            },
            "social_proximity": {
                "method": "Proximite employeur-association par secteur (effectif >= 10)",
                "limitation": "Proximite sectorielle != collaboration reelle",
                "data_source": "SIRENE NAF + actors table",
            },
            # -- L2: FinancialLinkInferrer subtype --
            "likely_finances": {
                "method": "Inference bancaire basee sur taille entreprise (effectif >= 15)",
                "limitation": "Taille entreprise != relation bancaire reelle",
                "data_source": "SIRENE tranche_effectif",
            },
            # -- L2: FormationLinkInferrer subtypes --
            "trains_sector": {
                "method": "Inference demande formation par secteur (>= 3 entreprises, top 10)",
                "limitation": "Demande sectorielle != offre de formation reelle",
                "data_source": "Nombre d'entreprises par secteur",
            },
            "likely_trains": {
                "method": "Inference formation-employeur par taille (effectif >= 50)",
                "limitation": "Grande entreprise != client formation reel",
                "data_source": "SIRENE tranche_effectif",
            },
            "cascade_risk": {
                "method": "Propagation fragility × concentration sectorielle",
                "limitation": "Pas de donnees fournisseurs, modele simplifie",
                "data_source": "Predicteur L3 (CascadePredictor)",
            },
            "likely_institution": {
                "method": "Prediction basee sur taille, secteur et evenements BODACC",
                "limitation": "Pas de verification reelle, liens hypothetiques",
                "data_source": "Predicteur L3 (InstitutionalLinkPredictor)",
            },
            "territorial_impact": {
                "method": "Score composite: emploi × unicite sectorielle × contagion",
                "limitation": "Estimation par tranche, pas impact reel mesure",
                "data_source": "Predicteur L3 (TerritorialImpactPredictor)",
            },
            # -- L1: TerritorialStructuresExtractor subtypes --
            "commune_in_dept": {
                "method": "Extraction directe communes geo.api.gouv.fr",
                "limitation": "Top 30 communes par population seulement",
                "data_source": "geo.api.gouv.fr (communes)",
            },
            "located_in_commune": {
                "method": "Correspondance code postal entreprise → commune",
                "limitation": "Code postal peut couvrir plusieurs communes",
                "data_source": "Code postal acteurs + geo.api.gouv.fr",
            },
            "administered_by": {
                "method": "Lien hierarchique commune → conseil departemental",
                "limitation": "Donnees statiques, pas de verification",
                "data_source": "Donnees statiques administratives",
            },
            "belongs_to_region": {
                "method": "Lien hierarchique departement → region",
                "limitation": "Donnees statiques, pas de verification",
                "data_source": "Donnees statiques administratives",
            },
            # -- L1: EPCIExtractor subtypes --
            "administers_territory": {
                "method": "Extraction EPCIs + institutions territoriales geo.api.gouv.fr",
                "limitation": "Lien administratif, pas d'impact economique mesure",
                "data_source": "geo.api.gouv.fr (EPCIs)",
            },
            "belongs_to_epci": {
                "method": "Correspondance code postal entreprise → EPCI via communes",
                "limitation": "Code postal peut couvrir plusieurs EPCIs",
                "data_source": "geo.api.gouv.fr (communes d'EPCI)",
            },
            # -- L1: PolesExtractor subtypes --
            "pole_in_territory": {
                "method": "Donnees hardcodees poles de competitivite Phase V",
                "limitation": "Donnees 2023, certains poles ont fusionne ou disparu",
                "data_source": "competitivite.gouv.fr + Wikipedia",
            },
            "pole_covers_sector": {
                "method": "Mapping pole → sections NAF couvertes",
                "limitation": "Sections NAF larges, pas de granularite sous-secteur",
                "data_source": "competitivite.gouv.fr",
            },
        }

        honesty: list[dict[str, Any]] = []
        for row in subtype_counts:
            info = subtype_info.get(row["subtype"], {})
            honesty.append(
                {
                    "relation_subtype": row["subtype"],
                    "relation_type": row["rtype"],
                    "count": row["cnt"],
                    "avg_confidence": float(row["avg_confidence"]),
                    "min_confidence": float(row["min_confidence"]),
                    "max_confidence": float(row["max_confidence"]),
                    "method": info.get("method", "Non documente"),
                    "limitation": info.get("limitation", "Non documente"),
                    "data_source": info.get("data_source", "Inconnu"),
                }
            )

        return honesty

    async def _upsert_relations(
        self,
        conn: asyncpg.Connection,
        relations: list[dict[str, Any]],
    ) -> int:
        """UPSERT relations (and their sources) into the database."""
        if not relations:
            return 0

        # Build an external_id -> actor UUID map from the database
        # (we need the real actor UUIDs for the FK references)
        ext_ids = set()
        for rel in relations:
            ext_ids.add(rel["source_actor_external_id"])
            ext_ids.add(rel["target_actor_external_id"])

        rows = await conn.fetch(
            """
            SELECT id, external_id FROM actors
            WHERE external_id = ANY($1)
            """,
            list(ext_ids),
        )
        ext_to_uuid: dict[str, uuid.UUID] = {row["external_id"]: row["id"] for row in rows}

        upserted = 0
        for rel in relations:
            src_uuid = ext_to_uuid.get(rel["source_actor_external_id"])
            tgt_uuid = ext_to_uuid.get(rel["target_actor_external_id"])
            if src_uuid is None or tgt_uuid is None:
                logger.debug(
                    "Skipping relation {}->{}: actor not found",
                    rel["source_actor_external_id"],
                    rel["target_actor_external_id"],
                )
                continue

            try:
                evidence_json = json.dumps(rel.get("evidence") or {})
                rel_uuid = uuid.UUID(rel["id"])

                await conn.execute(
                    """
                    INSERT INTO relations
                        (id, source_actor_id, target_actor_id, relation_type,
                         subtype, confidence, weight, evidence)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4::relation_type,
                            $5, $6, $7, $8::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        confidence = GREATEST(relations.confidence, EXCLUDED.confidence),
                        weight = EXCLUDED.weight,
                        evidence = relations.evidence || EXCLUDED.evidence
                    """,
                    rel_uuid,
                    src_uuid,
                    tgt_uuid,
                    rel["relation_type"],
                    rel["subtype"],
                    rel["confidence"],
                    rel.get("weight", 1.0),
                    evidence_json,
                )
                upserted += 1

                # -- relation_sources (provenance tracking) --
                source_type = rel.get("source_type", "sirene")
                source_ref = rel.get("source_ref", "")
                contributed = rel.get("confidence", 0.0)

                await conn.execute(
                    """
                    INSERT INTO relation_sources
                        (relation_id, source_type, source_ref, contributed_confidence)
                    VALUES ($1::uuid, $2::source_type, $3, $4)
                    ON CONFLICT DO NOTHING
                    """,
                    rel_uuid,
                    source_type,
                    source_ref,
                    contributed,
                )

            except Exception:
                logger.exception(
                    "Failed to upsert relation {}->{}",
                    rel["source_actor_external_id"],
                    rel["target_actor_external_id"],
                )

        return upserted
