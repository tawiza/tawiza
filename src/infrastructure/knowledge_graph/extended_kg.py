"""Extended KnowledgeGraph with Neo4j integration."""

import asyncio
from typing import Any

from src.infrastructure.agents.tajine.validation.knowledge_graph import (
    KnowledgeGraph,
    Triple,
)

from .algorithms.centrality import CentralityCalculator, CentralityScore
from .algorithms.communities import Community, CommunityDetector
from .algorithms.similarity import SimilarCompany, SimilarityFinder
from .neo4j_client import Neo4jClient, Neo4jConfig
from .sync.batch_writer import BatchWriter, SyncConfig
from .sync.queue import SyncItem, SyncQueue


class ExtendedKnowledgeGraph(KnowledgeGraph):
    """
    KnowledgeGraph extended with Neo4j persistence and algorithms.

    Maintains in-memory cache for fast reads.
    Async syncs writes to Neo4j.
    Provides graph algorithm access.
    """

    def __init__(
        self, neo4j_config: Neo4jConfig | None = None, sync_config: SyncConfig | None = None
    ):
        """
        Initialize extended KnowledgeGraph.

        Args:
            neo4j_config: Neo4j connection config (None for in-memory only)
            sync_config: Sync configuration
        """
        super().__init__()

        self._neo4j_client: Neo4jClient | None = None
        self._sync_queue: SyncQueue | None = None
        self._batch_writer: BatchWriter | None = None

        # Algorithm helpers
        self._community_detector: CommunityDetector | None = None
        self._centrality_calc: CentralityCalculator | None = None
        self._similarity_finder: SimilarityFinder | None = None

        if neo4j_config:
            self._neo4j_client = Neo4jClient(neo4j_config)
            self._sync_queue = SyncQueue()
            self._batch_writer = BatchWriter(self._sync_queue, self._neo4j_client, sync_config)

            # Initialize algorithm helpers
            self._community_detector = CommunityDetector(self._neo4j_client)
            self._centrality_calc = CentralityCalculator(self._neo4j_client)
            self._similarity_finder = SimilarityFinder(self._neo4j_client)

    async def connect(self) -> bool:
        """Connect to Neo4j and start sync."""
        if not self._neo4j_client:
            return False

        connected = await self._neo4j_client.connect()
        if connected and self._batch_writer:
            await self._batch_writer.start()
        return connected

    async def close(self) -> None:
        """Stop sync and close Neo4j connection."""
        if self._batch_writer:
            await self._batch_writer.stop()
        if self._neo4j_client:
            await self._neo4j_client.close()

    def add_triple(
        self,
        subject: str,
        predicate: str,
        obj: Any,
        source: str | None = None,
        confidence: float = 1.0,
    ) -> Triple:
        """Add triple to cache and queue for Neo4j sync."""
        # Add to in-memory cache
        triple = super().add_triple(subject, predicate, obj, source, confidence)

        # Queue for Neo4j sync if configured
        if self._sync_queue:
            # Parse subject to get entity type
            parts = subject.split(":", 1)
            entity_type = parts[0].capitalize() if len(parts) > 1 else "Entity"
            entity_id = parts[1] if len(parts) > 1 else subject

            item = SyncItem(
                operation="merge",
                node_type=entity_type,
                data={
                    "id": entity_id,
                    predicate: obj,
                    "_source": source,
                    "_confidence": confidence,
                },
            )
            # Queue without blocking
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._sync_queue.put(item))
                else:
                    loop.run_until_complete(self._sync_queue.put(item))
            except RuntimeError:
                # No event loop available - sync not active
                pass

        return triple

    # Graph algorithm methods
    async def get_communities(self, territory_code: str, min_size: int = 2) -> list[Community]:
        """Detect communities in territory."""
        if not self._community_detector:
            return []
        return await self._community_detector.detect(territory_code, min_size)

    async def get_top_companies(
        self, territory_code: str, top_k: int = 20
    ) -> list[CentralityScore]:
        """Get top companies by PageRank centrality."""
        if not self._centrality_calc:
            return []
        return await self._centrality_calc.pagerank(territory_code, top_k)

    async def find_similar_companies(self, siren: str, top_k: int = 10) -> list[SimilarCompany]:
        """Find companies similar to given SIREN."""
        if not self._similarity_finder:
            return []
        return await self._similarity_finder.find_similar(siren, top_k)

    async def hydrate_from_neo4j(self, limit: int = 10000) -> int:
        """
        Load data from Neo4j into in-memory cache.

        Args:
            limit: Max entities to load

        Returns:
            Number of triples loaded
        """
        if not self._neo4j_client or not self._neo4j_client.is_connected:
            return 0

        query = """
        MATCH (n)
        WHERE n:Company OR n:Establishment OR n:Territory
        RETURN labels(n)[0] AS label, properties(n) AS props
        LIMIT $limit
        """

        results = await self._neo4j_client.execute(query, {"limit": limit})

        count = 0
        for r in results:
            label = r["label"].lower()
            props = r["props"]

            # Determine subject ID
            if label == "company":
                subject = f"company:{props.get('siren', '')}"
            elif label == "establishment":
                subject = f"establishment:{props.get('siret', '')}"
            elif label == "territory":
                subject = f"territory:{props.get('code', '')}"
            else:
                continue

            # Add properties as triples (skip sync back)
            for key, value in props.items():
                if value is not None and not key.startswith("_"):
                    super().add_triple(subject, key, value, source="neo4j")
                    count += 1

        return count
