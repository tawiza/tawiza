"""Dramatiq-based distributed crawling tasks.

This module provides asynchronous, distributed crawling via Dramatiq.
Supports:
- Distributed task execution
- Rate limiting
- Retry with backoff
- Priority queues
"""

from src.infrastructure.crawler.tasks.broker import (
    dramatiq_broker,
    get_broker,
    init_broker,
)
from src.infrastructure.crawler.tasks.crawl_tasks import (
    crawl_batch,
    crawl_url,
    extract_entities,
    process_result,
)

__all__ = [
    "dramatiq_broker",
    "get_broker",
    "init_broker",
    "crawl_url",
    "crawl_batch",
    "process_result",
    "extract_entities",
]
