"""Centrality algorithms (PageRank, Betweenness)."""
from dataclasses import dataclass

from loguru import logger


@dataclass
class CentralityScore:
    """Centrality score for a company."""
    siren: str
    score: float
    rank: int = 0
    name: str = ""


class CentralityCalculator:
    """
    Calculate centrality metrics using Neo4j GDS.

    Supports PageRank and Betweenness centrality.
    """

    def __init__(self, client):
        """Initialize with Neo4j client."""
        self.client = client

    async def pagerank(
        self,
        territory_code: str,
        top_k: int = 20,
        damping_factor: float = 0.85
    ) -> list[CentralityScore]:
        """
        Calculate PageRank for companies in territory.

        Args:
            territory_code: Territory to analyze
            top_k: Number of top results
            damping_factor: PageRank damping (0.85 default)

        Returns:
            Top K companies by PageRank
        """
        query = """
        CALL gds.pageRank.stream({
            nodeQuery: 'MATCH (c:Company)-[:HAS_ESTABLISHMENT]->(:Establishment)-[:LOCATED_IN]->(:Territory {code: $code}) RETURN id(c) AS id',
            relationshipQuery: 'MATCH (c1:Company)-[:OPERATES_IN]->(s:Sector)<-[:OPERATES_IN]-(c2:Company) WHERE c1 <> c2 RETURN id(c1) AS source, id(c2) AS target',
            dampingFactor: $damping
        })
        YIELD nodeId, score
        WITH gds.util.asNode(nodeId) AS company, score
        RETURN company.siren AS siren, company.name AS name, score
        ORDER BY score DESC
        LIMIT $limit
        """

        try:
            results = await self.client.execute(query, {
                "code": territory_code,
                "damping": damping_factor,
                "limit": top_k
            })
        except Exception as e:
            logger.warning(f"PageRank failed, using simple fallback: {e}")
            return await self._simple_centrality(territory_code, top_k)

        return [
            CentralityScore(
                siren=r["siren"],
                name=r.get("name", ""),
                score=r["score"],
                rank=i + 1
            )
            for i, r in enumerate(results)
        ]

    async def _simple_centrality(
        self,
        territory_code: str,
        top_k: int
    ) -> list[CentralityScore]:
        """Simple degree centrality without GDS."""
        query = """
        MATCH (c:Company)-[:HAS_ESTABLISHMENT]->(:Establishment)-[:LOCATED_IN]->(:Territory {code: $code})
        OPTIONAL MATCH (c)-[r:OPERATES_IN]->()
        WITH c, count(r) AS degree
        RETURN c.siren AS siren, c.name AS name, degree AS score
        ORDER BY degree DESC
        LIMIT $limit
        """
        results = await self.client.execute(query, {
            "code": territory_code,
            "limit": top_k
        })

        return [
            CentralityScore(
                siren=r["siren"],
                name=r.get("name", ""),
                score=float(r["score"]),
                rank=i + 1
            )
            for i, r in enumerate(results)
        ]
