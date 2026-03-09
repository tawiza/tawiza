"""Camel Workforce for territorial intelligence."""

from .agents import (
    create_analyst_agent,
    create_data_agent,
    create_geo_agent,
    create_web_agent,
    get_analyst_agent,
    get_data_agent,
    get_geo_agent,
    get_web_agent,
)
from .territorial_workforce import (
    TerritorialWorkforce,
    create_territorial_workforce,
)

__all__ = [
    # Workforce
    "TerritorialWorkforce",
    "create_territorial_workforce",
    # Individual agents
    "create_data_agent",
    "get_data_agent",
    "create_geo_agent",
    "get_geo_agent",
    "create_web_agent",
    "get_web_agent",
    "create_analyst_agent",
    "get_analyst_agent",
]
