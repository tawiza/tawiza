"""TAJINE Knowledge Graph module."""
from src.infrastructure.agents.tajine.knowledge.service import (
    KnowledgeGraphService,
    get_kg_service,
)

__all__ = ["KnowledgeGraphService", "get_kg_service"]
