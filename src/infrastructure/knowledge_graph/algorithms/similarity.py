"""Node similarity for finding similar companies."""
from dataclasses import dataclass, field

from loguru import logger


@dataclass
class SimilarCompany:
    """Similar company result."""
    siren: str
    similarity: float
    name: str = ""
    shared_sectors: list[str] = field(default_factory=list)


class SimilarityFinder:
    """
    Find similar companies using Neo4j GDS Node Similarity.

    Similarity based on shared sectors and territory.
    """

    def __init__(self, client):
        """Initialize with Neo4j client."""
        self.client = client

    async def find_similar(
        self,
        siren: str,
        top_k: int = 10
    ) -> list[SimilarCompany]:
        """
        Find companies similar to given SIREN.

        Args:
            siren: Source company SIREN
            top_k: Number of similar companies to return

        Returns:
            List of similar companies with scores
        """
        # Try GDS node similarity first
        query = """
        CALL gds.nodeSimilarity.stream({
            nodeQuery: 'MATCH (c:Company) RETURN id(c) AS id',
            relationshipQuery: 'MATCH (c:Company)-[:OPERATES_IN]->(s:Sector) RETURN id(c) AS source, id(s) AS target'
        })
        YIELD node1, node2, similarity
        WITH gds.util.asNode(node1) AS c1, gds.util.asNode(node2) AS c2, similarity
        WHERE c1.siren = $siren
        RETURN c2.siren AS siren, c2.name AS name, similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        try:
            results = await self.client.execute(query, {
                "siren": siren,
                "limit": top_k
            })
        except Exception as e:
            logger.warning(f"GDS similarity failed, using Jaccard: {e}")
            return await self._jaccard_similarity(siren, top_k)

        return [
            SimilarCompany(
                siren=r["siren"],
                name=r.get("name", ""),
                similarity=r["similarity"]
            )
            for r in results
        ]

    async def _jaccard_similarity(
        self,
        siren: str,
        top_k: int
    ) -> list[SimilarCompany]:
        """Calculate Jaccard similarity based on shared sectors."""
        query = """
        MATCH (c1:Company {siren: $siren})-[:OPERATES_IN]->(s:Sector)<-[:OPERATES_IN]-(c2:Company)
        WHERE c1 <> c2
        WITH c1, c2, collect(s.naf_code) AS shared
        MATCH (c1)-[:OPERATES_IN]->(s1:Sector)
        WITH c1, c2, shared, collect(s1.naf_code) AS sectors1
        MATCH (c2)-[:OPERATES_IN]->(s2:Sector)
        WITH c2, shared, sectors1, collect(s2.naf_code) AS sectors2
        WITH c2, shared,
             size(shared) * 1.0 / (size(sectors1) + size(sectors2) - size(shared)) AS jaccard
        RETURN c2.siren AS siren, c2.name AS name, jaccard AS similarity, shared
        ORDER BY jaccard DESC
        LIMIT $limit
        """

        results = await self.client.execute(query, {
            "siren": siren,
            "limit": top_k
        })

        return [
            SimilarCompany(
                siren=r["siren"],
                name=r.get("name", ""),
                similarity=r["similarity"],
                shared_sectors=r.get("shared", [])
            )
            for r in results
        ]
