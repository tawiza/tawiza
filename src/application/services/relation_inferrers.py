"""Relation inferrers (Level 2) -- statistical correlation analysis.

Unlike L1 extractors which query the raw ``signals`` table, inferrers
operate on the already-persisted ``actors`` and ``relations`` tables to
discover higher-level patterns through statistical analysis.

All inferred relations have:
- relation_type = 'inferred'
- confidence in [0.40, 0.79]
- source_type = 'model'
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import unicodedata
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from itertools import combinations
from typing import Any

import asyncpg
from loguru import logger

from src.application.services._db_pool import acquire_conn


def _stable_uuid(prefix: str, key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"{prefix}:{key}")


def _actor_id(actor_type: str, external_id: str) -> uuid.UUID:
    return _stable_uuid("actor", f"{actor_type}:{external_id}")


def _relation_id(source_ext: str, target_ext: str, subtype: str) -> uuid.UUID:
    return _stable_uuid("relation", f"{source_ext}->{target_ext}:{subtype}")


# ---------------------------------------------------------------------------
# INSEE tranche_effectif → estimated headcount
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
    """Convert INSEE tranche_effectif code to estimated headcount."""
    if not tranche:
        return 5  # default: micro-enterprise
    return _TRANCHE_EFFECTIF.get(str(tranche).strip(), 5)


# ---------------------------------------------------------------------------
# Name normalisation helpers (for director link detection)
# ---------------------------------------------------------------------------

# Matches strict "NOM, Prenom" pattern:
# - Last name: 1-2 uppercase words (e.g. "DUPONT", "BEN SAID"), no digits
# - Comma + space separator
# - First name: 1-2 mixed-case words (e.g. "Jean", "Marie-Claire")
_PERSON_NAME_RE = re.compile(
    r"^([A-ZÀ-Ü][A-ZÀ-Üa-zà-ÿ-]*(?:\s[A-ZÀ-Ü][A-ZÀ-Üa-zà-ÿ-]*)?)"
    r",\s*"
    r"([A-ZÀ-Üa-zà-ÿ][A-Za-zÀ-ÿ-]*(?:\s[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ-]*)?)$"
)

# Corporate keywords that disqualify a commercant from being a person name.
# Matched as whole words (word-boundary check) to avoid false positives
# like "sa" matching inside "ABBASSA".
_CORPORATE_KEYWORDS_RE = re.compile(
    r"\b(?:"
    r"sarl|sas|eurl|sci|selarl|scp|snc"
    r"|pharmacie|garage|restaurant|hotel|cafe|bar"
    r"|boulangerie|institut|cabinet|societe|fils"
    r"|association|cooperative|mutuelle|fondation"
    r")\b",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    """Normalize a person name: lowercase, strip accents, collapse spaces."""
    name = name.lower().strip()
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = " ".join(name.split())
    return name if len(name) >= 3 else ""


def _is_person_name(commercant: str) -> bool:
    """Heuristic: return True if *commercant* looks like a person name.

    BODACC ``commercant`` is a person name when the format is
    ``NOM, Prenom`` (uppercase last name, comma, then first name).
    Rejects entries containing corporate keywords or multiple commas
    (which indicate business name pairs like "ENSEIGNE, RAISON SOCIALE").
    """
    text = commercant.strip()
    # Reject if contains more than one comma (business name pairs)
    if text.count(",") != 1:
        return False
    # Reject if any corporate keyword in the text (word-boundary match)
    if _CORPORATE_KEYWORDS_RE.search(text):
        return False
    return bool(_PERSON_NAME_RE.match(text))


def _extract_person_from_listepersonnes(lp_raw: str) -> tuple[str, str]:
    """Parse the ``listepersonnes`` JSON string from BODACC.

    Returns ``(full_name, siren)`` where *siren* is derived from
    ``numeroIdentification`` (RCS number with spaces removed).
    Returns empty strings on failure.
    """
    try:
        lp = json.loads(lp_raw) if isinstance(lp_raw, str) else lp_raw
        personne = lp.get("personne", lp)
        nom = personne.get("nom", "")
        prenom = personne.get("prenom", "").split(",")[0].strip()
        full_name = f"{nom} {prenom}".strip()

        # RCS number without spaces = SIREN (9 digits)
        num_id = (
            personne.get("numeroImmatriculation", {})
            .get("numeroIdentification", "")
            .replace(" ", "")
        )
        siren = num_id if len(num_id) == 9 and num_id.isdigit() else ""
        return full_name, siren
    except Exception:
        return "", ""


# ---------------------------------------------------------------------------
# Haversine distance helper
# ---------------------------------------------------------------------------


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two GPS points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseInferrer(ABC):
    """Base class for L2 relation inferrers.

    Inferrers query existing actors/relations to discover patterns.
    They return the same dict format as extractors for uniform upsert.
    """

    source_name: str = ""

    @abstractmethod
    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        """Return ``{"actors": [...], "relations": [...]}``."""
        ...


# ---------------------------------------------------------------------------
# 1. SectorConcentrationInferrer
# ---------------------------------------------------------------------------


class SectorConcentrationInferrer(BaseInferrer):
    """Detect over-represented sectors in a department.

    Algorithm:
    1. Count enterprises per NAF sector in the department
    2. Calculate each sector's share of total enterprises
    3. If share > CONCENTRATION_THRESHOLD → inferred "sector_dominance" relation
    4. Confidence scales linearly: 15% share → 0.45, 50%+ share → 0.79

    Creates: sector → territory "sector_dominance" (inferred)
    """

    source_name = "sector_concentration"

    CONCENTRATION_THRESHOLD = 0.10  # 10% minimum to be "concentrated"

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # Count enterprises per sector in this department
            rows = await conn.fetch(
                """
                SELECT
                    a_sec.external_id AS sector_ext_id,
                    a_sec.name AS sector_name,
                    a_sec.metadata AS sector_metadata,
                    COUNT(DISTINCT a_ent.id) AS enterprise_count
                FROM relations r
                JOIN actors a_ent ON r.source_actor_id = a_ent.id
                JOIN actors a_sec ON r.target_actor_id = a_sec.id
                WHERE r.subtype = 'belongs_to_sector'
                  AND a_ent.department_code = $1
                  AND a_ent.type = 'enterprise'
                  AND a_sec.type = 'sector'
                GROUP BY a_sec.external_id, a_sec.name, a_sec.metadata
                ORDER BY enterprise_count DESC
                """,
                department_code,
            )

            total_enterprises = await conn.fetchval(
                """
                SELECT COUNT(*) FROM actors
                WHERE department_code = $1 AND type = 'enterprise'
                """,
                department_code,
            )

        if not rows or not total_enterprises or total_enterprises == 0:
            logger.info("SectorConcentrationInferrer: no data for dept {}", department_code)
            return {"actors": [], "relations": []}

        territory_ext_id = f"DEPT:{department_code}"

        for row in rows:
            sector_ext_id = row["sector_ext_id"]
            count = row["enterprise_count"]
            share = count / total_enterprises

            if share < self.CONCENTRATION_THRESHOLD:
                continue

            # Confidence: linear scale from 0.45 (at threshold) to 0.79 (at 50%+)
            confidence = min(0.45 + (share - self.CONCENTRATION_THRESHOLD) * 0.85, 0.79)
            confidence = round(confidence, 3)

            # Weight proportional to concentration
            weight = round(share * 10, 2)

            rel_id = _relation_id(sector_ext_id, territory_ext_id, "sector_dominance")
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": sector_ext_id,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "inferred",
                    "subtype": "sector_dominance",
                    "confidence": confidence,
                    "weight": weight,
                    "evidence": {
                        "source": "sector_concentration_model",
                        "method": "statistical_share",
                        "enterprise_count": count,
                        "total_enterprises": total_enterprises,
                        "share_pct": round(share * 100, 1),
                        "department": department_code,
                        "sector": sector_ext_id,
                    },
                    "source_type": "model",
                    "source_ref": f"inferrer:sector_concentration:{sector_ext_id}:{department_code}",
                }
            )

        logger.info(
            "SectorConcentrationInferrer dept={}: {} sector_dominance relations",
            department_code,
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# 2. EmploymentWeightInferrer
# ---------------------------------------------------------------------------


class EmploymentWeightInferrer(BaseInferrer):
    """Analyze the relative employment weight of enterprises.

    Algorithm:
    1. Fetch all enterprises in the department with tranche_effectif
    2. Estimate total employment from tranche codes
    3. If an enterprise represents > WEIGHT_THRESHOLD of total employment
       → inferred "employment_anchor" relation (enterprise → territory)
    4. Confidence scales with employment share

    Creates: enterprise → territory "employment_anchor" (inferred)
    """

    source_name = "employment_weight"

    WEIGHT_THRESHOLD = 0.02  # 2% of dept employment = significant employer

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT id, external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'enterprise'
                """,
                department_code,
            )

        if not rows:
            return {"actors": [], "relations": []}

        # Estimate employment per enterprise
        enterprise_employment: list[tuple[dict, int]] = []
        total_employment = 0

        for row in rows:
            meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
            tranche = meta.get("tranche_effectif")
            headcount = _estimate_headcount(tranche)
            enterprise_employment.append((dict(row), headcount))
            total_employment += headcount

        if total_employment == 0:
            return {"actors": [], "relations": []}

        territory_ext_id = f"DEPT:{department_code}"

        for row_dict, headcount in enterprise_employment:
            share = headcount / total_employment
            if share < self.WEIGHT_THRESHOLD:
                continue

            ent_ext_id = row_dict["external_id"]

            # Confidence: 0.45 at threshold, up to 0.79 at 20%+
            confidence = min(0.45 + (share - self.WEIGHT_THRESHOLD) * 1.9, 0.79)
            confidence = round(confidence, 3)

            weight = round(share * 20, 2)

            rel_id = _relation_id(ent_ext_id, territory_ext_id, "employment_anchor")
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": ent_ext_id,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "inferred",
                    "subtype": "employment_anchor",
                    "confidence": confidence,
                    "weight": weight,
                    "evidence": {
                        "source": "employment_weight_model",
                        "method": "tranche_effectif_estimation",
                        "estimated_headcount": headcount,
                        "total_dept_employment": total_employment,
                        "share_pct": round(share * 100, 2),
                        "department": department_code,
                        "enterprise": ent_ext_id,
                        "enterprise_name": row_dict["name"],
                    },
                    "source_type": "model",
                    "source_ref": f"inferrer:employment_weight:{ent_ext_id}:{department_code}",
                }
            )

        logger.info(
            "EmploymentWeightInferrer dept={}: {} employment_anchor relations (total_employment={})",
            department_code,
            len(relations),
            total_employment,
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# 3. GeographicClusterInferrer
# ---------------------------------------------------------------------------


class GeographicClusterInferrer(BaseInferrer):
    """Identify geographic clusters of enterprises in the same sector.

    Algorithm:
    1. Group enterprises by (postal_code, NAF_section) within the department
    2. If a group has >= CLUSTER_MIN_SIZE enterprises → create a cluster
    3. Create a virtual "cluster" actor and link enterprises to it
    4. Confidence scales with cluster size

    Creates:
    - New "sector" actor: CLUSTER:{dept}:{naf}:{cp}
    - enterprise → cluster "cluster_member" (inferred)
    """

    source_name = "geographic_cluster"

    CLUSTER_MIN_SIZE = 3  # minimum enterprises to form a cluster

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # Fetch enterprises with their sector and postal code
            rows = await conn.fetch(
                """
                SELECT
                    a_ent.external_id AS ent_ext_id,
                    a_ent.name AS ent_name,
                    a_ent.metadata AS ent_metadata,
                    a_sec.external_id AS sector_ext_id,
                    a_sec.name AS sector_name
                FROM relations r
                JOIN actors a_ent ON r.source_actor_id = a_ent.id
                JOIN actors a_sec ON r.target_actor_id = a_sec.id
                WHERE r.subtype = 'belongs_to_sector'
                  AND a_ent.department_code = $1
                  AND a_ent.type = 'enterprise'
                  AND a_sec.type = 'sector'
                """,
                department_code,
            )

        if not rows:
            return {"actors": [], "relations": []}

        # Group by (postal_code, naf_section)
        # NAF section = first 2 chars of NAF code (e.g., "47" from "47.11Z")
        clusters: dict[str, list[dict]] = defaultdict(list)

        for row in rows:
            meta = row["ent_metadata"] if isinstance(row["ent_metadata"], dict) else {}
            cp = meta.get("code_postal", "")
            sector_ext = row["sector_ext_id"]  # e.g., NAF:47.11Z

            # Extract NAF section (first 2 digits)
            naf_code = sector_ext.replace("NAF:", "") if sector_ext.startswith("NAF:") else ""
            naf_section = naf_code[:2] if len(naf_code) >= 2 else naf_code

            if not cp or not naf_section:
                continue

            cluster_key = f"{cp}:{naf_section}"
            clusters[cluster_key].append(
                {
                    "ent_ext_id": row["ent_ext_id"],
                    "ent_name": row["ent_name"],
                    "sector_ext_id": sector_ext,
                    "sector_name": row["sector_name"],
                    "cp": cp,
                    "naf_section": naf_section,
                }
            )

        # Create cluster actors and relations for groups above threshold
        for cluster_key, members in clusters.items():
            if len(members) < self.CLUSTER_MIN_SIZE:
                continue

            cp, naf_section = cluster_key.split(":", 1)
            cluster_ext_id = f"CLUSTER:{department_code}:{naf_section}:{cp}"
            sector_name = members[0]["sector_name"]
            cluster_name = f"Cluster {sector_name} ({cp})"

            # Create cluster actor (type=sector for graph visualization)
            actors[cluster_ext_id] = {
                "id": str(_actor_id("sector", cluster_ext_id)),
                "type": "sector",
                "external_id": cluster_ext_id,
                "name": cluster_name,
                "department_code": department_code,
                "metadata": {
                    "cluster": True,
                    "naf_section": naf_section,
                    "postal_code": cp,
                    "member_count": len(members),
                },
            }

            # Confidence scales with cluster size: 3→0.45, 10+→0.75
            base_confidence = min(0.40 + len(members) * 0.05, 0.75)
            base_confidence = round(base_confidence, 3)

            # Link each enterprise to the cluster
            for member in members:
                ent_ext_id = member["ent_ext_id"]
                rel_id = _relation_id(ent_ext_id, cluster_ext_id, "cluster_member")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": ent_ext_id,
                        "target_actor_external_id": cluster_ext_id,
                        "relation_type": "inferred",
                        "subtype": "cluster_member",
                        "confidence": base_confidence,
                        "weight": 1.0,
                        "evidence": {
                            "source": "geographic_cluster_model",
                            "method": "postal_code_naf_grouping",
                            "cluster_key": cluster_key,
                            "cluster_size": len(members),
                            "postal_code": cp,
                            "naf_section": naf_section,
                            "department": department_code,
                        },
                        "source_type": "model",
                        "source_ref": f"inferrer:geographic_cluster:{cluster_ext_id}:{ent_ext_id}",
                    }
                )

        logger.info(
            "GeographicClusterInferrer dept={}: {} clusters, {} cluster_member relations",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# 4. SocialLinkInferrer
# ---------------------------------------------------------------------------


class SocialLinkInferrer(BaseInferrer):
    """Infer links between associations and sectors/enterprises.

    Algorithm:
    1. Fetch associations in the department that have NAF codes
    2. Fetch sector memberships (belongs_to_sector relations)
    3. For each association with a matching NAF, find enterprises in the same sector
    4. If sector has >= 2 enterprises → create social_link (association → sector)
    5. For top 5 employers (headcount >= 10) → create social_proximity (association → enterprise)

    Creates:
    - association → sector  "social_link"     (inferred)
    - association → enterprise "social_proximity" (inferred)
    """

    source_name = "social_link"

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # Fetch associations in department with their metadata (NAF codes)
            assoc_rows = await conn.fetch(
                """
                SELECT id, external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'association'
                """,
                department_code,
            )

            # Fetch sector memberships: enterprise → sector
            sector_rows = await conn.fetch(
                """
                SELECT
                    a_ent.external_id  AS ent_ext_id,
                    a_ent.metadata     AS ent_metadata,
                    a_sec.external_id  AS sector_ext_id,
                    a_sec.name         AS sector_name
                FROM relations r
                JOIN actors a_ent ON r.source_actor_id = a_ent.id
                JOIN actors a_sec ON r.target_actor_id = a_sec.id
                WHERE r.subtype = 'belongs_to_sector'
                  AND a_ent.department_code = $1
                  AND a_ent.type = 'enterprise'
                  AND a_sec.type = 'sector'
                """,
                department_code,
            )

        if not assoc_rows or not sector_rows:
            logger.info("SocialLinkInferrer: no data for dept {}", department_code)
            return {"actors": [], "relations": []}

        # Build sector → list of (enterprise_ext_id, headcount)
        sector_enterprises: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for row in sector_rows:
            meta = row["ent_metadata"] if isinstance(row["ent_metadata"], dict) else {}
            hc = _estimate_headcount(meta.get("tranche_effectif"))
            sector_enterprises[row["sector_ext_id"]].append((row["ent_ext_id"], hc))

        for assoc in assoc_rows:
            assoc_ext_id = assoc["external_id"]
            meta = assoc["metadata"] if isinstance(assoc["metadata"], dict) else {}
            naf_code = meta.get("naf", "")
            if not naf_code:
                continue

            # Find matching sector by NAF prefix
            matching_sector = f"NAF:{naf_code}"
            ent_list = sector_enterprises.get(matching_sector, [])

            # social_link: association → sector  (if >= 2 enterprises in sector)
            if len(ent_list) >= 2:
                # Confidence: 0.45 base, scales up to 0.70 with more enterprises
                confidence = min(0.45 + len(ent_list) * 0.01, 0.70)
                confidence = round(confidence, 3)

                rel_id = _relation_id(assoc_ext_id, matching_sector, "social_link")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": assoc_ext_id,
                        "target_actor_external_id": matching_sector,
                        "relation_type": "inferred",
                        "subtype": "social_link",
                        "confidence": confidence,
                        "weight": round(len(ent_list) / 10, 2),
                        "evidence": {
                            "source": "social_link_model",
                            "method": "naf_sector_matching",
                            "association": assoc_ext_id,
                            "association_name": assoc["name"],
                            "sector": matching_sector,
                            "enterprises_in_sector": len(ent_list),
                            "department": department_code,
                        },
                        "source_type": "model",
                        "source_ref": f"inferrer:social_link:{assoc_ext_id}:{matching_sector}",
                    }
                )

            # social_proximity: association → enterprise (top 5 employers with hc >= 10)
            large_employers = [(ext_id, hc) for ext_id, hc in ent_list if hc >= 10]
            large_employers.sort(key=lambda x: x[1], reverse=True)

            for ent_ext_id, hc in large_employers[:5]:
                # Confidence: 0.40 base, scales up to 0.65 with headcount
                confidence = min(0.40 + (hc / 5000) * 0.25, 0.65)
                confidence = round(confidence, 3)

                rel_id = _relation_id(assoc_ext_id, ent_ext_id, "social_proximity")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": assoc_ext_id,
                        "target_actor_external_id": ent_ext_id,
                        "relation_type": "inferred",
                        "subtype": "social_proximity",
                        "confidence": confidence,
                        "weight": round(hc / 100, 2),
                        "evidence": {
                            "source": "social_link_model",
                            "method": "employer_proximity",
                            "association": assoc_ext_id,
                            "enterprise": ent_ext_id,
                            "enterprise_headcount": hc,
                            "department": department_code,
                        },
                        "source_type": "model",
                        "source_ref": f"inferrer:social_link:{assoc_ext_id}:{ent_ext_id}",
                    }
                )

        logger.info(
            "SocialLinkInferrer dept={}: {} relations (social_link + social_proximity)",
            department_code,
            len(relations),
        )
        return {"actors": [], "relations": relations}


# ---------------------------------------------------------------------------
# 5. FinancialLinkInferrer
# ---------------------------------------------------------------------------


class FinancialLinkInferrer(BaseInferrer):
    """Infer bank/financial institution → enterprise links by enterprise size.

    Algorithm:
    1. Fetch financial actors and enterprises in the department
    2. For each (financial, enterprise) pair where headcount >= 15
    3. Create likely_finances relation with confidence scaling by headcount

    Creates: financial → enterprise "likely_finances" (inferred)
    """

    source_name = "financial_link"

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            financial_rows = await conn.fetch(
                """
                SELECT id, external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'financial'
                """,
                department_code,
            )

            enterprise_rows = await conn.fetch(
                """
                SELECT id, external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'enterprise'
                """,
                department_code,
            )

        if not financial_rows or not enterprise_rows:
            logger.info("FinancialLinkInferrer: no data for dept {}", department_code)
            return {"actors": [], "relations": []}

        for fin in financial_rows:
            fin_ext_id = fin["external_id"]
            relations_for_fin = 0

            for ent in enterprise_rows:
                if relations_for_fin >= 50:
                    break
                ent_ext_id = ent["external_id"]
                meta = ent["metadata"] if isinstance(ent["metadata"], dict) else {}
                hc = _estimate_headcount(meta.get("tranche_effectif"))

                if hc < 15:
                    continue

                # Confidence: 0.40 base + scale by headcount, capped at 0.70
                confidence = min(0.40 + (hc / 5000) * 0.30, 0.70)
                confidence = round(confidence, 3)

                weight = round(hc / 100, 2)

                rel_id = _relation_id(fin_ext_id, ent_ext_id, "likely_finances")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": fin_ext_id,
                        "target_actor_external_id": ent_ext_id,
                        "relation_type": "inferred",
                        "subtype": "likely_finances",
                        "confidence": confidence,
                        "weight": weight,
                        "evidence": {
                            "source": "financial_link_model",
                            "method": "size_based_banking_inference",
                            "financial_actor": fin_ext_id,
                            "financial_name": fin["name"],
                            "enterprise": ent_ext_id,
                            "enterprise_name": ent["name"],
                            "enterprise_headcount": hc,
                            "department": department_code,
                        },
                        "source_type": "model",
                        "source_ref": f"inferrer:financial_link:{fin_ext_id}:{ent_ext_id}",
                    }
                )
                relations_for_fin += 1

        logger.info(
            "FinancialLinkInferrer dept={}: {} likely_finances relations",
            department_code,
            len(relations),
        )
        return {"actors": [], "relations": relations}


# ---------------------------------------------------------------------------
# 6. FormationLinkInferrer
# ---------------------------------------------------------------------------


class FormationLinkInferrer(BaseInferrer):
    """Infer training links between formation actors, sectors, and enterprises.

    Algorithm:
    1. Fetch formation actors in the department
    2. Identify top sectors by enterprise count (>= 3 enterprises, top 10)
    3. For each formation: create trains_sector (formation → sector)
    4. For each formation: create likely_trains (formation → enterprise) for large employers

    Creates:
    - formation → sector     "trains_sector"  (inferred)
    - formation → enterprise "likely_trains"   (inferred)
    """

    source_name = "formation_link"

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            formation_rows = await conn.fetch(
                """
                SELECT id, external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'formation'
                """,
                department_code,
            )

            # Top sectors by enterprise count (>= 3 enterprises)
            top_sectors = await conn.fetch(
                """
                SELECT
                    a_sec.external_id AS sector_ext_id,
                    a_sec.name        AS sector_name,
                    COUNT(DISTINCT a_ent.id) AS ent_count
                FROM relations r
                JOIN actors a_ent ON r.source_actor_id = a_ent.id
                JOIN actors a_sec ON r.target_actor_id = a_sec.id
                WHERE r.subtype = 'belongs_to_sector'
                  AND a_ent.department_code = $1
                  AND a_ent.type = 'enterprise'
                  AND a_sec.type = 'sector'
                GROUP BY a_sec.external_id, a_sec.name
                HAVING COUNT(DISTINCT a_ent.id) >= 3
                ORDER BY ent_count DESC
                LIMIT 10
                """,
                department_code,
            )

            enterprise_rows = await conn.fetch(
                """
                SELECT id, external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'enterprise'
                """,
                department_code,
            )

        if not formation_rows:
            logger.info("FormationLinkInferrer: no formation actors for dept {}", department_code)
            return {"actors": [], "relations": []}

        for formation in formation_rows:
            form_ext_id = formation["external_id"]

            # trains_sector: formation → sector (for top sectors)
            for sector in top_sectors:
                sector_ext_id = sector["sector_ext_id"]
                ent_count = sector["ent_count"]

                # Confidence: 0.40 base + 0.02 per enterprise, capped at 0.65
                confidence = min(0.40 + ent_count * 0.02, 0.65)
                confidence = round(confidence, 3)

                rel_id = _relation_id(form_ext_id, sector_ext_id, "trains_sector")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": form_ext_id,
                        "target_actor_external_id": sector_ext_id,
                        "relation_type": "inferred",
                        "subtype": "trains_sector",
                        "confidence": confidence,
                        "weight": round(ent_count / 10, 2),
                        "evidence": {
                            "source": "formation_link_model",
                            "method": "sector_demand_inference",
                            "formation": form_ext_id,
                            "formation_name": formation["name"],
                            "sector": sector_ext_id,
                            "sector_name": sector["sector_name"],
                            "enterprises_in_sector": ent_count,
                            "department": department_code,
                        },
                        "source_type": "model",
                        "source_ref": f"inferrer:formation_link:{form_ext_id}:{sector_ext_id}",
                    }
                )

            # likely_trains: formation → enterprise (for large employers, hc >= 50)
            for ent in enterprise_rows:
                ent_ext_id = ent["external_id"]
                meta = ent["metadata"] if isinstance(ent["metadata"], dict) else {}
                hc = _estimate_headcount(meta.get("tranche_effectif"))

                if hc < 50:
                    continue

                # Confidence: 0.40 base + hc * 0.0005, capped at 0.60
                confidence = min(0.40 + hc * 0.0005, 0.60)
                confidence = round(confidence, 3)

                rel_id = _relation_id(form_ext_id, ent_ext_id, "likely_trains")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": form_ext_id,
                        "target_actor_external_id": ent_ext_id,
                        "relation_type": "inferred",
                        "subtype": "likely_trains",
                        "confidence": confidence,
                        "weight": round(hc / 100, 2),
                        "evidence": {
                            "source": "formation_link_model",
                            "method": "employer_training_demand",
                            "formation": form_ext_id,
                            "formation_name": formation["name"],
                            "enterprise": ent_ext_id,
                            "enterprise_name": ent["name"],
                            "enterprise_headcount": hc,
                            "department": department_code,
                        },
                        "source_type": "model",
                        "source_ref": f"inferrer:formation_link:{form_ext_id}:{ent_ext_id}",
                    }
                )

        logger.info(
            "FormationLinkInferrer dept={}: {} relations (trains_sector + likely_trains)",
            department_code,
            len(relations),
        )
        return {"actors": [], "relations": relations}


# ---------------------------------------------------------------------------
# 7. SupplyChainInferrer
# ---------------------------------------------------------------------------


# CPV code compatibility: key = buyer CPV prefix (2 digits),
# value = list of likely supplier CPV prefixes.
class SupplyChainInferrer(BaseInferrer):
    """Detect enterprises sharing the same public buyer via BOAMP data.

    Algorithm (V2 — real co-attribution, no CPV heuristics):
    1. Query existing ``awarded_contract`` relations (L1, from BoampExtractor)
    2. Group suppliers (target actors) by their buyer (source actor)
    3. For buyers with 2+ suppliers, create ``co_supplier`` relations
       between each pair of suppliers

    This is high-value: enterprises that supply the same public buyer
    are in the same market ecosystem.  The relation is factual (based
    on real public procurement awards) not speculative.

    Confidence scales with the number of shared buyers:
    - 1 shared buyer: 0.70
    - 2 shared buyers: 0.80
    - 3+ shared buyers: 0.85

    Creates: enterprise <-> enterprise "co_supplier" (inferred)
    """

    source_name = "supply_chain"

    MAX_SUPPLIERS_PER_BUYER = 20  # cap to avoid combinatorial explosion

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # Get awarded_contract relations: source = buyer, target = supplier
            rows = await conn.fetch(
                """
                SELECT
                    a_buyer.external_id AS buyer_ext,
                    a_buyer.name AS buyer_name,
                    a_sup.external_id AS supplier_ext,
                    a_sup.name AS supplier_name
                FROM relations r
                JOIN actors a_buyer ON r.source_actor_id = a_buyer.id
                JOIN actors a_sup ON r.target_actor_id = a_sup.id
                WHERE r.subtype = 'awarded_contract'
                  AND (a_buyer.department_code = $1 OR a_sup.department_code = $1)
                """,
                department_code,
            )

        if not rows:
            logger.info("SupplyChainInferrer V2: no awarded_contract for dept {}", department_code)
            return {"actors": [], "relations": []}

        # Group: buyer -> list of (supplier_ext, supplier_name)
        buyer_suppliers: dict[str, list[tuple[str, str]]] = defaultdict(list)
        buyer_names: dict[str, str] = {}
        for row in rows:
            buyer_ext = row["buyer_ext"]
            buyer_names[buyer_ext] = row["buyer_name"]
            buyer_suppliers[buyer_ext].append((row["supplier_ext"], row["supplier_name"]))

        # Also track co-occurrence counts: pair -> set of shared buyers
        pair_buyers: dict[tuple[str, str], set[str]] = defaultdict(set)
        pair_names: dict[tuple[str, str], tuple[str, str]] = {}

        for buyer_ext, suppliers in buyer_suppliers.items():
            # Deduplicate and cap
            unique_suppliers = list(dict.fromkeys(suppliers))
            if len(unique_suppliers) < 2:
                continue
            capped = unique_suppliers[: self.MAX_SUPPLIERS_PER_BUYER]

            for (ext_a, name_a), (ext_b, name_b) in combinations(capped, 2):
                if ext_a == ext_b:
                    continue
                pair_key = tuple(sorted([ext_a, ext_b]))
                pair_buyers[pair_key].add(buyer_ext)
                pair_names[pair_key] = (
                    name_a if pair_key[0] == ext_a else name_b,
                    name_b if pair_key[1] == ext_b else name_a,
                )

        # Create co_supplier relations
        for pair_key, shared_buyers in pair_buyers.items():
            ext_a, ext_b = pair_key
            shared_count = len(shared_buyers)

            # Confidence scales with shared buyer count
            if shared_count >= 3:
                confidence = 0.85
            elif shared_count == 2:
                confidence = 0.80
            else:
                confidence = 0.70

            weight = round(min(shared_count / 3, 3.0), 2)
            names = pair_names.get(pair_key, ("", ""))
            buyer_list = [buyer_names.get(b, b) for b in sorted(shared_buyers)]

            rel_id = _relation_id(ext_a, ext_b, "co_supplier")
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": ext_a,
                    "target_actor_external_id": ext_b,
                    "relation_type": "inferred",
                    "subtype": "co_supplier",
                    "confidence": confidence,
                    "weight": weight,
                    "evidence": {
                        "source": "boamp_co_attribution",
                        "method": "shared_public_buyer",
                        "shared_buyers": buyer_list[:5],
                        "shared_buyer_count": shared_count,
                        "enterprise_a": names[0],
                        "enterprise_b": names[1],
                        "department": department_code,
                    },
                    "source_type": "model",
                    "source_ref": f"inferrer:supply_chain:{ext_a}:{ext_b}",
                }
            )

        logger.info(
            "SupplyChainInferrer V2 dept={}: {} buyers with 2+ suppliers, {} co_supplier relations",
            department_code,
            sum(1 for s in buyer_suppliers.values() if len(set(s)) >= 2),
            len(relations),
        )
        return {"actors": [], "relations": relations}


# ---------------------------------------------------------------------------
# 8. DirectorLinkInferrer
# ---------------------------------------------------------------------------


class DirectorLinkInferrer(BaseInferrer):
    """Detect enterprises sharing a director via SIRENE dirigeants data.

    Algorithm (V2 — real data, no BODACC parsing):
    1. Query enterprise actors that have ``metadata->'dirigeants'``
       (populated by SireneDirigeantsEnricher)
    2. For each dirigeant, build a matching key from
       (nom_normalized, prenoms_normalized, annee_naissance)
       — three-field matching virtually eliminates homonyms
    3. Map each key to the enterprise(s) where it appears
    4. For keys appearing in 2+ enterprises (cap at 10):
       create ``shared_director`` relations between each pair

    Confidence is high (0.85 base) because the source is official
    SIRENE registry data, not heuristic name parsing.

    Creates: enterprise <-> enterprise "shared_director" (inferred)
    """

    source_name = "director_link"

    MAX_ENTERPRISES_PER_DIRECTOR = 10

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # Fetch enterprises that have dirigeants in metadata
            actor_rows = await conn.fetch(
                """
                SELECT external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'enterprise'
                  AND metadata->'dirigeants' IS NOT NULL
                  AND jsonb_array_length(metadata->'dirigeants') > 0
                """,
                department_code,
            )

        if not actor_rows:
            logger.info(
                "DirectorLinkInferrer V2: no SIRENE dirigeants for dept {}", department_code
            )
            return {"actors": [], "relations": []}

        # Build mapping: director_key -> set of (external_id, enterprise_name, qualite)
        director_enterprises: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
        total_dirigeants = 0

        for row in actor_rows:
            ext_id = row["external_id"]
            ent_name = row["name"]
            raw_meta = row["metadata"]
            # asyncpg may return JSONB as string
            if isinstance(raw_meta, str):
                try:
                    meta = json.loads(raw_meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            elif isinstance(raw_meta, dict):
                meta = raw_meta
            else:
                meta = {}
            dirigeants = meta.get("dirigeants", [])

            for d in dirigeants:
                nom = (d.get("nom") or "").strip()
                prenoms = (d.get("prenoms") or "").strip()
                annee = d.get("annee_naissance")
                qualite = d.get("qualite", "")

                if not nom or not prenoms:
                    continue

                total_dirigeants += 1

                # Build matching key: normalized (nom, prenoms, annee)
                nom_n = _normalize_name(nom)
                prenoms_n = _normalize_name(prenoms)
                if not nom_n or not prenoms_n:
                    continue

                # Use annee_naissance for disambiguation when available
                key = f"{nom_n}|{prenoms_n}|{annee or ''}"
                director_enterprises[key].add((ext_id, ent_name, qualite))

        # Create shared_director relations for directors in 2+ enterprises
        shared_count_total = 0
        for director_key, enterprises in director_enterprises.items():
            ent_list = sorted(enterprises)
            if len(ent_list) < 2 or len(ent_list) > self.MAX_ENTERPRISES_PER_DIRECTOR:
                continue

            shared_count_total += 1
            shared_count = len(ent_list)

            # High confidence: SIRENE data is official registry
            # 0.85 base + 0.03 per extra enterprise, cap 0.95
            confidence = min(0.85 + (shared_count - 2) * 0.03, 0.95)
            confidence = round(confidence, 3)

            weight = round(shared_count / 3, 2)

            parts = director_key.split("|")
            director_display = f"{parts[0]} {parts[1]}" if len(parts) >= 2 else director_key

            for (ext_a, name_a, qual_a), (ext_b, name_b, qual_b) in combinations(ent_list, 2):
                rel_id = _relation_id(ext_a, ext_b, "shared_director")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": ext_a,
                        "target_actor_external_id": ext_b,
                        "relation_type": "inferred",
                        "subtype": "shared_director",
                        "confidence": confidence,
                        "weight": weight,
                        "evidence": {
                            "source": "sirene_dirigeants",
                            "method": "sirene_dirigeants_matching",
                            "director_key": director_key,
                            "director_display": director_display,
                            "qualite_a": qual_a,
                            "qualite_b": qual_b,
                            "enterprise_a": name_a,
                            "enterprise_b": name_b,
                            "shared_count": shared_count,
                            "department": department_code,
                        },
                        "source_type": "model",
                        "source_ref": f"inferrer:director_link:{director_key}:{ext_a}:{ext_b}",
                    }
                )

        logger.info(
            "DirectorLinkInferrer V2 dept={}: {} dirigeants scanned, "
            "{} shared across 2+ enterprises, {} relations",
            department_code,
            total_dirigeants,
            shared_count_total,
            len(relations),
        )
        return {"actors": [], "relations": relations}


# ---------------------------------------------------------------------------
# 9. ProximityInferrer
# ---------------------------------------------------------------------------


class ProximityInferrer(BaseInferrer):
    """Detect geographic proximity between actors using BAN geocoding.

    Algorithm:
    1. Query actors with address info (ville, commune, code_postal, adresse)
    2. Geocode each via BAN API (cap at 50 calls)
    3. For each pair within 500m: create ``geographic_proximity`` relation
    4. Confidence: 0.55 if < 200m, 0.35 if 200-500m
    5. Weight: 1 - distance/500 (closer = stronger)

    Creates: actor <-> actor "geographic_proximity" (inferred)
    """

    source_name = "proximity"

    MAX_GEOCODE_CALLS = 50
    MAX_DISTANCE_M = 500
    HIGH_CONFIDENCE_DISTANCE_M = 200
    GEOCODE_DELAY_S = 0.1  # 100ms between BAN API calls

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # Fetch actors that may have address metadata
            rows = await conn.fetch(
                """
                SELECT id, external_id, name, type::text AS actor_type, metadata
                FROM actors
                WHERE department_code = $1
                  AND metadata IS NOT NULL
                  AND (
                      metadata->>'ville' IS NOT NULL
                      OR metadata->>'commune' IS NOT NULL
                      OR metadata->>'code_postal' IS NOT NULL
                      OR metadata->>'adresse' IS NOT NULL
                      OR metadata->>'adresse_siege' IS NOT NULL
                  )
                """,
                department_code,
            )

        if not rows:
            logger.info("ProximityInferrer: no actors with address for dept {}", department_code)
            return {"actors": [], "relations": []}

        # Import BAN adapter lazily to avoid circular imports
        from src.infrastructure.datasources.adapters.ban import BanAdapter

        ban = BanAdapter()

        # Build geocoding queries and geocode each actor
        geocoded: list[dict[str, Any]] = []  # list of {ext_id, name, lat, lon}
        geocode_count = 0

        for row in rows:
            if geocode_count >= self.MAX_GEOCODE_CALLS:
                break

            # asyncpg returns jsonb as str or dict
            raw_meta = row["metadata"]
            if isinstance(raw_meta, str):
                try:
                    meta = json.loads(raw_meta)
                except (json.JSONDecodeError, TypeError):
                    continue
            elif isinstance(raw_meta, dict):
                meta = raw_meta
            else:
                continue

            # Build address query from available fields
            adresse = meta.get("adresse") or meta.get("adresse_siege") or ""
            code_postal = meta.get("code_postal") or ""
            ville = meta.get("ville") or meta.get("commune") or ""

            # Need at least city or postal code
            if not ville and not code_postal:
                continue

            query_str = f"{adresse} {code_postal} {ville}".strip()
            if not query_str or len(query_str) < 3:
                continue

            try:
                result = await ban.geocode(query_str)
                geocode_count += 1

                if result and result.get("lat") and result.get("lon"):
                    score = result.get("score", 0)
                    # Only keep results with reasonable geocoding quality
                    if score and score >= 0.4:
                        geocoded.append(
                            {
                                "external_id": row["external_id"],
                                "name": row["name"],
                                "lat": result["lat"],
                                "lon": result["lon"],
                                "geo_score": score,
                                "geo_label": result.get("label", ""),
                            }
                        )

                # Rate limit: 100ms delay between calls
                await asyncio.sleep(self.GEOCODE_DELAY_S)

            except Exception as exc:
                logger.debug(
                    "ProximityInferrer: geocode failed for '{}': {}",
                    query_str[:80],
                    exc,
                )
                continue

        logger.info(
            "ProximityInferrer dept={}: geocoded {}/{} actors ({} calls)",
            department_code,
            len(geocoded),
            len(rows),
            geocode_count,
        )

        if len(geocoded) < 2:
            return {"actors": [], "relations": []}

        # Compare all pairs for proximity
        for a, b in combinations(geocoded, 2):
            dist = _haversine(a["lat"], a["lon"], b["lat"], b["lon"])

            if dist > self.MAX_DISTANCE_M:
                continue

            # Confidence: 0.55 if < 200m, 0.35 if 200-500m
            if dist < self.HIGH_CONFIDENCE_DISTANCE_M:
                confidence = 0.55
            else:
                confidence = 0.35

            # Weight: 1 - distance/500 (closer = stronger)
            weight = round(1.0 - dist / self.MAX_DISTANCE_M, 3)
            weight = max(weight, 0.01)  # floor at 0.01

            ext_a = a["external_id"]
            ext_b = b["external_id"]

            rel_id = _relation_id(ext_a, ext_b, "geographic_proximity")
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": ext_a,
                    "target_actor_external_id": ext_b,
                    "relation_type": "inferred",
                    "subtype": "geographic_proximity",
                    "confidence": confidence,
                    "weight": weight,
                    "evidence": {
                        "source": "proximity_model",
                        "method": "ban_geocoding_haversine",
                        "distance_m": round(dist, 1),
                        "actor_a": a["name"],
                        "actor_b": b["name"],
                        "geo_label_a": a["geo_label"],
                        "geo_label_b": b["geo_label"],
                        "geo_score_a": a["geo_score"],
                        "geo_score_b": b["geo_score"],
                        "department": department_code,
                    },
                    "source_type": "model",
                    "source_ref": f"inferrer:proximity:{ext_a}:{ext_b}",
                }
            )

        logger.info(
            "ProximityInferrer dept={}: {} geographic_proximity relations from {} geocoded actors",
            department_code,
            len(relations),
            len(geocoded),
        )
        return {"actors": [], "relations": relations}


# ---------------------------------------------------------------------------
# 10. PoleMembershipInferrer
# ---------------------------------------------------------------------------

# NAF division (2 digits) -> NAF section letter.
# Source: INSEE nomenclature NAF Rev.2
# https://www.insee.fr/fr/information/2406147
_NAF_DIVISION_TO_SECTION: dict[str, str] = {
    "01": "A",
    "02": "A",
    "03": "A",
    "05": "B",
    "06": "B",
    "07": "B",
    "08": "B",
    "09": "B",
    "10": "C",
    "11": "C",
    "12": "C",
    "13": "C",
    "14": "C",
    "15": "C",
    "16": "C",
    "17": "C",
    "18": "C",
    "19": "C",
    "20": "C",
    "21": "C",
    "22": "C",
    "23": "C",
    "24": "C",
    "25": "C",
    "26": "C",
    "27": "C",
    "28": "C",
    "29": "C",
    "30": "C",
    "31": "C",
    "32": "C",
    "33": "C",
    "35": "D",
    "36": "E",
    "37": "E",
    "38": "E",
    "39": "E",
    "41": "F",
    "42": "F",
    "43": "F",
    "45": "G",
    "46": "G",
    "47": "G",
    "49": "H",
    "50": "H",
    "51": "H",
    "52": "H",
    "53": "H",
    "55": "I",
    "56": "I",
    "58": "J",
    "59": "J",
    "60": "J",
    "61": "J",
    "62": "J",
    "63": "J",
    "64": "K",
    "65": "K",
    "66": "K",
    "68": "L",
    "69": "M",
    "70": "M",
    "71": "M",
    "72": "M",
    "73": "M",
    "74": "M",
    "75": "M",
    "77": "N",
    "78": "N",
    "79": "N",
    "80": "N",
    "81": "N",
    "82": "N",
    "84": "O",
    "85": "P",
    "86": "Q",
    "87": "Q",
    "88": "Q",
    "90": "R",
    "91": "R",
    "92": "R",
    "93": "R",
    "94": "S",
    "95": "S",
    "96": "S",
    "97": "T",
    "98": "T",
    "99": "U",
}


def _naf_code_to_section(naf_code: str) -> str:
    """Convert a French NAF code (e.g. '62.01Z', '4711C') to its section letter.

    NAF codes have the format ``DD.DDL`` (e.g. ``62.01Z``).  The section is
    derived from the first two digits (division) via ``_NAF_DIVISION_TO_SECTION``.
    Returns empty string if the code cannot be parsed.
    """
    if not naf_code:
        return ""
    # Strip whitespace and extract digits
    cleaned = naf_code.strip().replace(".", "")
    # We need at least 2 digits to get the division
    digits = "".join(c for c in cleaned[:4] if c.isdigit())
    if len(digits) >= 2:
        division = digits[:2]
        return _NAF_DIVISION_TO_SECTION.get(division, "")
    return ""


# CPV code prefix (2 digits) -> approximate NAF section letter.
# Used as fallback for BOAMP enterprises that have cpv_code but no NAF.
_CPV_TO_NAF_SECTION: dict[str, str] = {
    "03": "A",  # Agriculture, fishing
    "09": "C",
    "14": "C",
    "15": "C",
    "16": "C",
    "18": "C",
    "19": "C",
    "22": "C",
    "24": "C",
    "30": "C",
    "31": "C",
    "33": "C",
    "34": "C",
    "35": "C",
    "38": "C",
    "39": "C",
    "42": "C",
    "43": "C",
    "44": "C",  # Manufacturing
    "45": "F",
    "50": "F",  # Construction
    "48": "J",
    "72": "J",  # ICT
    "60": "H",
    "63": "H",  # Transport
    "64": "D",  # Energy
    "66": "K",  # Finance
    "71": "M",
    "73": "M",  # Professional/Scientific
    "79": "R",  # Culture/Sport
    "85": "Q",  # Health
    "55": "I",  # Hospitality
}


def _normalize_sector_label(label: str) -> str:
    """Lowercase + strip accents for fuzzy sector comparison."""
    label = label.lower().strip()
    label = unicodedata.normalize("NFD", label)
    label = "".join(c for c in label if unicodedata.category(c) != "Mn")
    return label


def _extract_enterprise_naf_section(meta: dict[str, Any]) -> tuple[str, str]:
    """Derive the NAF section letter for an enterprise from its metadata.

    Tries multiple sources in order of reliability:
    1. ``naf_section`` (direct, if already set)
    2. ``naf`` or ``activite_principale`` (full NAF code -> division -> section)
    3. ``cpv_code`` (approximate CPV -> NAF mapping, lower confidence)

    Returns ``(section_letter, source)`` where *source* is one of
    ``"naf_section"``, ``"naf_code"``, ``"cpv_code"``, or ``""`` if not found.
    """
    # Source 1: direct naf_section field
    naf_section = str(meta.get("naf_section") or "").strip().upper()
    if len(naf_section) == 1 and naf_section.isalpha():
        return naf_section, "naf_section"

    # Source 2: derive from full NAF code
    naf_code = meta.get("naf") or meta.get("activite_principale") or ""
    if naf_code:
        section = _naf_code_to_section(str(naf_code))
        if section:
            return section, "naf_code"

    # Source 3: fallback from CPV code (approximate, for BOAMP enterprises)
    cpv_raw = meta.get("cpv_code", [])
    if isinstance(cpv_raw, str):
        try:
            cpv_raw = json.loads(cpv_raw)
        except (json.JSONDecodeError, TypeError):
            cpv_raw = [cpv_raw]
    if not isinstance(cpv_raw, list):
        cpv_raw = [str(cpv_raw)]
    for cpv_code in cpv_raw:
        cpv_prefix = str(cpv_code).strip()[:2]
        section = _CPV_TO_NAF_SECTION.get(cpv_prefix, "")
        if section:
            return section, "cpv_code"

    return "", ""


class PoleMembershipInferrer(BaseInferrer):
    """Match enterprises to competitiveness poles by NAF sector.

    Algorithm:
    1. Fetch competitiveness_pole actors in the department
    2. For each pole, read ``sectors`` from metadata -- these are **NAF section
       codes** (single uppercase letters like ``"C"``, ``"M"``, ``"Q"``), NOT
       textual keywords
    3. Fetch enterprises in the department
    4. For each enterprise, derive its NAF section via multiple sources:
       - ``naf_section`` field (direct)
       - ``naf`` / ``activite_principale`` (full NAF code -> division -> section)
       - ``cpv_code`` (approximate CPV -> NAF mapping, lower confidence)
    5. If the enterprise's NAF section is in the pole's sectors set
       -> create ``pole_member_inferred`` relation

    Creates: enterprise -> competitiveness_pole "pole_member_inferred" (inferred)
    """

    source_name = "pole_membership"

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            pole_rows = await conn.fetch(
                """
                SELECT external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'competitiveness_pole'
                """,
                department_code,
            )

            enterprise_rows = await conn.fetch(
                """
                SELECT external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'enterprise'
                """,
                department_code,
            )

        if not pole_rows or not enterprise_rows:
            logger.info(
                "PoleMembershipInferrer: no poles or enterprises for dept {}",
                department_code,
            )
            return {"actors": [], "relations": []}

        # Pre-process poles: extract NAF section codes from metadata.sectors
        poles: list[dict[str, Any]] = []
        for row in pole_rows:
            raw_meta = row["metadata"]
            if isinstance(raw_meta, str):
                try:
                    meta = json.loads(raw_meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            elif isinstance(raw_meta, dict):
                meta = raw_meta
            else:
                meta = {}

            raw_sectors = meta.get("sectors") or meta.get("secteurs") or []
            if isinstance(raw_sectors, str):
                # Sometimes stored as comma-separated string
                raw_sectors = [s.strip() for s in raw_sectors.split(",") if s.strip()]
            if not isinstance(raw_sectors, list):
                raw_sectors = []

            # Sectors are NAF section codes (single uppercase letters)
            naf_sections: set[str] = set()
            for s in raw_sectors:
                s = str(s).strip().upper()
                if len(s) == 1 and s.isalpha():
                    naf_sections.add(s)
                # else: could be a textual keyword -- ignore for now

            if not naf_sections:
                continue

            poles.append(
                {
                    "external_id": row["external_id"],
                    "name": row["name"],
                    "naf_sections": naf_sections,
                }
            )

        if not poles:
            logger.info(
                "PoleMembershipInferrer: no poles with NAF sector metadata for dept {}",
                department_code,
            )
            return {"actors": [], "relations": []}

        # Match enterprises to poles via NAF section — cap per pole
        _MAX_PER_POLE = 15

        # Build candidates per pole, scored by confidence
        for pole in poles:
            pole_ext_id = pole["external_id"]
            candidates: list[tuple[float, str, dict[str, Any], str, str]] = []

            for ent in enterprise_rows:
                raw_meta = ent["metadata"]
                if isinstance(raw_meta, str):
                    try:
                        meta = json.loads(raw_meta)
                    except (json.JSONDecodeError, TypeError):
                        continue
                elif isinstance(raw_meta, dict):
                    meta = raw_meta
                else:
                    continue

                ent_section, section_source = _extract_enterprise_naf_section(meta)
                if not ent_section or ent_section not in pole["naf_sections"]:
                    continue

                base_confidence = 0.35 if section_source == "cpv_code" else 0.50
                candidates.append(
                    (base_confidence, ent["external_id"], ent, ent_section, section_source)
                )

            # Sort by confidence desc, keep top N per pole
            candidates.sort(key=lambda x: x[0], reverse=True)
            for base_confidence, ent_ext_id, ent, ent_section, section_source in candidates[
                :_MAX_PER_POLE
            ]:
                rel_id = _relation_id(ent_ext_id, pole_ext_id, "pole_member_inferred")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": ent_ext_id,
                        "target_actor_external_id": pole_ext_id,
                        "relation_type": "inferred",
                        "subtype": "pole_member_inferred",
                        "confidence": base_confidence,
                        "weight": 0.4,
                        "evidence": {
                            "source": "pole_membership_model",
                            "method": "naf_section_direct_match",
                            "naf_section": ent_section,
                            "section_source": section_source,
                            "pole_sectors": sorted(pole["naf_sections"]),
                            "pole_name": pole["name"],
                            "enterprise": ent_ext_id,
                            "enterprise_name": ent["name"],
                            "department": department_code,
                        },
                        "source_type": "model",
                        "source_ref": (f"inferrer:pole_membership:{ent_ext_id}:{pole_ext_id}"),
                    }
                )

        logger.info(
            "PoleMembershipInferrer dept={}: {} pole_member_inferred relations "
            "(capped {}×pole, {} poles, {} enterprises)",
            department_code,
            len(relations),
            _MAX_PER_POLE,
            len(poles),
            len(enterprise_rows),
        )
        return {"actors": [], "relations": relations}


# ---------------------------------------------------------------------------
# 11. EPCIBelongsInferrer
# ---------------------------------------------------------------------------


class EPCIBelongsInferrer(BaseInferrer):
    """Match enterprises to EPCI collectivities via commune/postal code.

    Algorithm:
    1. Fetch collectivity actors (EPCIs) in the department
    2. For each EPCI, read ``communes`` from metadata (list of commune codes)
       and ``codes_postaux`` (list of postal codes, if present)
    3. Fetch enterprises in the department
    4. For each enterprise, extract ``commune_code`` or ``code_postal``
    5. If commune_code is in the EPCI's communes list -> confidence 0.65
    6. If postal code matches an EPCI's postal codes -> confidence 0.40
    7. Create ``belongs_to_epci_inferred`` relation

    Creates: enterprise -> collectivity "belongs_to_epci_inferred" (inferred)
    """

    source_name = "epci_belongs"

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            epci_rows = await conn.fetch(
                """
                SELECT external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'collectivity'
                """,
                department_code,
            )

            enterprise_rows = await conn.fetch(
                """
                SELECT external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'enterprise'
                """,
                department_code,
            )

        if not epci_rows or not enterprise_rows:
            logger.info(
                "EPCIBelongsInferrer: no EPCI or enterprises for dept {}",
                department_code,
            )
            return {"actors": [], "relations": []}

        # Pre-process EPCIs: build lookup structures
        epcis: list[dict[str, Any]] = []
        for row in epci_rows:
            raw_meta = row["metadata"]
            if isinstance(raw_meta, str):
                try:
                    meta = json.loads(raw_meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            elif isinstance(raw_meta, dict):
                meta = raw_meta
            else:
                meta = {}

            # Commune codes: list of INSEE commune codes (e.g. ["13001", "13055"])
            raw_communes = meta.get("communes") or []
            if isinstance(raw_communes, str):
                try:
                    raw_communes = json.loads(raw_communes)
                except (json.JSONDecodeError, TypeError):
                    raw_communes = [c.strip() for c in raw_communes.split(",") if c.strip()]
            commune_set = (
                {str(c).strip() for c in raw_communes if c}
                if isinstance(raw_communes, list)
                else set()
            )

            # Postal codes: may be stored separately or derivable from communes
            raw_postaux = meta.get("codes_postaux") or meta.get("postal_codes") or []
            if isinstance(raw_postaux, str):
                try:
                    raw_postaux = json.loads(raw_postaux)
                except (json.JSONDecodeError, TypeError):
                    raw_postaux = [p.strip() for p in raw_postaux.split(",") if p.strip()]
            postal_set = (
                {str(p).strip() for p in raw_postaux if p}
                if isinstance(raw_postaux, list)
                else set()
            )

            if not commune_set and not postal_set:
                continue

            epcis.append(
                {
                    "external_id": row["external_id"],
                    "name": row["name"],
                    "communes": commune_set,
                    "postal_codes": postal_set,
                }
            )

        if not epcis:
            logger.info(
                "EPCIBelongsInferrer: no EPCI with commune/postal metadata for dept {}",
                department_code,
            )
            return {"actors": [], "relations": []}

        # Match enterprises to EPCIs
        matched_count = 0
        for ent in enterprise_rows:
            raw_meta = ent["metadata"]
            if isinstance(raw_meta, str):
                try:
                    meta = json.loads(raw_meta)
                except (json.JSONDecodeError, TypeError):
                    continue
            elif isinstance(raw_meta, dict):
                meta = raw_meta
            else:
                continue

            commune_code = str(meta.get("commune_code") or meta.get("code_commune") or "").strip()
            postal_code = str(meta.get("code_postal") or meta.get("postal_code") or "").strip()

            if not commune_code and not postal_code:
                continue

            ent_ext_id = ent["external_id"]

            for epci in epcis:
                epci_ext_id = epci["external_id"]
                confidence = 0.0
                match_method = ""

                # Priority 1: exact commune code match
                if commune_code and commune_code in epci["communes"]:
                    confidence = 0.65
                    match_method = "commune_code_exact"
                # Priority 2: postal code match
                elif postal_code and epci["postal_codes"] and postal_code in epci["postal_codes"]:
                    confidence = 0.40
                    match_method = "postal_code_match"
                else:
                    continue

                rel_id = _relation_id(ent_ext_id, epci_ext_id, "belongs_to_epci_inferred")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": ent_ext_id,
                        "target_actor_external_id": epci_ext_id,
                        "relation_type": "inferred",
                        "subtype": "belongs_to_epci_inferred",
                        "confidence": confidence,
                        "weight": 0.5,
                        "evidence": {
                            "source": "epci_belongs_model",
                            "method": match_method,
                            "commune_code": commune_code,
                            "postal_code": postal_code,
                            "epci_name": epci["name"],
                            "enterprise": ent_ext_id,
                            "enterprise_name": ent["name"],
                            "department": department_code,
                        },
                        "source_type": "model",
                        "source_ref": (f"inferrer:epci_belongs:{ent_ext_id}:{epci_ext_id}"),
                    }
                )
                matched_count += 1
                # An enterprise can belong to only one EPCI in practice,
                # but we keep all matches (first match will have highest confidence)
                break

        logger.info(
            "EPCIBelongsInferrer dept={}: {} belongs_to_epci_inferred relations "
            "({} EPCIs, {} enterprises)",
            department_code,
            len(relations),
            len(epcis),
            len(enterprise_rows),
        )
        return {"actors": [], "relations": relations}


# ---------------------------------------------------------------------------
# 12. IncubatorMatchInferrer
# ---------------------------------------------------------------------------


def _parse_meta(raw: Any) -> dict[str, Any]:
    """Safely parse asyncpg metadata (may be str or dict)."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


class IncubatorMatchInferrer(BaseInferrer):
    """Match young/small enterprises to nearby incubators.

    Algorithm:
    1. Fetch incubator actors in the department
    2. For each incubator, extract ``themes`` and ``localisation`` from metadata
    3. Fetch enterprises whose metadata indicates a young company:
       - ``date_creation`` > 2020, OR
       - ``tranche_effectif`` indicates < 50 employees, OR
       - name/metadata contains "startup", "jeune", etc.
    4. For each young enterprise in the same department -> base relation
    5. If the incubator's themes match the enterprise's NAF sector,
       boost confidence

    Creates: enterprise -> incubator "incubated_by_inferred" (inferred)
    """

    source_name = "incubator_match"

    # Year threshold: companies created after this are considered "young"
    YOUNG_YEAR = 2020
    # Max headcount for a "young/small" company
    YOUNG_MAX_HEADCOUNT = 50
    # Keywords in name/metadata that suggest a young company
    _YOUNG_KEYWORDS = frozenset(["startup", "jeune", "incub", "pépinière", "pepiniere"])

    # Mapping: incubator theme keyword -> compatible NAF sections
    _THEME_TO_NAF: dict[str, list[str]] = {
        "numérique": ["J"],
        "numerique": ["J"],
        "digital": ["J"],
        "logiciel": ["J"],
        "cybersecurite": ["J"],
        "IA": ["J", "M"],
        "sante": ["Q", "M"],
        "biotech": ["M", "Q"],
        "biotechnologie": ["M", "Q"],
        "medtech": ["Q", "M"],
        "cleantech": ["D", "E"],
        "energie": ["D"],
        "agroalimentaire": ["A", "C"],
        "agriculture": ["A"],
        "industrie": ["C"],
        "aeronautique": ["C"],
        "spatial": ["C", "M"],
        "defense": ["C"],
        "construction": ["F"],
        "transport": ["H"],
        "mobilite": ["H"],
        "finance": ["K"],
        "fintech": ["K", "J"],
        "tourisme": ["I", "R"],
        "culture": ["R"],
        "commerce": ["G"],
        "recherche": ["M"],
    }

    async def infer(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            incubator_rows = await conn.fetch(
                """
                SELECT external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'incubator'
                """,
                department_code,
            )

            enterprise_rows = await conn.fetch(
                """
                SELECT external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'enterprise'
                """,
                department_code,
            )

        if not incubator_rows or not enterprise_rows:
            logger.info(
                "IncubatorMatchInferrer: no incubators or enterprises for dept {}",
                department_code,
            )
            return {"actors": [], "relations": []}

        # Pre-process incubators
        incubators: list[dict[str, Any]] = []
        for row in incubator_rows:
            meta = _parse_meta(row["metadata"])

            # Extract themes (list of keywords)
            raw_themes = meta.get("themes") or meta.get("domaines") or meta.get("secteurs") or []
            if isinstance(raw_themes, str):
                raw_themes = [t.strip() for t in raw_themes.split(",") if t.strip()]
            if not isinstance(raw_themes, list):
                raw_themes = []
            themes_normalized = [_normalize_sector_label(t) for t in raw_themes if t]

            # Compute compatible NAF sections from themes
            compatible_naf: set[str] = set()
            for theme in themes_normalized:
                for keyword, naf_sections in self._THEME_TO_NAF.items():
                    if _normalize_sector_label(
                        keyword
                    ) in theme or theme in _normalize_sector_label(keyword):
                        compatible_naf.update(naf_sections)

            incubators.append(
                {
                    "external_id": row["external_id"],
                    "name": row["name"],
                    "themes": themes_normalized,
                    "compatible_naf": compatible_naf,
                }
            )

        # Filter young/small enterprises
        young_enterprises: list[dict[str, Any]] = []
        for ent in enterprise_rows:
            meta = _parse_meta(ent["metadata"])
            is_young = False

            # Criterion 1: date_creation after YOUNG_YEAR
            date_creation = str(meta.get("date_creation") or "")
            if date_creation:
                # Accept formats: "2022", "2022-01-15", "15/01/2022"
                year_match = re.search(r"(20\d{2})", date_creation)
                if year_match:
                    year = int(year_match.group(1))
                    if year > self.YOUNG_YEAR:
                        is_young = True

            # Criterion 2: small headcount
            if not is_young:
                tranche = meta.get("tranche_effectif")
                headcount = _estimate_headcount(tranche)
                if headcount < self.YOUNG_MAX_HEADCOUNT:
                    is_young = True

            # Criterion 3: keyword in name or metadata
            if not is_young:
                search_text = (ent["name"] or "").lower()
                search_text += " " + str(meta.get("enseigne") or "").lower()
                search_text += " " + str(meta.get("nature") or "").lower()
                for kw in self._YOUNG_KEYWORDS:
                    if kw in search_text:
                        is_young = True
                        break

            if not is_young:
                continue

            # Extract NAF section for theme matching
            naf_section = str(meta.get("naf_section") or "").strip().upper()
            if not naf_section:
                naf_code = meta.get("activite_principale") or meta.get("naf") or ""
                if naf_code and len(naf_code) >= 1 and naf_code[0].isalpha():
                    naf_section = naf_code[0].upper()

            young_enterprises.append(
                {
                    "external_id": ent["external_id"],
                    "name": ent["name"],
                    "naf_section": naf_section,
                    "meta": meta,
                }
            )

        if not young_enterprises:
            logger.info(
                "IncubatorMatchInferrer: no young enterprises for dept {}",
                department_code,
            )
            return {"actors": [], "relations": []}

        # Match young enterprises to incubators — cap per incubator
        _MAX_PER_INCUBATOR = 8

        # Build candidates per incubator, scored by thematic relevance
        for incub in incubators:
            incub_ext_id = incub["external_id"]
            candidates: list[tuple[float, dict[str, Any], bool]] = []

            for ent in young_enterprises:
                ent_naf = ent["naf_section"]
                confidence = 0.35
                thematic_match = False
                if ent_naf and incub["compatible_naf"] and ent_naf in incub["compatible_naf"]:
                    confidence = 0.55
                    thematic_match = True
                candidates.append((confidence, ent, thematic_match))

            # Sort by confidence desc, keep top N
            candidates.sort(key=lambda x: x[0], reverse=True)
            for confidence, ent, thematic_match in candidates[:_MAX_PER_INCUBATOR]:
                ent_ext_id = ent["external_id"]
                rel_id = _relation_id(ent_ext_id, incub_ext_id, "incubated_by_inferred")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": ent_ext_id,
                        "target_actor_external_id": incub_ext_id,
                        "relation_type": "inferred",
                        "subtype": "incubated_by_inferred",
                        "confidence": confidence,
                        "weight": 0.3,
                        "evidence": {
                            "source": "incubator_match_model",
                            "method": (
                                "department_thematic_match"
                                if thematic_match
                                else "department_proximity"
                            ),
                            "thematic_match": thematic_match,
                            "enterprise_naf_section": ent["naf_section"],
                            "incubator_themes": incub["themes"][:10],
                            "incubator_name": incub["name"],
                            "enterprise": ent_ext_id,
                            "enterprise_name": ent["name"],
                            "department": department_code,
                        },
                        "source_type": "model",
                        "source_ref": (f"inferrer:incubator_match:{ent_ext_id}:{incub_ext_id}"),
                    }
                )

        logger.info(
            "IncubatorMatchInferrer dept={}: {} incubated_by_inferred relations "
            "(capped {}×incubator, {} incubators, {} young enterprises)",
            department_code,
            len(relations),
            _MAX_PER_INCUBATOR,
            len(incubators),
            len(young_enterprises),
        )
        return {"actors": [], "relations": relations}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

INFERRERS: dict[str, type[BaseInferrer]] = {
    "sector_concentration": SectorConcentrationInferrer,
    "employment_weight": EmploymentWeightInferrer,
    "geographic_cluster": GeographicClusterInferrer,
    # "social_link" removed: speculative, no real data behind it
    # "financial_link" removed: speculative, no real data behind it
    # "formation_link" removed: replaced by QualiopiExtractor (real data)
    "supply_chain": SupplyChainInferrer,
    "director_link": DirectorLinkInferrer,
    "proximity": ProximityInferrer,
    "pole_membership": PoleMembershipInferrer,
    "epci_belongs": EPCIBelongsInferrer,
    "incubator_match": IncubatorMatchInferrer,
}
