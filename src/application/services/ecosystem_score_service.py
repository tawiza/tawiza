"""Ecosystem maturity score -- 6-dimension composite score for territorial completeness.

Dimensions (weights):
  1. Tissu economique (25%) - enterprises, sectors, sector relations
  2. Structures support (20%) - poles, clusters, incubators, dev agencies
  3. Maillage institutionnel (15%) - institutions, collectivities, institutional relations
  4. Formation & recherche (15%) - formations, research labs, training relations
  5. Emploi & competences (15%) - employment basins, employment relations
  6. Foncier & infrastructure (10%) - economic zones, professional networks
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.application.services._db_pool import acquire_conn


async def compute_ecosystem_score(department_code: str) -> dict[str, Any]:
    """Compute the ecosystem maturity score for a department.

    Returns a dict with:
    - department_code: str
    - overall_score: float (0-100)
    - dimensions: list of 6 dimension dicts
    - actor_counts: dict of actor type -> count
    - relation_counts: dict of relation subtype -> count
    - recommendations: list of strings
    """
    logger.info("Computing ecosystem score for dept {}", department_code)

    async with acquire_conn() as conn:
        # Count actors by type
        actor_rows = await conn.fetch(
            """
            SELECT type::text, COUNT(*) as cnt
            FROM actors
            WHERE department_code = $1
            GROUP BY type
            """,
            department_code,
        )
        actor_counts: dict[str, int] = {row["type"]: row["cnt"] for row in actor_rows}

        # Count relations by subtype (join on source actor's department)
        relation_rows = await conn.fetch(
            """
            SELECT r.subtype, COUNT(*) as cnt
            FROM relations r
            JOIN actors a ON r.source_actor_id = a.id
            WHERE a.department_code = $1
            GROUP BY r.subtype
            """,
            department_code,
        )
        relation_counts: dict[str, int] = {row["subtype"]: row["cnt"] for row in relation_rows}

    # ------------------------------------------------------------------
    # Dimension 1: Tissu economique (25%)
    # Indicators: enterprise count, sector diversity, sector relations
    # ------------------------------------------------------------------
    enterprises = actor_counts.get("enterprise", 0)
    sectors = actor_counts.get("sector", 0)
    # Expected: a typical dept has 200+ enterprises mapped, 10+ sectors
    ent_score = min(enterprises / 200, 1.0) * 60  # max 60 pts from volume
    sector_score = min(sectors / 10, 1.0) * 25  # max 25 pts from diversity
    sector_rels = relation_counts.get("belongs_to_sector", 0) + relation_counts.get(
        "sector_dominance", 0
    )
    rel_score = min(sector_rels / 50, 1.0) * 15
    d1_score = ent_score + sector_score + rel_score

    # ------------------------------------------------------------------
    # Dimension 2: Structures support (20%)
    # Indicators: poles, clusters, incubators, dev agencies
    # ------------------------------------------------------------------
    poles = actor_counts.get("competitiveness_pole", 0)
    clusters = actor_counts.get("cluster", 0)
    incubators = actor_counts.get("incubator", 0)
    dev_agencies = actor_counts.get("dev_agency", 0)
    support_total = poles + clusters + incubators + dev_agencies
    # Expected: 5+ support structures
    d2_score = min(support_total / 5, 1.0) * 70
    # Bonus for diversity (having multiple types)
    support_types_present = sum(1 for x in [poles, clusters, incubators, dev_agencies] if x > 0)
    d2_score += (support_types_present / 4) * 30

    # ------------------------------------------------------------------
    # Dimension 3: Maillage institutionnel (15%)
    # Indicators: institutions, collectivities, institutional relations
    # ------------------------------------------------------------------
    institutions = actor_counts.get("institution", 0)
    collectivities = actor_counts.get("collectivity", 0)
    inst_rels = (
        relation_counts.get("likely_institution", 0)
        + relation_counts.get("administers_territory", 0)
        + relation_counts.get("belongs_to_epci", 0)
        + relation_counts.get("belongs_to_epci_inferred", 0)
    )
    d3_score = (
        min(institutions / 5, 1.0) * 30
        + min(collectivities / 3, 1.0) * 30
        + min(inst_rels / 20, 1.0) * 40
    )

    # ------------------------------------------------------------------
    # Dimension 4: Formation & recherche (15%)
    # Indicators: formations, research labs, training relations
    # ------------------------------------------------------------------
    formations = actor_counts.get("formation", 0)
    research_labs = actor_counts.get("research_lab", 0)
    formation_rels = (
        relation_counts.get("trains_sector", 0)
        + relation_counts.get("likely_trains", 0)
        + relation_counts.get("trains_in", 0)
    )
    d4_score = (
        min(formations / 3, 1.0) * 35
        + min(research_labs / 2, 1.0) * 35
        + min(formation_rels / 10, 1.0) * 30
    )

    # ------------------------------------------------------------------
    # Dimension 5: Emploi & competences (15%)
    # Indicators: employment basins, employment relations
    # ------------------------------------------------------------------
    employment_basins = actor_counts.get("employment_basin", 0)
    employment_rels = relation_counts.get("employment_anchor", 0) + relation_counts.get(
        "employment_weight", 0
    )
    d5_score = min(employment_basins / 2, 1.0) * 40 + min(employment_rels / 20, 1.0) * 60

    # ------------------------------------------------------------------
    # Dimension 6: Foncier & infrastructure (10%)
    # Indicators: economic zones, professional networks
    # ------------------------------------------------------------------
    economic_zones = actor_counts.get("economic_zone", 0)
    pro_networks = actor_counts.get("professional_network", 0)
    d6_score = min(economic_zones / 3, 1.0) * 50 + min(pro_networks / 2, 1.0) * 50

    # ------------------------------------------------------------------
    # Weights and assembly
    # ------------------------------------------------------------------
    weights = {
        "tissu_economique": 0.25,
        "structures_support": 0.20,
        "maillage_institutionnel": 0.15,
        "formation_recherche": 0.15,
        "emploi_competences": 0.15,
        "foncier_infrastructure": 0.10,
    }

    dimensions = [
        {
            "name": "tissu_economique",
            "label": "Tissu economique",
            "weight": weights["tissu_economique"],
            "score": round(d1_score, 1),
            "max_score": 100,
            "indicators": {
                "enterprises": enterprises,
                "sectors": sectors,
                "sector_relations": sector_rels,
            },
        },
        {
            "name": "structures_support",
            "label": "Structures de support",
            "weight": weights["structures_support"],
            "score": round(d2_score, 1),
            "max_score": 100,
            "indicators": {
                "poles": poles,
                "clusters": clusters,
                "incubators": incubators,
                "dev_agencies": dev_agencies,
            },
        },
        {
            "name": "maillage_institutionnel",
            "label": "Maillage institutionnel",
            "weight": weights["maillage_institutionnel"],
            "score": round(d3_score, 1),
            "max_score": 100,
            "indicators": {
                "institutions": institutions,
                "collectivities": collectivities,
                "institutional_relations": inst_rels,
            },
        },
        {
            "name": "formation_recherche",
            "label": "Formation & recherche",
            "weight": weights["formation_recherche"],
            "score": round(d4_score, 1),
            "max_score": 100,
            "indicators": {
                "formations": formations,
                "research_labs": research_labs,
                "formation_relations": formation_rels,
            },
        },
        {
            "name": "emploi_competences",
            "label": "Emploi & competences",
            "weight": weights["emploi_competences"],
            "score": round(d5_score, 1),
            "max_score": 100,
            "indicators": {
                "employment_basins": employment_basins,
                "employment_relations": employment_rels,
            },
        },
        {
            "name": "foncier_infrastructure",
            "label": "Foncier & infrastructure",
            "weight": weights["foncier_infrastructure"],
            "score": round(d6_score, 1),
            "max_score": 100,
            "indicators": {
                "economic_zones": economic_zones,
                "professional_networks": pro_networks,
            },
        },
    ]

    # Overall composite score
    overall = sum(d["score"] * d["weight"] for d in dimensions)

    # Recommendations
    recommendations: list[str] = []
    for d in dimensions:
        if d["score"] < 30:
            recommendations.append(
                f"Priorite haute: enrichir la dimension '{d['label']}' (score {d['score']}/100)"
            )
        elif d["score"] < 60:
            recommendations.append(f"A ameliorer: '{d['label']}' (score {d['score']}/100)")

    if not recommendations:
        recommendations.append("Bon niveau de couverture sur toutes les dimensions")

    logger.info(
        "Ecosystem score for dept {}: {:.1f}/100 ({} actors, {} relations)",
        department_code,
        overall,
        sum(actor_counts.values()),
        sum(relation_counts.values()),
    )

    return {
        "department_code": department_code,
        "overall_score": round(overall, 1),
        "dimensions": dimensions,
        "actor_counts": actor_counts,
        "relation_counts": relation_counts,
        "total_actors": sum(actor_counts.values()),
        "total_relations": sum(relation_counts.values()),
        "recommendations": recommendations,
    }
