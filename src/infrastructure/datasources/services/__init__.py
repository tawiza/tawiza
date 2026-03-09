"""Data source services."""

from .department_stats import (
    DEPARTMENT_NAMES,
    NAF_SECTORS,
    DepartmentStatsService,
    get_department_stats_service,
)

__all__ = [
    "DepartmentStatsService",
    "get_department_stats_service",
    "DEPARTMENT_NAMES",
    "NAF_SECTORS",
]
