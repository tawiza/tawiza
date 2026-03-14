"""Neo4j client for graph database operations."""

import asyncio
from dataclasses import dataclass
from typing import Any

from loguru import logger

try:
    from neo4j import GraphDatabase

    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connection_pool_size: int = 50


class Neo4jClient:
    """
    Async-compatible Neo4j client.

    Wraps the official neo4j driver for use in async context.
    """

    def __init__(self, config: Neo4jConfig):
        """Initialize client with config."""
        self.config = config
        self._driver = None
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Check if driver is connected."""
        return self._driver is not None

    async def connect(self) -> bool:
        """
        Establish connection to Neo4j.

        Returns:
            True if connected successfully
        """
        if not HAS_NEO4J:
            logger.warning("neo4j package not installed")
            return False

        async with self._lock:
            if self._driver is not None:
                return True

            try:
                self._driver = GraphDatabase.driver(
                    self.config.uri,
                    auth=(self.config.user, self.config.password),
                    max_connection_pool_size=self.config.max_connection_pool_size,
                )
                # Verify connectivity
                self._driver.verify_connectivity()
                logger.info(f"Connected to Neo4j at {self.config.uri}")
                return True
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
                self._driver = None
                return False

    async def execute(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dicts
        """
        if not self._driver:
            raise RuntimeError("Not connected to Neo4j")

        def _run_query():
            with self._driver.session(database=self.config.database) as session:
                result = session.run(query, parameters or {})
                return result.data()

        # Run in thread pool for async compatibility
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run_query)

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a write query."""
        if not self._driver:
            raise RuntimeError("Not connected to Neo4j")

        def _run_write():
            with self._driver.session(database=self.config.database) as session:
                result = session.run(query, parameters or {})
                return result.data()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run_write)

    async def close(self) -> None:
        """Close the driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")
