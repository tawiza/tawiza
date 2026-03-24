"""
DAG Manager for causal graph persistence in Neo4j.

Provides CRUD operations for causal links with graceful degradation
to in-memory storage when Neo4j is unavailable.
"""

from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from loguru import logger

from src.infrastructure.agents.tajine.cognitive.causal.models import (
    CausalChain,
    CausalLink,
)

if TYPE_CHECKING:
    from src.infrastructure.knowledge_graph.neo4j_client import Neo4jClient


class DAGManager:
    """Manages causal DAG persistence in Neo4j.

    Features:
    - Store/retrieve causal links
    - Traverse causal chains
    - Graceful degradation to in-memory when Neo4j unavailable

    Note:
        All public methods follow the same pattern: try Neo4j first,
        fall back to in-memory on failure. This duplication is intentional
        for readability - each method is self-contained.
    """

    def __init__(self, neo4j_client: Optional["Neo4jClient"] = None):
        """Initialize DAG manager.

        Args:
            neo4j_client: Neo4j client instance (optional)
        """
        self._client = neo4j_client
        # In-memory fallback: effect -> [CausalLink, ...]
        self._memory_dag: dict[str, list[CausalLink]] = defaultdict(list)

    @property
    def is_neo4j_available(self) -> bool:
        """Check if Neo4j is available."""
        return self._client is not None and self._client.is_connected

    async def store_link(self, link: CausalLink, context: str = "default") -> bool:
        """Store a causal link.

        Args:
            link: Causal link to store
            context: Namespace (e.g., territory code)

        Returns:
            True if stored successfully
        """
        if not self.is_neo4j_available:
            return self._store_in_memory(link)

        try:
            query = """
            MERGE (c:CausalFactor {name: $cause, context: $context})
            MERGE (e:CausalFactor {name: $effect, context: $context})
            MERGE (c)-[r:CAUSES]->(e)
            SET r.correlation = $correlation,
                r.lag_months = $lag_months,
                r.confidence = $confidence,
                r.evidence = $evidence,
                r.updated_at = datetime()
            RETURN r
            """
            await self._client.execute_write(
                query,
                {
                    "cause": link.cause,
                    "effect": link.effect,
                    "context": context,
                    "correlation": link.correlation,
                    "lag_months": link.lag_months,
                    "confidence": link.confidence,
                    "evidence": link.evidence,
                },
            )
            logger.debug(f"Stored causal link: {link.cause} -> {link.effect}")
            return True
        except Exception as e:
            logger.warning(f"Neo4j store failed, using memory: {e}")
            return self._store_in_memory(link)

    def _store_in_memory(self, link: CausalLink) -> bool:
        """Store link in memory fallback."""
        self._memory_dag[link.effect].append(link)
        logger.debug(f"Stored in memory: {link.cause} -> {link.effect}")
        return True

    async def get_causes(
        self, effect: str, context: str = "default", min_confidence: float = 0.5
    ) -> list[CausalLink]:
        """Get causes of an effect.

        Args:
            effect: Effect to find causes for
            context: Namespace
            min_confidence: Minimum confidence threshold

        Returns:
            List of causal links
        """
        if not self.is_neo4j_available:
            return self._get_causes_from_memory(effect, min_confidence)

        try:
            query = """
            MATCH (c:CausalFactor)-[r:CAUSES]->(e:CausalFactor {name: $effect, context: $context})
            WHERE r.confidence >= $min_confidence
            RETURN c.name AS cause, r.correlation AS correlation,
                   r.lag_months AS lag_months, r.confidence AS confidence,
                   r.evidence AS evidence
            ORDER BY r.confidence DESC
            LIMIT 10
            """
            results = await self._client.execute(
                query, {"effect": effect, "context": context, "min_confidence": min_confidence}
            )
            return [
                CausalLink(
                    cause=r["cause"],
                    effect=effect,
                    correlation=r["correlation"],
                    lag_months=r["lag_months"],
                    confidence=r["confidence"],
                    evidence=r.get("evidence", ""),
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Neo4j query failed: {e}")
            return self._get_causes_from_memory(effect, min_confidence)

    def _get_causes_from_memory(self, effect: str, min_confidence: float) -> list[CausalLink]:
        """Get causes from in-memory DAG."""
        links = self._memory_dag.get(effect, [])
        filtered = [l for l in links if l.confidence >= min_confidence]
        return sorted(filtered, key=lambda x: x.confidence, reverse=True)[:10]

    async def get_causal_chain(
        self, root: str, target: str, context: str = "default", max_depth: int = 3
    ) -> CausalChain | None:
        """Find causal chain from root to target.

        Args:
            root: Starting factor
            target: Target effect
            context: Namespace
            max_depth: Maximum chain depth

        Returns:
            CausalChain if path exists, None otherwise
        """
        if not self.is_neo4j_available:
            return self._get_chain_from_memory(root, target, max_depth)

        try:
            query = """
            MATCH path = (root:CausalFactor {name: $root, context: $context})
                        -[:CAUSES*1..$max_depth]->
                        (target:CausalFactor {name: $target, context: $context})
            WITH path,
                 reduce(conf = 1.0, r IN relationships(path) | conf * r.confidence) AS chain_conf
            RETURN [n IN nodes(path) | n.name] AS chain_nodes,
                   [r IN relationships(path) | {
                       cause: startNode(r).name,
                       effect: endNode(r).name,
                       correlation: r.correlation,
                       lag_months: r.lag_months,
                       confidence: r.confidence,
                       evidence: r.evidence
                   }] AS chain_links,
                   chain_conf
            ORDER BY chain_conf DESC
            LIMIT 1
            """
            results = await self._client.execute(
                query, {"root": root, "target": target, "context": context, "max_depth": max_depth}
            )

            if not results:
                return None

            r = results[0]
            links = [
                CausalLink(
                    cause=l["cause"],
                    effect=l["effect"],
                    correlation=l.get("correlation", 0),
                    lag_months=l.get("lag_months", 0),
                    confidence=l.get("confidence", 0),
                    evidence=l.get("evidence", ""),
                )
                for l in r["chain_links"]
            ]

            return CausalChain(
                root_cause=root, final_effect=target, links=links, total_confidence=r["chain_conf"]
            )
        except Exception as e:
            logger.warning(f"Neo4j chain query failed: {e}")
            return self._get_chain_from_memory(root, target, max_depth)

    def _get_chain_from_memory(self, root: str, target: str, max_depth: int) -> CausalChain | None:
        """Find chain in memory using BFS."""
        # Simple BFS to find path
        visited = set()
        queue = [(root, [])]

        while queue and len(visited) < 100:
            current, path = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            if current == target and path:
                return CausalChain(root_cause=root, final_effect=target, links=path)

            if len(path) >= max_depth:
                continue

            # Find links where current is the cause
            for _effect, links in self._memory_dag.items():
                for link in links:
                    if link.cause == current and link.effect not in visited:
                        queue.append((link.effect, path + [link]))

        return None

    async def clear_context(self, context: str) -> None:
        """Clear all causal data for a context."""
        if self.is_neo4j_available:
            try:
                query = """
                MATCH (f:CausalFactor {context: $context})
                DETACH DELETE f
                """
                await self._client.execute_write(query, {"context": context})
                logger.info(f"Cleared causal context: {context}")
            except Exception as e:
                logger.warning(f"Failed to clear Neo4j context: {e}")

        # Clear only links associated with this context from memory
        # Note: In-memory links don't store context, so we clear all as fallback
        # For context-aware memory storage, would need to add context to CausalLink
        self._memory_dag.clear()
        logger.debug(f"Cleared in-memory DAG (context: {context})")
