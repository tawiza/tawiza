"""Dashboard module for Tawiza.

Provides persistent storage for analyses history, alerts, and watchlist.
"""

from .database import DashboardDB, init_database
from .models import Alert, Analysis, DashboardStats, DashboardStatus, PollStatus, WatchItem
from .stats import StatsCalculator, get_async_stats

__all__ = [
    "DashboardDB",
    "init_database",
    "Alert",
    "Analysis",
    "WatchItem",
    "PollStatus",
    "DashboardStatus",
    "DashboardStats",
    "StatsCalculator",
    "get_async_stats",
]
