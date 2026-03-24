"""Community detection using Louvain algorithm."""

import contextlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class Community:
    """A detected community of companies."""

    id: int
    members: list[str]  # List of SIRENs
    size: int
    dominant_sector: str = ""


class CommunityDetector:
    """
    Detect communities using Neo4j GDS Louvain algorithm.

    Requires Neo4j Graph Data Science plugin.
    """

    def __init__(self, client):
        """Initialize with Neo4j client."""
        self.client = client

    async def detect(self, territory_code: str, min_community_size: int = 2) -> list[Community]:
        """
        Detect communities in a territory.

        Args:
            territory_code: Territory to analyze
            min_community_size: Minimum members per community

        Returns:
            List of detected communities
        """
        # Create projected graph for territory
        project_query = """
        CALL gds.graph.project.cypher(
            'territory_graph',
            'MATCH (c:Company)-[:HAS_ESTABLISHMENT]->(:Establishment)-[:LOCATED_IN]->(:Territory {code: $code})
             RETURN id(c) AS id',
            'MATCH (c1:Company)-[:OPERATES_IN]->(s:Sector)<-[:OPERATES_IN]-(c2:Company)
             WHERE c1 <> c2
             RETURN id(c1) AS source, id(c2) AS target'
        )
        """

        try:
            await self.client.execute(project_query, {"code": territory_code})
        except Exception as e:
            logger.warning(f"Graph projection failed: {e}")
            # Fallback: simple query without GDS
            return await self._detect_simple(territory_code, min_community_size)

        # Run Louvain
        louvain_query = """
        CALL gds.louvain.stream('territory_graph')
        YIELD nodeId, communityId
        WITH gds.util.asNode(nodeId) AS company, communityId
        RETURN company.siren AS siren, communityId AS community
        """

        results = await self.client.execute(louvain_query)

        # Cleanup projected graph
        with contextlib.suppress(Exception):
            await self.client.execute("CALL gds.graph.drop('territory_graph', false)")

        return self._build_communities(results, min_community_size)

    async def _detect_simple(self, territory_code: str, min_size: int) -> list[Community]:
        """Simple community detection without GDS."""
        query = """
        MATCH (c:Company)-[:HAS_ESTABLISHMENT]->(:Establishment)-[:LOCATED_IN]->(:Territory {code: $code})
        MATCH (c)-[:OPERATES_IN]->(s:Sector)
        RETURN c.siren AS siren, s.naf_code AS sector
        """
        results = await self.client.execute(query, {"code": territory_code})

        # Group by sector as simple "communities"
        by_sector = defaultdict(list)
        for r in results:
            by_sector[r["sector"]].append(r["siren"])

        communities = []
        for i, (sector, members) in enumerate(by_sector.items()):
            if len(members) >= min_size:
                communities.append(
                    Community(id=i, members=members, size=len(members), dominant_sector=sector)
                )

        return sorted(communities, key=lambda c: c.size, reverse=True)

    def _build_communities(self, results: list[dict[str, Any]], min_size: int) -> list[Community]:
        """Build Community objects from query results."""
        by_community = defaultdict(list)
        for r in results:
            by_community[r["community"]].append(r["siren"])

        communities = []
        for cid, members in by_community.items():
            if len(members) >= min_size:
                communities.append(Community(id=cid, members=members, size=len(members)))

        return sorted(communities, key=lambda c: c.size, reverse=True)
