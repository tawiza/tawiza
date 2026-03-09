"""Data sources infrastructure for multi-source territorial intelligence."""

from src.infrastructure.datasources.base import (
    AdapterConfig,
    BaseAdapter,
    DataSourceAdapter,
    SyncStatus,
)
from src.infrastructure.datasources.manager import DataSourceManager
from src.infrastructure.datasources.models import (
    BoampMarket,
    BodaccEvent,
    Enterprise,
    News,
)

__all__ = [
    # Base
    "AdapterConfig",
    "BaseAdapter",
    "DataSourceAdapter",
    "SyncStatus",
    # Manager
    "DataSourceManager",
    # Models
    "Enterprise",
    "BodaccEvent",
    "BoampMarket",
    "News",
]
