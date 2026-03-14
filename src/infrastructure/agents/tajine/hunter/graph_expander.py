"""Graph Expander - Neo4j gap detection for proactive data gathering."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class GapType(Enum):
    """Types of knowledge gaps."""

    MISSING_RELATIONSHIP = "missing_relationship"
    STALE_DATA = "stale_data"
    INCOMPLETE_ENTITY = "incomplete_entity"
    ISOLATED_NODE = "isolated_node"


@dataclass
class KnowledgeGap:
    """A gap in the knowledge graph to fill."""

    gap_type: GapType
    entity_id: str
    description: str
    priority: int = 2  # 1=high, 2=medium, 3=low
    suggested_sources: list[str] = field(default_factory=list)


class GraphExpander:
    """
    Detects gaps in the knowledge graph for proactive data gathering.

    Finds:
    - Missing relationships (enterprises without dirigeants, etc.)
    - Stale data (not updated in N days)
    - Incomplete entities (missing important fields)
    - Isolated nodes (no connections)
    """

    REQUIRED_FIELDS = {
        "Entreprise": ["denominationUniteLegale", "activitePrincipaleUniteLegale"],
        "Etablissement": ["adresseEtablissement", "trancheEffectifsEtablissement"],
    }

    def __init__(
        self,
        neo4j_client=None,
        stale_days: int = 90,
        max_gaps: int = 50,
    ):
        """Initialize with Neo4j client."""
        self.neo4j = neo4j_client
        self.stale_days = stale_days
        self.max_gaps = max_gaps

    async def find_gaps(
        self,
        territory: str,
        entity_types: list[str] | None = None,
    ) -> list[KnowledgeGap]:
        """Find all gaps in the knowledge graph for a territory."""
        gaps = []

        # Run all gap detection methods concurrently
        missing_rels, stale, incomplete = await asyncio.gather(
            self._find_missing_relationships(territory),
            self._find_stale_entities(territory),
            self._find_incomplete_entities(territory),
        )
        gaps.extend(missing_rels)
        gaps.extend(stale)
        gaps.extend(incomplete)

        # Sort by priority and limit
        gaps.sort(key=lambda g: g.priority)
        return gaps[: self.max_gaps]

    async def _find_missing_relationships(self, territory: str) -> list[KnowledgeGap]:
        """Find entities missing expected relationships."""
        if not self.neo4j:
            return []

        query = """
        MATCH (e:Entreprise)
        WHERE e.codePostal STARTS WITH $territory
        AND NOT (e)-[:A_DIRIGEANT]->()
        RETURN e.siren as siren, 'Dirigeant' as missing_type
        LIMIT 20
        """

        try:
            results = await self.neo4j.run_query(query, {"territory": territory})
            return [
                KnowledgeGap(
                    gap_type=GapType.MISSING_RELATIONSHIP,
                    entity_id=f"SIREN:{r['siren']}",
                    description=f"Missing {r['missing_type']} relationship",
                    priority=2,
                    suggested_sources=["bodacc", "infogreffe"],
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Failed to find missing relationships: {e}")
            return []

    async def _find_stale_entities(self, territory: str) -> list[KnowledgeGap]:
        """Find entities not updated recently."""
        if not self.neo4j:
            return []

        stale_date = (datetime.now(UTC) - timedelta(days=self.stale_days)).isoformat()

        query = """
        MATCH (e:Entreprise)
        WHERE e.codePostal STARTS WITH $territory
        AND e.lastUpdated < $stale_date
        RETURN e.siren as siren, e.lastUpdated as last_updated
        LIMIT 20
        """

        try:
            results = await self.neo4j.run_query(
                query, {"territory": territory, "stale_date": stale_date}
            )
            return [
                KnowledgeGap(
                    gap_type=GapType.STALE_DATA,
                    entity_id=f"SIREN:{r['siren']}",
                    description=f"Not updated since {r['last_updated'][:10]}",
                    priority=3,
                    suggested_sources=["sirene"],
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Failed to find stale entities: {e}")
            return []

    async def _find_incomplete_entities(self, territory: str) -> list[KnowledgeGap]:
        """Find entities missing important fields."""
        if not self.neo4j:
            return []

        query = """
        MATCH (e:Entreprise)
        WHERE e.codePostal STARTS WITH $territory
        AND (e.chiffreAffaires IS NULL OR e.effectif IS NULL)
        RETURN e.siren as siren,
               CASE WHEN e.chiffreAffaires IS NULL THEN 'chiffre_affaires' ELSE '' END +
               CASE WHEN e.effectif IS NULL THEN ',effectif' ELSE '' END as missing
        LIMIT 20
        """

        try:
            results = await self.neo4j.run_query(query, {"territory": territory})
            return [
                KnowledgeGap(
                    gap_type=GapType.INCOMPLETE_ENTITY,
                    entity_id=f"SIREN:{r['siren']}",
                    description=f"Missing fields: {r['missing']}",
                    priority=2,
                    suggested_sources=["sirene", "infogreffe"],
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Failed to find incomplete entities: {e}")
            return []

    def gap_to_queries(self, gap: KnowledgeGap) -> list[str]:
        """Convert a knowledge gap to actionable search queries."""
        queries = []
        siren = gap.entity_id.replace("SIREN:", "")

        if gap.gap_type == GapType.MISSING_RELATIONSHIP:
            queries.append(f"dirigeants entreprise {siren}")
            queries.append(f"beneficiaires effectifs {siren}")

        elif gap.gap_type == GapType.STALE_DATA:
            queries.append(f"SIREN {siren}")

        elif gap.gap_type == GapType.INCOMPLETE_ENTITY:
            queries.append(f"chiffre affaires {siren}")
            queries.append(f"effectif salariés {siren}")

        return queries

    def to_kg_gaps_dict(self, gaps: list[KnowledgeGap]) -> dict:
        """Convert gaps to dict format for HypothesisGenerator."""
        return {
            "missing_fields": [
                g.description for g in gaps if g.gap_type == GapType.INCOMPLETE_ENTITY
            ],
            "stale_entities": [g.entity_id for g in gaps if g.gap_type == GapType.STALE_DATA],
            "missing_relationships": [
                g.entity_id for g in gaps if g.gap_type == GapType.MISSING_RELATIONSHIP
            ],
        }
