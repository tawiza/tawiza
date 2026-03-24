"""Browser automation utilities for complex web applications."""

from .download_manager import (
    DownloadInfo,
    DownloadManager,
    get_download_manager,
)
from .spa_support import (
    InfiniteScrollHandler,
    SPAHelper,
    SPAWaitStrategy,
    WaitCondition,
)

__all__ = [
    "SPAWaitStrategy",
    "SPAHelper",
    "WaitCondition",
    "InfiniteScrollHandler",
    "DownloadManager",
    "DownloadInfo",
    "get_download_manager",
]
