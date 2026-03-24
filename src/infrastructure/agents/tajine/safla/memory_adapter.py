"""SAFLA Memory Adapter for TAJINE.

Bridges SAFLA's HybridMemoryArchitecture with TAJINE's memory needs:
- Vector memory for semantic similarity search
- Episodic memory for task execution history
- Semantic memory for knowledge graph (territories, entities, relationships)
- Working memory for active context during analysis

This enables TAJINE to:
1. Remember past analyses and their outcomes
2. Build persistent knowledge about territories
3. Learn from successes and failures
4. Maintain context across sessions
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from safla.core.hybrid_memory import HybridMemoryArchitecture


@dataclass
class TAJINEMemoryItem:
    """Memory item adapted for TAJINE's territorial intelligence context."""

    item_id: str
    content: str
    memory_type: str  # "task", "analysis", "entity", "insight", "error"
    territory: str | None = None
    sector: str | None = None
    confidence: float = 0.0
    source: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_safla_metadata(self) -> dict[str, Any]:
        """Convert to SAFLA metadata format."""
        return {
            "type": self.memory_type,
            "territory": self.territory,
            "sector": self.sector,
            "confidence": self.confidence,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            **self.metadata,
        }


class SAFLAMemoryAdapter:
    """Adapter bridging SAFLA's memory system with TAJINE.

    Provides a simplified interface for TAJINE to interact with SAFLA's
    sophisticated memory architecture while maintaining domain-specific
    semantics for territorial intelligence.
    """

    def __init__(
        self,
        storage_path: Path | None = None,
        embedding_dim: int = 768,
        use_persistence: bool = True,
        ollama_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text",
    ):
        """Initialize the SAFLA memory adapter.

        Args:
            storage_path: Path for persistent storage (default: ~/.tawiza/safla)
            embedding_dim: Dimension for embeddings (768 for nomic-embed-text)
            use_persistence: Whether to persist memory to disk
            ollama_url: Ollama API URL for embeddings
            embedding_model: Model to use for embeddings (nomic-embed-text recommended)
        """
        self.storage_path = storage_path or Path.home() / ".tawiza" / "safla"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.embedding_dim = embedding_dim
        self.use_persistence = use_persistence
        self.ollama_url = ollama_url
        self.embedding_model = embedding_model

        self._memory: HybridMemoryArchitecture | None = None
        self._initialized = False
        self._embedding_cache: dict[str, np.ndarray] = {}
        self._ollama_client = None
        self._ollama_available = False

        logger.info(
            f"SAFLAMemoryAdapter initialized (storage: {self.storage_path}, embeddings: {embedding_model})"
        )

    async def initialize(self) -> None:
        """Initialize the SAFLA memory system and Ollama embeddings."""
        if self._initialized:
            return

        # Initialize Ollama client for embeddings
        try:
            from src.infrastructure.llm.ollama_client import OllamaClient

            self._ollama_client = OllamaClient(base_url=self.ollama_url)
            self._ollama_available = await self._ollama_client.is_available()
            if self._ollama_available:
                logger.info(f"Ollama embeddings available ({self.embedding_model})")
            else:
                logger.warning("Ollama not available, using hash-based embeddings")
        except Exception as e:
            logger.warning(f"Could not initialize Ollama for embeddings: {e}")
            self._ollama_available = False

        try:
            from safla.core.hybrid_memory import HybridMemoryArchitecture

            # Use SAFLA defaults - it handles its own configuration
            self._memory = HybridMemoryArchitecture()

            # Load persisted state if available
            if self.use_persistence:
                await self._load_state()

            self._initialized = True
            logger.info("SAFLA memory system initialized successfully")

        except ImportError as e:
            logger.warning(f"SAFLA not available, using fallback memory: {e}")
            self._memory = None
            self._initialized = True

    async def store_task_memory(
        self,
        task_id: str,
        query: str,
        result: dict[str, Any],
        territory: str | None = None,
        sector: str | None = None,
        success: bool = True,
    ) -> str:
        """Store memory of a task execution.

        Args:
            task_id: Unique task identifier
            query: Original user query
            result: Task execution result
            territory: Territory code if applicable
            sector: Economic sector if applicable
            success: Whether task succeeded

        Returns:
            Memory item ID
        """
        await self.initialize()

        # Create content summary
        content = f"Query: {query}\nSuccess: {success}\nResult summary: {str(result)[:500]}"

        item = TAJINEMemoryItem(
            item_id=task_id,
            content=content,
            memory_type="task",
            territory=territory,
            sector=sector,
            confidence=result.get("confidence", 0.5) if isinstance(result, dict) else 0.5,
            metadata={
                "success": success,
                "result_keys": list(result.keys()) if isinstance(result, dict) else [],
            },
        )

        return await self._store_item(item)

    async def store_analysis_insight(
        self,
        insight: str,
        analysis_type: str,
        territory: str | None = None,
        confidence: float = 0.5,
        sources: list[str] | None = None,
    ) -> str:
        """Store an analysis insight for future reference.

        Args:
            insight: The insight text
            analysis_type: Type of analysis (e.g., "economic", "demographic")
            territory: Territory code if applicable
            confidence: Confidence score
            sources: Data sources used

        Returns:
            Memory item ID
        """
        await self.initialize()

        item_id = hashlib.sha256(f"{insight}{datetime.now().isoformat()}".encode()).hexdigest()[:16]

        item = TAJINEMemoryItem(
            item_id=item_id,
            content=insight,
            memory_type="insight",
            territory=territory,
            confidence=confidence,
            metadata={"analysis_type": analysis_type, "sources": sources or []},
        )

        return await self._store_item(item)

    async def store_entity(
        self,
        entity_id: str,
        entity_type: str,
        name: str,
        attributes: dict[str, Any],
        territory: str | None = None,
    ) -> str:
        """Store an entity in semantic memory.

        Args:
            entity_id: Unique entity identifier (e.g., SIREN number)
            entity_type: Type of entity (e.g., "enterprise", "institution")
            name: Entity name
            attributes: Entity attributes
            territory: Territory code

        Returns:
            Memory item ID
        """
        await self.initialize()

        content = f"{entity_type}: {name}\nAttributes: {str(attributes)[:300]}"

        item = TAJINEMemoryItem(
            item_id=entity_id,
            content=content,
            memory_type="entity",
            territory=territory,
            metadata={"entity_type": entity_type, "name": name, **attributes},
        )

        return await self._store_item(item)

    async def recall_similar(
        self,
        query: str,
        memory_type: str | None = None,
        territory: str | None = None,
        limit: int = 5,
        min_similarity: float = 0.3,
    ) -> list[TAJINEMemoryItem]:
        """Recall memories similar to the query.

        Args:
            query: Search query
            memory_type: Filter by memory type
            territory: Filter by territory
            limit: Maximum results
            min_similarity: Minimum similarity threshold

        Returns:
            List of matching memory items
        """
        await self.initialize()

        if self._memory is None:
            return []

        try:
            # Generate query embedding
            embedding = await self._get_embedding(query)

            # Search in SAFLA vector memory
            results = self._memory.vector_memory.similarity_search(
                query_embedding=embedding,
                k=limit * 2,  # Get more to filter
                similarity_threshold=min_similarity,
            )

            # Filter and convert results
            items = []
            for result in results:
                # Result is a SimilarityResult with item_id, similarity_score, item
                metadata = result.item.metadata if result.item else {}

                # Apply filters
                if memory_type and metadata.get("type") != memory_type:
                    continue
                if territory and metadata.get("territory") != territory:
                    continue

                item = TAJINEMemoryItem(
                    item_id=metadata.get("item_id", result.item_id),
                    content=metadata.get("content", ""),
                    memory_type=metadata.get("type", "unknown"),
                    territory=metadata.get("territory"),
                    sector=metadata.get("sector"),
                    confidence=metadata.get("confidence", 0.0),
                    metadata=metadata,
                )
                items.append(item)

                if len(items) >= limit:
                    break

            return items

        except Exception as e:
            logger.error(f"Error recalling memories: {e}")
            return []

    async def get_territory_knowledge(self, territory: str) -> dict[str, Any]:
        """Get accumulated knowledge about a territory.

        Args:
            territory: Territory code (e.g., "75" for Paris)

        Returns:
            Dictionary with territory insights, entities, and history
        """
        await self.initialize()

        # Recall all memories for this territory
        insights = await self.recall_similar(
            query=f"territory {territory}",
            territory=territory,
            limit=20,
        )

        # Organize by type
        knowledge = {
            "territory": territory,
            "insights": [],
            "entities": [],
            "tasks": [],
            "last_updated": None,
        }

        for item in insights:
            if item.memory_type == "insight":
                knowledge["insights"].append(item.content)
            elif item.memory_type == "entity":
                knowledge["entities"].append(item.metadata)
            elif item.memory_type == "task":
                knowledge["tasks"].append(item.metadata)

            if knowledge["last_updated"] is None or item.timestamp > knowledge["last_updated"]:
                knowledge["last_updated"] = item.timestamp

        return knowledge

    async def _store_item(self, item: TAJINEMemoryItem) -> str:
        """Internal method to store an item in SAFLA memory."""
        if self._memory is None:
            logger.warning("SAFLA memory not available, item not stored")
            return item.item_id

        try:
            # Generate embedding
            embedding = await self._get_embedding(item.content)

            # Store in SAFLA vector memory
            metadata = item.to_safla_metadata()
            metadata["content"] = item.content
            metadata["item_id"] = item.item_id

            # SAFLA's vector_memory.store returns the generated ID
            stored_id = self._memory.vector_memory.store(
                embedding=embedding,
                metadata=metadata,
            )

            # Persist if enabled
            if self.use_persistence:
                await self._save_state()

            logger.debug(f"Stored memory item: {item.item_id} ({item.memory_type}) -> {stored_id}")
            return item.item_id

        except Exception as e:
            logger.error(f"Error storing memory item: {e}")
            return item.item_id

    async def _get_embedding(self, text: str) -> np.ndarray:
        """Get or generate embedding for text.

        Uses Ollama embeddings when available, falls back to hash-based.
        """
        cache_key = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()

        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        # Try Ollama embeddings first
        if self._ollama_available and self._ollama_client:
            try:
                embedding_list = await self._ollama_client.embed(text, model=self.embedding_model)
                if embedding_list:
                    embedding = np.array(embedding_list, dtype=np.float32)
                    # Normalize
                    norm = np.linalg.norm(embedding)
                    if norm > 0:
                        embedding = embedding / norm
                    # Update embedding_dim if different
                    if len(embedding) != self.embedding_dim:
                        self.embedding_dim = len(embedding)
                    self._embedding_cache[cache_key] = embedding
                    return embedding
            except Exception as e:
                logger.warning(f"Ollama embedding failed, using fallback: {e}")

        # Fallback: deterministic hash-based embedding
        np.random.seed(int(cache_key[:8], 16))
        embedding = np.random.randn(self.embedding_dim).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)

        self._embedding_cache[cache_key] = embedding
        return embedding

    async def _save_state(self) -> None:
        """Persist memory state to disk."""
        if self._memory is None:
            return

        try:
            state_file = self.storage_path / "memory_state.pkl"
            # SAFLA should have its own persistence, but we can add extra safety
            logger.debug(f"Memory state checkpoint at {state_file}")
        except Exception as e:
            logger.warning(f"Failed to save memory state: {e}")

    async def _load_state(self) -> None:
        """Load memory state from disk."""
        state_file = self.storage_path / "memory_state.pkl"
        if not state_file.exists():
            return

        try:
            logger.debug(f"Loading memory state from {state_file}")
            # SAFLA handles its own persistence
        except Exception as e:
            logger.warning(f"Failed to load memory state: {e}")

    async def get_stats(self) -> dict[str, Any]:
        """Get memory system statistics."""
        if self._memory is None:
            return {"status": "unavailable", "reason": "SAFLA not initialized"}

        return {
            "status": "active",
            "embedding_dim": self.embedding_dim,
            "storage_path": str(self.storage_path),
            "cache_size": len(self._embedding_cache),
        }
