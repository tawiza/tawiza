"""Relation predictors (Level 3) -- hypothetical / predictive relations.

Unlike L2 inferrers which find statistical patterns in existing data,
L3 predictors MODEL future scenarios and probabilistic links that
cannot be confirmed from available data sources.

All predicted relations have:
- relation_type = 'hypothetical'
- confidence in [0.05, 0.39]
- source_type = 'model'
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any

from loguru import logger

from src.application.services._db_pool import acquire_conn
from src.application.services.cascade_model import predict_cascade_probability


def _stable_uuid(prefix: str, key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"{prefix}:{key}")


def _actor_id(actor_type: str, external_id: str) -> uuid.UUID:
    return _stable_uuid("actor", f"{actor_type}:{external_id}")


def _relation_id(source_ext: str, target_ext: str, subtype: str) -> uuid.UUID:
    return _stable_uuid("relation", f"{source_ext}->{target_ext}:{subtype}")


# ---------------------------------------------------------------------------
# INSEE tranche_effectif → estimated headcount (shared with inferrers)
# ---------------------------------------------------------------------------

_TRANCHE_EFFECTIF: dict[str, int] = {
    "00": 0,
    "01": 1,
    "02": 4,
    "03": 7,
    "11": 15,
    "12": 35,
    "21": 75,
    "22": 150,
    "31": 225,
    "32": 375,
    "33": 750,
    "41": 1500,
    "42": 3500,
    "51": 7500,
    "52": 10000,
}


def _estimate_headcount(tranche: str | None) -> int:
    if not tranche:
        return 5
    return _TRANCHE_EFFECTIF.get(str(tranche).strip(), 5)


# ---------------------------------------------------------------------------
# Known institutional actors (virtual)
# ---------------------------------------------------------------------------

_INSTITUTIONS: list[dict[str, Any]] = [
    {
        "external_id": "INST:CCI",
        "name": "Chambre de Commerce et d'Industrie",
        "metadata": {"type": "cci", "scope": "departement"},
    },
    {
        "external_id": "INST:BPI",
        "name": "Bpifrance",
        "metadata": {"type": "bpi", "scope": "national"},
    },
    {
        "external_id": "INST:FT",
        "name": "France Travail (ex-Pole Emploi)",
        "metadata": {"type": "france_travail", "scope": "departement"},
    },
    {
        "external_id": "INST:URSSAF",
        "name": "URSSAF",
        "metadata": {"type": "urssaf", "scope": "regional"},
    },
    {
        "external_id": "INST:TRIBUNAL",
        "name": "Tribunal de Commerce",
        "metadata": {"type": "tribunal", "scope": "departement"},
    },
]


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BasePredictor(ABC):
    """Base class for L3 relation predictors."""

    source_name: str = ""

    @abstractmethod
    async def predict(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        """Return ``{"actors": [...], "relations": [...]}``."""
        ...


# ---------------------------------------------------------------------------
# 1. CascadePredictor
# ---------------------------------------------------------------------------


class CascadePredictor(BasePredictor):
    """Predict domino/cascade effects from enterprise failures.

    Algorithm:
    1. For each enterprise with BODACC distress signals (liquidation,
       redressement, procedure collective), compute a "fragility" score.
    2. Find other enterprises in the same sector AND territory.
    3. Create hypothetical "cascade_risk" relations between the fragile
       enterprise and its sector peers.
    4. Confidence = fragility × sector_concentration × proximity factor.

    Creates: enterprise_fragile → enterprise_peer "cascade_risk" (hypothetical)
    """

    source_name = "cascade_predictor"

    # BODACC events that indicate financial distress
    DISTRESS_SUBTYPES = {
        "event_liquidation",
        "event_redressement",
        "event_procedure_collective",
        "event_cloture_insuffisance",
    }

    async def predict(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # 1. Find enterprises with distress signals
            distressed = await conn.fetch(
                """
                SELECT DISTINCT a.external_id, a.name, a.metadata,
                       COUNT(r.id) AS distress_count
                FROM actors a
                JOIN relations r ON r.source_actor_id = a.id
                WHERE a.department_code = $1
                  AND a.type = 'enterprise'
                  AND r.subtype = ANY($2)
                GROUP BY a.external_id, a.name, a.metadata
                """,
                department_code,
                list(self.DISTRESS_SUBTYPES),
            )

            if not distressed:
                return {"actors": [], "relations": []}

            # 2. Build sector membership: enterprise_ext_id → sector_ext_id
            sector_links = await conn.fetch(
                """
                SELECT a_ent.external_id AS ent_ext,
                       a_sec.external_id AS sec_ext
                FROM relations r
                JOIN actors a_ent ON r.source_actor_id = a_ent.id
                JOIN actors a_sec ON r.target_actor_id = a_sec.id
                WHERE a_ent.department_code = $1
                  AND r.subtype = 'belongs_to_sector'
                  AND a_ent.type = 'enterprise'
                  AND a_sec.type = 'sector'
                """,
                department_code,
            )

            ent_to_sector: dict[str, str] = {}
            sector_to_ents: dict[str, list[str]] = defaultdict(list)
            for row in sector_links:
                ent_to_sector[row["ent_ext"]] = row["sec_ext"]
                sector_to_ents[row["sec_ext"]].append(row["ent_ext"])

            # 3. Get total enterprise count for concentration factor
            total_enterprises = await conn.fetchval(
                "SELECT COUNT(*) FROM actors WHERE department_code = $1 AND type = 'enterprise'",
                department_code,
            )

        if total_enterprises == 0:
            return {"actors": [], "relations": []}

        # 4. Create cascade_risk relations
        distressed_set = {row["external_id"] for row in distressed}

        for row in distressed:
            ent_ext = row["external_id"]
            distress_count = row["distress_count"]

            # Fragility score: more distress events = higher fragility
            fragility = min(distress_count * 0.15, 0.5)

            sector = ent_to_sector.get(ent_ext)
            if not sector:
                continue

            peers = sector_to_ents.get(sector, [])
            if len(peers) < 2:
                continue

            # Sector concentration factor
            concentration = len(peers) / total_enterprises

            for peer_ext in peers:
                if peer_ext == ent_ext:
                    continue
                if peer_ext in distressed_set:
                    continue  # skip already-distressed peers

                # Confidence: fragility × concentration, capped at 0.39
                confidence = min(fragility * (1 + concentration * 5), 0.39)
                confidence = round(max(confidence, 0.05), 3)

                rel_id = _relation_id(ent_ext, peer_ext, "cascade_risk")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": ent_ext,
                        "target_actor_external_id": peer_ext,
                        "relation_type": "hypothetical",
                        "subtype": "cascade_risk",
                        "confidence": confidence,
                        "weight": round(fragility * 5, 2),
                        "evidence": {
                            "source": "cascade_predictor",
                            "method": "distress_propagation",
                            "fragile_enterprise": ent_ext,
                            "fragile_name": row["name"],
                            "distress_events": distress_count,
                            "fragility_score": round(fragility, 3),
                            "sector": sector,
                            "sector_peers": len(peers),
                            "concentration": round(concentration, 4),
                        },
                        "source_type": "model",
                        "source_ref": f"predictor:cascade:{ent_ext}:{peer_ext}",
                    }
                )

        logger.info(
            "CascadePredictor dept={}: {} cascade_risk relations from {} distressed enterprises",
            department_code,
            len(relations),
            len(distressed),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# 2. InstitutionalLinkPredictor
# ---------------------------------------------------------------------------


class InstitutionalLinkPredictor(BasePredictor):
    """Predict likely institutional connections for enterprises.

    Algorithm:
    1. For each enterprise, predict which institutions they likely interact with:
       - All enterprises → CCI (registration), URSSAF (social charges)
       - Enterprises with >50 employees → BPI (financing)
       - Enterprises with distress events → Tribunal de Commerce
       - All enterprises → France Travail (employment)
    2. Confidence based on enterprise characteristics.

    Creates:
    - institution actors (INST:CCI, INST:BPI, etc.)
    - enterprise → institution "likely_institution" (hypothetical)
    """

    source_name = "institutional_link_predictor"

    async def predict(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # Only predict institutional links for enterprises that have
            # at least one concrete signal (BOAMP contract, BODACC event,
            # subvention, or other L1 relation) — not for every enterprise.
            enterprises = await conn.fetch(
                """
                SELECT DISTINCT a.external_id, a.name, a.metadata
                FROM actors a
                JOIN relations r ON r.source_actor_id = a.id OR r.target_actor_id = a.id
                WHERE a.department_code = $1
                  AND a.type = 'enterprise'
                  AND r.relation_type = 'structural'
                  AND r.subtype NOT IN ('headquarter_in', 'belongs_to_sector',
                                        'sector_present_in', 'located_in_commune')
                """,
                department_code,
            )

            # Check which enterprises have distress signals
            distressed_set: set[str] = set()
            distressed_rows = await conn.fetch(
                """
                SELECT DISTINCT a.external_id
                FROM actors a
                JOIN relations r ON r.source_actor_id = a.id
                WHERE a.department_code = $1
                  AND r.subtype IN ('event_liquidation', 'event_redressement',
                                    'event_procedure_collective')
                """,
                department_code,
            )
            distressed_set = {row["external_id"] for row in distressed_rows}

        if not enterprises:
            return {"actors": [], "relations": []}

        # Create institutional actors
        for inst in _INSTITUTIONS:
            inst_ext = f"{inst['external_id']}:{department_code}"
            actors[inst_ext] = {
                "id": str(_actor_id("institution", inst_ext)),
                "type": "institution",
                "external_id": inst_ext,
                "name": f"{inst['name']} ({department_code})",
                "department_code": department_code,
                "metadata": inst["metadata"],
            }

        for ent_row in enterprises:
            ent_ext = ent_row["external_id"]
            meta = ent_row["metadata"] if isinstance(ent_row["metadata"], dict) else {}
            headcount = _estimate_headcount(meta.get("tranche_effectif"))

            # CCI: all enterprises likely registered
            cci_ext = f"INST:CCI:{department_code}"
            rel_id = _relation_id(ent_ext, cci_ext, "likely_institution")
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": ent_ext,
                    "target_actor_external_id": cci_ext,
                    "relation_type": "hypothetical",
                    "subtype": "likely_institution",
                    "confidence": 0.30,
                    "weight": 1.0,
                    "evidence": {
                        "source": "institutional_link_predictor",
                        "method": "enterprise_characteristics",
                        "institution": "CCI",
                        "reason": "Immatriculation RCS obligatoire",
                    },
                    "source_type": "model",
                    "source_ref": f"predictor:institution:{ent_ext}:CCI",
                }
            )

            # URSSAF: all employers
            if headcount > 0:
                urssaf_ext = f"INST:URSSAF:{department_code}"
                rel_id = _relation_id(ent_ext, urssaf_ext, "likely_institution")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": ent_ext,
                        "target_actor_external_id": urssaf_ext,
                        "relation_type": "hypothetical",
                        "subtype": "likely_institution",
                        "confidence": 0.25 if headcount > 10 else 0.15,
                        "weight": 1.0,
                        "evidence": {
                            "source": "institutional_link_predictor",
                            "method": "employer_status",
                            "institution": "URSSAF",
                            "estimated_headcount": headcount,
                        },
                        "source_type": "model",
                        "source_ref": f"predictor:institution:{ent_ext}:URSSAF",
                    }
                )

            # BPI: larger enterprises or high-growth sectors
            if headcount >= 50:
                bpi_ext = f"INST:BPI:{department_code}"
                confidence = min(0.10 + (headcount / 1000) * 0.2, 0.35)
                rel_id = _relation_id(ent_ext, bpi_ext, "likely_institution")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": ent_ext,
                        "target_actor_external_id": bpi_ext,
                        "relation_type": "hypothetical",
                        "subtype": "likely_institution",
                        "confidence": round(confidence, 3),
                        "weight": 1.5,
                        "evidence": {
                            "source": "institutional_link_predictor",
                            "method": "size_based_financing",
                            "institution": "BPI",
                            "estimated_headcount": headcount,
                        },
                        "source_type": "model",
                        "source_ref": f"predictor:institution:{ent_ext}:BPI",
                    }
                )

            # Tribunal: enterprises with distress signals
            if ent_ext in distressed_set:
                tribunal_ext = f"INST:TRIBUNAL:{department_code}"
                rel_id = _relation_id(ent_ext, tribunal_ext, "likely_institution")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": ent_ext,
                        "target_actor_external_id": tribunal_ext,
                        "relation_type": "hypothetical",
                        "subtype": "likely_institution",
                        "confidence": 0.35,
                        "weight": 2.0,
                        "evidence": {
                            "source": "institutional_link_predictor",
                            "method": "distress_event_match",
                            "institution": "Tribunal de Commerce",
                            "has_distress_events": True,
                        },
                        "source_type": "model",
                        "source_ref": f"predictor:institution:{ent_ext}:TRIBUNAL",
                    }
                )

            # France Travail: enterprises with employees
            if headcount >= 10:
                ft_ext = f"INST:FT:{department_code}"
                rel_id = _relation_id(ent_ext, ft_ext, "likely_institution")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": ent_ext,
                        "target_actor_external_id": ft_ext,
                        "relation_type": "hypothetical",
                        "subtype": "likely_institution",
                        "confidence": 0.20,
                        "weight": 1.0,
                        "evidence": {
                            "source": "institutional_link_predictor",
                            "method": "employer_employment_service",
                            "institution": "France Travail",
                            "estimated_headcount": headcount,
                        },
                        "source_type": "model",
                        "source_ref": f"predictor:institution:{ent_ext}:FT",
                    }
                )

        logger.info(
            "InstitutionalLinkPredictor dept={}: {} actors, {} likely_institution relations",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# 3. TerritorialImpactPredictor
# ---------------------------------------------------------------------------


class TerritorialImpactPredictor(BasePredictor):
    """Estimate territorial impact if an enterprise were to fail.

    Algorithm:
    1. For each enterprise, compute an impact score based on:
       - Employment share of the department
       - Sector uniqueness (is it the only representative of its sector?)
       - Number of BODACC distress signals in same sector (contagion risk)
    2. Create "territorial_impact" relation (enterprise → territory)
       only for enterprises with significant impact (score > threshold).
    3. Confidence ∝ impact score, capped at 0.39.

    Creates: enterprise → territory "territorial_impact" (hypothetical)
    """

    source_name = "territorial_impact_predictor"

    IMPACT_THRESHOLD = 0.15  # minimum impact score to create relation

    async def predict(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # Fetch all enterprises with metadata
            enterprises = await conn.fetch(
                """
                SELECT a.external_id, a.name, a.metadata
                FROM actors a
                WHERE a.department_code = $1 AND a.type = 'enterprise'
                """,
                department_code,
            )

            # Sector membership
            sector_links = await conn.fetch(
                """
                SELECT a_ent.external_id AS ent_ext,
                       a_sec.external_id AS sec_ext,
                       a_sec.name AS sec_name
                FROM relations r
                JOIN actors a_ent ON r.source_actor_id = a_ent.id
                JOIN actors a_sec ON r.target_actor_id = a_sec.id
                WHERE a_ent.department_code = $1
                  AND r.subtype = 'belongs_to_sector'
                """,
                department_code,
            )

            # Count distress events per sector
            sector_distress = await conn.fetch(
                """
                SELECT a_sec.external_id AS sec_ext,
                       COUNT(DISTINCT a_ent.id) AS distressed_count
                FROM relations r_distress
                JOIN actors a_ent ON r_distress.source_actor_id = a_ent.id
                JOIN relations r_sec ON r_sec.source_actor_id = a_ent.id
                JOIN actors a_sec ON r_sec.target_actor_id = a_sec.id
                WHERE a_ent.department_code = $1
                  AND r_distress.subtype IN ('event_liquidation', 'event_redressement',
                                              'event_procedure_collective')
                  AND r_sec.subtype = 'belongs_to_sector'
                GROUP BY a_sec.external_id
                """,
                department_code,
            )

        if not enterprises:
            return {"actors": [], "relations": []}

        # Build lookup maps
        ent_to_sector: dict[str, tuple[str, str]] = {}
        sector_members: dict[str, int] = defaultdict(int)
        for row in sector_links:
            ent_to_sector[row["ent_ext"]] = (row["sec_ext"], row["sec_name"])
            sector_members[row["sec_ext"]] += 1

        sector_distress_map: dict[str, int] = {
            row["sec_ext"]: row["distressed_count"] for row in sector_distress
        }

        # Total employment estimation
        total_employment = 0
        ent_headcounts: dict[str, int] = {}
        for row in enterprises:
            meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
            hc = _estimate_headcount(meta.get("tranche_effectif"))
            ent_headcounts[row["external_id"]] = hc
            total_employment += hc

        if total_employment == 0:
            total_employment = 1  # avoid division by zero

        territory_ext_id = f"DEPT:{department_code}"

        for row in enterprises:
            ent_ext = row["external_id"]
            headcount = ent_headcounts.get(ent_ext, 5)

            # Factor 1: Employment share (0.0 - 1.0)
            employment_share = headcount / total_employment

            # Factor 2: Sector uniqueness (1.0 if sole representative)
            sector_info = ent_to_sector.get(ent_ext)
            if sector_info:
                sec_ext, sec_name = sector_info
                members_in_sector = sector_members.get(sec_ext, 1)
                uniqueness = 1.0 / members_in_sector
            else:
                sec_ext, sec_name = "", ""
                uniqueness = 0.0

            # Factor 3: Sector contagion (how many distressed in same sector)
            contagion = 0.0
            if sec_ext:
                distressed_in_sector = sector_distress_map.get(sec_ext, 0)
                contagion = min(distressed_in_sector * 0.1, 0.3)

            # Composite impact score
            impact = (
                employment_share * 0.5  # employment is most important
                + uniqueness * 0.3  # being the only one matters
                + contagion * 0.2  # sector fragility amplifies
            )

            if impact < self.IMPACT_THRESHOLD:
                continue

            # Confidence capped at L3 range
            confidence = min(impact * 0.8, 0.39)
            confidence = round(max(confidence, 0.05), 3)

            rel_id = _relation_id(ent_ext, territory_ext_id, "territorial_impact")
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": ent_ext,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "hypothetical",
                    "subtype": "territorial_impact",
                    "confidence": confidence,
                    "weight": round(impact * 10, 2),
                    "evidence": {
                        "source": "territorial_impact_predictor",
                        "method": "composite_impact_score",
                        "enterprise": ent_ext,
                        "enterprise_name": row["name"],
                        "estimated_headcount": headcount,
                        "employment_share_pct": round(employment_share * 100, 2),
                        "sector": sec_ext,
                        "sector_name": sec_name,
                        "sector_uniqueness": round(uniqueness, 3),
                        "sector_contagion": round(contagion, 3),
                        "impact_score": round(impact, 4),
                        "department": department_code,
                    },
                    "source_type": "model",
                    "source_ref": f"predictor:territorial_impact:{ent_ext}:{department_code}",
                }
            )

        logger.info(
            "TerritorialImpactPredictor dept={}: {} territorial_impact relations",
            department_code,
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# What-If Simulation Engine
# ---------------------------------------------------------------------------


async def simulate_whatif(
    actor_external_id: str,
    department_code: str,
    max_depth: int = 3,
) -> dict[str, Any]:
    """Simulate what happens if *actor_external_id* fails.

    Performs a BFS through the relation graph from the failing enterprise,
    calculating cascading impact at each hop. Returns:
    - cascade_paths: ordered list of affected actors with impact scores
    - total_impact_score: aggregate territorial impact
    - employment_at_risk: estimated jobs threatened
    """
    async with acquire_conn() as conn:
        # Validate the actor exists
        actor = await conn.fetchrow(
            "SELECT id, external_id, name, metadata FROM actors WHERE external_id = $1",
            actor_external_id,
        )
        if not actor:
            return {"error": f"Actor {actor_external_id} not found"}

        actor_meta = actor["metadata"] if isinstance(actor["metadata"], dict) else {}
        source_headcount = _estimate_headcount(actor_meta.get("tranche_effectif"))

        # Fetch all relations in the department for BFS
        all_relations = await conn.fetch(
            """
            SELECT r.source_actor_id, r.target_actor_id,
                   r.relation_type::text, r.subtype, r.confidence, r.weight,
                   a_src.external_id AS src_ext, a_src.name AS src_name,
                   a_src.metadata AS src_meta, a_src.type::text AS src_type,
                   a_tgt.external_id AS tgt_ext, a_tgt.name AS tgt_name,
                   a_tgt.metadata AS tgt_meta, a_tgt.type::text AS tgt_type
            FROM relations r
            JOIN actors a_src ON r.source_actor_id = a_src.id
            JOIN actors a_tgt ON r.target_actor_id = a_tgt.id
            WHERE (a_src.department_code = $1 OR a_tgt.department_code = $1)
            """,
            department_code,
        )

    # Build adjacency: actor_ext → [(peer_ext, relation_info)]
    adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    actor_info: dict[str, dict[str, Any]] = {}

    for row in all_relations:
        src_ext = row["src_ext"]
        tgt_ext = row["tgt_ext"]
        src_meta = row["src_meta"] if isinstance(row["src_meta"], dict) else {}
        tgt_meta = row["tgt_meta"] if isinstance(row["tgt_meta"], dict) else {}

        actor_info[src_ext] = {
            "name": row["src_name"],
            "type": row["src_type"],
            "headcount": _estimate_headcount(src_meta.get("tranche_effectif")),
            "metadata": src_meta,
        }
        actor_info[tgt_ext] = {
            "name": row["tgt_name"],
            "type": row["tgt_type"],
            "headcount": _estimate_headcount(tgt_meta.get("tranche_effectif")),
            "metadata": tgt_meta,
        }

        link_info = {
            "relation_type": row["relation_type"],
            "subtype": row["subtype"],
            "confidence": float(row["confidence"]),
            "weight": float(row["weight"] or 1.0),
        }

        adjacency[src_ext].append({"peer": tgt_ext, **link_info})
        adjacency[tgt_ext].append({"peer": src_ext, **link_info})

    # BFS cascade simulation
    visited: set[str] = {actor_external_id}
    cascade_paths: list[dict[str, Any]] = []
    queue: list[tuple[str, int, float]] = [(actor_external_id, 0, 1.0)]
    total_employment_at_risk = source_headcount

    while queue:
        current_ext, depth, propagation_factor = queue.pop(0)
        if depth >= max_depth:
            continue

        neighbors = adjacency.get(current_ext, [])
        for link in neighbors:
            peer_ext = link["peer"]
            if peer_ext in visited:
                continue

            peer_info = actor_info.get(peer_ext, {})
            if peer_info.get("type") not in ("enterprise", "sector"):
                continue  # only propagate to enterprises and sectors

            # Cascade probability via ML model (logistic regression on graph features)
            source_degree = len(adjacency.get(current_ext, []))
            target_degree = len(adjacency.get(peer_ext, []))
            current_meta = actor_info.get(current_ext, {}).get("metadata", {})
            peer_meta = actor_info.get(peer_ext, {}).get("metadata", {})
            src_naf = current_meta.get("naf", "")
            tgt_naf = peer_meta.get("naf", "")
            same_sector = bool(src_naf and tgt_naf and src_naf[:2] == tgt_naf[:2])

            cascade_prob = (
                predict_cascade_probability(
                    relation_confidence=link["confidence"],
                    source_headcount=source_headcount,
                    target_headcount=peer_info.get("headcount", 5),
                    depth=depth + 1,
                    source_degree=source_degree,
                    target_degree=target_degree,
                    same_sector=same_sector,
                    relation_weight=link["weight"],
                )
                * propagation_factor
            )
            if cascade_prob < 0.01:
                continue  # too small to matter

            visited.add(peer_ext)
            peer_headcount = peer_info.get("headcount", 5)
            impact_score = round(cascade_prob * (peer_headcount / max(source_headcount, 1)), 4)

            cascade_paths.append(
                {
                    "actor_external_id": peer_ext,
                    "actor_name": peer_info.get("name", peer_ext),
                    "actor_type": peer_info.get("type", "unknown"),
                    "depth": depth + 1,
                    "cascade_probability": round(cascade_prob, 4),
                    "impact_score": impact_score,
                    "estimated_headcount": peer_headcount,
                    "via_relation": link["subtype"],
                    "via_confidence": link["confidence"],
                }
            )
            total_employment_at_risk += int(peer_headcount * cascade_prob)

            queue.append((peer_ext, depth + 1, cascade_prob))

    # Sort by impact score descending
    cascade_paths.sort(key=lambda x: x["impact_score"], reverse=True)

    # Aggregate impact
    total_impact = sum(p["impact_score"] for p in cascade_paths)

    return {
        "source_actor": {
            "external_id": actor_external_id,
            "name": actor["name"],
            "estimated_headcount": source_headcount,
        },
        "department_code": department_code,
        "cascade_depth": max_depth,
        "affected_actors": len(cascade_paths),
        "cascade_paths": cascade_paths[:50],  # limit to top 50
        "total_impact_score": round(total_impact, 4),
        "employment_at_risk": total_employment_at_risk,
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PREDICTORS: dict[str, type[BasePredictor]] = {
    "cascade": CascadePredictor,
    # "institutional_link" removed: produced 7000+ speculative relations per dept
    "territorial_impact": TerritorialImpactPredictor,
}
