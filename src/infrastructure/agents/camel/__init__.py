"""CAMEL AI agent integration module.

Provides multi-agent systems using CAMEL AI framework for:
- Territorial intelligence analysis
- Data collection and enrichment
- Collaborative problem solving
"""

# Lazy imports to avoid circular dependencies
def get_territorial_workforce():
    """Get TerritorialWorkforce factory function."""
    from src.infrastructure.agents.camel.workforce import create_territorial_workforce
    return create_territorial_workforce

__all__ = [
    "get_territorial_workforce",
]
