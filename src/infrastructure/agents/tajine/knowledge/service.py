"""Knowledge Graph service for TAJINE."""

from __future__ import annotations

import contextlib
import json
import logging
from typing import Any

from src.infrastructure.config.tajine_config import get_tajine_config
from src.infrastructure.knowledge_graph.neo4j_client import Neo4jClient, Neo4jConfig

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """Service for TAJINE Knowledge Graph operations.

    Provides graceful degradation - works without Neo4j in degraded mode.
    """

    def __init__(self, config: Neo4jConfig | None = None):
        """Initialize KG service with optional Neo4j connection."""
        self._client: Neo4jClient | None = None
        self._available = False
        self._config = config

    async def connect(self) -> bool:
        """Initialize Neo4j client with graceful degradation."""
        try:
            if self._config is None:
                tajine_config = get_tajine_config()
                self._config = Neo4jConfig(
                    uri=tajine_config.neo4j_uri,
                    user=tajine_config.neo4j_user,
                    password=tajine_config.neo4j_password,
                )

            self._client = Neo4jClient(self._config)
            connected = await self._client.connect()

            if connected:
                self._available = True
                logger.info("Knowledge Graph connected to Neo4j")
                return True
            else:
                logger.warning("Neo4j connection failed, running in degraded mode")
                self._available = False
                return False

        except Exception as e:
            logger.warning(f"Neo4j not available, running in degraded mode: {e}")
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        """Check if KG is available."""
        return self._available

    async def store_enterprise(self, data: dict[str, Any]) -> bool:
        """Store enterprise node in Knowledge Graph."""
        if not self._available or not self._client:
            logger.debug("KG not available, skipping store")
            return False

        query = """
        MERGE (e:Enterprise {siret: $siret})
        SET e.nom = $nom,
            e.departement = $departement,
            e.naf_code = $naf_code,
            e.updated_at = datetime()
        RETURN e
        """

        try:
            await self._client.execute_write(
                query,
                {
                    "siret": data.get("siret", ""),
                    "nom": data.get("nom", data.get("denominationUniteLegale", "")),
                    "departement": data.get("departement", ""),
                    "naf_code": data.get("naf_code", data.get("activitePrincipaleUniteLegale", "")),
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store enterprise: {e}")
            return False

    async def store_enterprises_batch(self, enterprises: list[dict[str, Any]]) -> int:
        """Store multiple enterprises efficiently."""
        if not self._available or not self._client:
            return 0

        query = """
        UNWIND $enterprises AS ent
        MERGE (e:Enterprise {siret: ent.siret})
        SET e.nom = ent.nom,
            e.departement = ent.departement,
            e.naf_code = ent.naf_code,
            e.updated_at = datetime()
        RETURN count(e) as stored
        """

        try:
            # Normalize data
            normalized = []
            for ent in enterprises:
                normalized.append(
                    {
                        "siret": ent.get("siret", ""),
                        "nom": ent.get("nom", ent.get("denominationUniteLegale", "")),
                        "departement": ent.get("departement", ""),
                        "naf_code": ent.get(
                            "naf_code", ent.get("activitePrincipaleUniteLegale", "")
                        ),
                    }
                )

            result = await self._client.execute_write(query, {"enterprises": normalized})
            return result[0]["stored"] if result else 0
        except Exception as e:
            logger.error(f"Failed to store enterprises batch: {e}")
            return 0

    async def get_enterprises_by_territory(
        self, department: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Query enterprises by territory."""
        if not self._available or not self._client:
            return []

        query = """
        MATCH (e:Enterprise {departement: $department})
        RETURN e
        LIMIT $limit
        """

        try:
            results = await self._client.execute(query, {"department": department, "limit": limit})
            return [r["e"] for r in results]
        except Exception as e:
            logger.error(f"Failed to query enterprises: {e}")
            return []

    async def get_enterprises_by_naf(
        self, naf_code: str, department: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Query enterprises by NAF code."""
        if not self._available or not self._client:
            return []

        if department:
            query = """
            MATCH (e:Enterprise {naf_code: $naf_code, departement: $department})
            RETURN e
            LIMIT $limit
            """
            params = {"naf_code": naf_code, "department": department, "limit": limit}
        else:
            query = """
            MATCH (e:Enterprise {naf_code: $naf_code})
            RETURN e
            LIMIT $limit
            """
            params = {"naf_code": naf_code, "limit": limit}

        try:
            results = await self._client.execute(query, params)
            return [r["e"] for r in results]
        except Exception as e:
            logger.error(f"Failed to query enterprises by NAF: {e}")
            return []

    async def store_analysis_result(
        self, territory: str, analysis_type: str, result: dict[str, Any]
    ) -> bool:
        """Store analysis result linked to territory."""
        if not self._available or not self._client:
            return False

        query = """
        MERGE (t:Territory {code: $territory})
        CREATE (a:Analysis {
            type: $analysis_type,
            result: $result,
            created_at: datetime()
        })
        CREATE (t)-[:HAS_ANALYSIS]->(a)
        RETURN a
        """

        try:
            await self._client.execute_write(
                query,
                {
                    "territory": territory,
                    "analysis_type": analysis_type,
                    "result": json.dumps(result),
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store analysis: {e}")
            return False

    async def get_previous_analyses(
        self, territory: str, analysis_type: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Get previous analyses for a territory."""
        if not self._available or not self._client:
            return []

        if analysis_type:
            query = """
            MATCH (t:Territory {code: $territory})-[:HAS_ANALYSIS]->(a:Analysis {type: $type})
            RETURN a
            ORDER BY a.created_at DESC
            LIMIT $limit
            """
            params = {"territory": territory, "type": analysis_type, "limit": limit}
        else:
            query = """
            MATCH (t:Territory {code: $territory})-[:HAS_ANALYSIS]->(a:Analysis)
            RETURN a
            ORDER BY a.created_at DESC
            LIMIT $limit
            """
            params = {"territory": territory, "limit": limit}

        try:
            results = await self._client.execute(query, params)
            analyses = []
            for r in results:
                a = dict(r["a"])
                if "result" in a and isinstance(a["result"], str):
                    with contextlib.suppress(json.JSONDecodeError):
                        a["result"] = json.loads(a["result"])
                analyses.append(a)
            return analyses
        except Exception as e:
            logger.error(f"Failed to get previous analyses: {e}")
            return []

    async def get_context_for_query(
        self, query: str, territory: str | None = None
    ) -> dict[str, Any]:
        """Get relevant context from KG for a query."""
        context = {
            "available": self._available,
            "territory": territory,
            "enterprises": [],
            "previous_analyses": [],
            "related_sectors": [],
        }

        if not self._available:
            return context

        if territory:
            context["enterprises"] = await self.get_enterprises_by_territory(territory, limit=20)
            context["previous_analyses"] = await self.get_previous_analyses(territory, limit=3)

        return context

    async def create_relationship(
        self,
        from_siret: str,
        to_siret: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """Create relationship between enterprises."""
        if not self._available or not self._client:
            return False

        props_str = ""
        if properties:
            props_str = " {" + ", ".join(f"{k}: ${k}" for k in properties) + "}"

        query = f"""
        MATCH (e1:Enterprise {{siret: $from_siret}})
        MATCH (e2:Enterprise {{siret: $to_siret}})
        MERGE (e1)-[r:{relationship_type}{props_str}]->(e2)
        SET r.updated_at = datetime()
        RETURN r
        """

        params = {"from_siret": from_siret, "to_siret": to_siret}
        if properties:
            params.update(properties)

        try:
            await self._client.execute_write(query, params)
            return True
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            return False

    async def get_territory_stats(self, department: str) -> dict[str, Any]:
        """Get aggregated statistics for a territory."""
        if not self._available or not self._client:
            return {"available": False}

        query = """
        MATCH (e:Enterprise {departement: $department})
        WITH count(e) as total,
             collect(DISTINCT e.naf_code) as sectors
        RETURN total, size(sectors) as sector_count, sectors[0..10] as top_sectors
        """

        try:
            result = await self._client.execute(query, {"department": department})
            if result:
                return {
                    "available": True,
                    "total_enterprises": result[0]["total"],
                    "sector_count": result[0]["sector_count"],
                    "top_sectors": result[0]["top_sectors"],
                }
            return {"available": True, "total_enterprises": 0}
        except Exception as e:
            logger.error(f"Failed to get territory stats: {e}")
            return {"available": False, "error": str(e)}

    async def close(self) -> None:
        """Close the connection."""
        if self._client:
            await self._client.close()
            self._available = False


# Singleton instance
_service: KnowledgeGraphService | None = None


async def get_kg_service() -> KnowledgeGraphService:
    """Get or create the global KG service."""
    global _service
    if _service is None:
        _service = KnowledgeGraphService()
        await _service.connect()
    return _service
