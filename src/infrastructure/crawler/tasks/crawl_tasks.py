"""Dramatiq tasks for distributed crawling.

Provides asynchronous, distributed crawling tasks with:
- Rate limiting
- Retry with exponential backoff
- Result processing pipeline
- Entity extraction
"""

import asyncio
import time
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from src.infrastructure.crawler.tasks.broker import get_rate_limiter

# Get dramatiq if available
try:
    import dramatiq
    from dramatiq import actor

    DRAMATIQ_AVAILABLE = True
except ImportError:
    DRAMATIQ_AVAILABLE = False

    # Mock decorator for when dramatiq is not available
    def actor(*args, **kwargs):
        def decorator(fn):
            fn.send = lambda *a, **kw: fn(*a, **kw)
            fn.send_with_options = lambda *a, **kw: fn(*a, **kw.get("args", ()))
            return fn

        if args and callable(args[0]):
            return decorator(args[0])
        return decorator


# Import crawling components (lazy to avoid circular imports)
def _get_crawler():
    """Get AdaptiveCrawler instance."""
    try:
        from src.infrastructure.crawler.adaptive_crawler import AdaptiveCrawler

        return AdaptiveCrawler()
    except ImportError:
        logger.warning("AdaptiveCrawler not available")
        return None


def _get_headers_manager():
    """Get HeadersManager instance."""
    try:
        from src.infrastructure.crawler.workers.headers_manager import get_headers_manager

        return get_headers_manager()
    except ImportError:
        return None


def _get_proxy_pool():
    """Get ProxyPoolManager instance."""
    try:
        from src.infrastructure.crawler.workers.proxy_pool import get_proxy_pool

        return get_proxy_pool()
    except ImportError:
        return None


@actor(
    max_retries=3,
    min_backoff=1000,
    max_backoff=30000,
    time_limit=60000,  # 60 seconds max
    queue_name="crawl",
)
def crawl_url(
    url: str,
    source_id: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crawl a single URL with rate limiting.

    Args:
        url: URL to crawl
        source_id: Source identifier for tracking
        options: Crawling options (headers, proxy, etc.)

    Returns:
        Crawl result with content and metadata
    """
    options = options or {}
    start_time = time.time()

    logger.debug(f"Crawling URL: {url} (source: {source_id})")

    # Apply rate limiting if available
    rate_limiter = get_rate_limiter()
    if rate_limiter:
        with rate_limiter.acquire():
            return _do_crawl(url, source_id, options, start_time)
    else:
        return _do_crawl(url, source_id, options, start_time)


def _do_crawl(
    url: str,
    source_id: str,
    options: dict[str, Any],
    start_time: float,
) -> dict[str, Any]:
    """Perform the actual crawl operation.

    Args:
        url: URL to crawl
        source_id: Source identifier
        options: Crawling options
        start_time: Request start timestamp

    Returns:
        Crawl result
    """
    import httpx

    # Get headers
    headers_manager = _get_headers_manager()
    headers = options.get("headers", {})
    if headers_manager:
        domain = urlparse(url).netloc
        headers = {**headers_manager.get_headers(domain), **headers}

    # Get proxy
    proxy = options.get("proxy")
    if not proxy:
        proxy_pool = _get_proxy_pool()
        if proxy_pool and proxy_pool.pool_size > 0:
            # Run async in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            proxy = loop.run_until_complete(proxy_pool.get_next())

    # Prepare httpx options
    httpx_kwargs: dict[str, Any] = {
        "headers": headers,
        "timeout": options.get("timeout", 30.0),
        "follow_redirects": options.get("follow_redirects", True),
    }

    if proxy:
        httpx_kwargs["proxies"] = {"http://": proxy, "https://": proxy}

    try:
        with httpx.Client(**httpx_kwargs) as client:
            response = client.get(url)

        elapsed_ms = (time.time() - start_time) * 1000

        # Update proxy stats if used
        if proxy:
            proxy_pool = _get_proxy_pool()
            if proxy_pool:
                if response.status_code < 400:
                    proxy_pool.mark_success(proxy, elapsed_ms)
                else:
                    proxy_pool.mark_failed(proxy)

        result = {
            "success": response.status_code < 400,
            "url": url,
            "source_id": source_id,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "content_length": len(response.content),
            "elapsed_ms": round(elapsed_ms, 2),
            "timestamp": time.time(),
        }

        # Include content if successful and small enough
        if result["success"] and result["content_length"] < 1_000_000:  # 1MB limit
            if "text" in result["content_type"] or "json" in result["content_type"]:
                result["content"] = response.text
            else:
                result["content_binary"] = True

        return result

    except httpx.TimeoutException:
        logger.warning(f"Timeout crawling {url}")
        if proxy:
            proxy_pool = _get_proxy_pool()
            if proxy_pool:
                proxy_pool.mark_failed(proxy)
        return {
            "success": False,
            "url": url,
            "source_id": source_id,
            "error": "timeout",
            "timestamp": time.time(),
        }

    except Exception as e:
        logger.error(f"Error crawling {url}: {e}")
        if proxy:
            proxy_pool = _get_proxy_pool()
            if proxy_pool:
                proxy_pool.mark_failed(proxy)
        return {
            "success": False,
            "url": url,
            "source_id": source_id,
            "error": str(e),
            "timestamp": time.time(),
        }


@actor(
    max_retries=2,
    min_backoff=2000,
    queue_name="crawl",
)
def crawl_batch(
    urls: list[str],
    source_id: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crawl a batch of URLs.

    Args:
        urls: List of URLs to crawl
        source_id: Source identifier
        options: Shared crawling options

    Returns:
        Batch results with individual URL outcomes
    """
    options = options or {}
    results = []
    success_count = 0
    error_count = 0

    for url in urls:
        try:
            # Add delay between requests
            if results:
                import random

                time.sleep(random.uniform(1.0, 3.0))

            result = crawl_url(url, source_id, options)
            results.append(result)

            if result.get("success"):
                success_count += 1
            else:
                error_count += 1

        except Exception as e:
            logger.error(f"Batch crawl error for {url}: {e}")
            results.append(
                {
                    "success": False,
                    "url": url,
                    "source_id": source_id,
                    "error": str(e),
                }
            )
            error_count += 1

    return {
        "batch_size": len(urls),
        "success_count": success_count,
        "error_count": error_count,
        "source_id": source_id,
        "results": results,
    }


@actor(
    queue_name="process",
    priority=5,
)
def process_result(
    crawl_result: dict[str, Any],
    processors: list[str] | None = None,
) -> dict[str, Any]:
    """Process a crawl result through a pipeline.

    Args:
        crawl_result: Result from crawl_url
        processors: List of processor names to apply

    Returns:
        Processed result with extracted data
    """
    if not crawl_result.get("success"):
        return crawl_result

    processors = processors or ["clean_html", "extract_text"]
    processed = crawl_result.copy()
    content = crawl_result.get("content", "")

    for processor in processors:
        try:
            if processor == "clean_html":
                # Basic HTML cleaning
                import re

                content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
                content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
                content = re.sub(r"<[^>]+>", " ", content)
                content = re.sub(r"\s+", " ", content).strip()
                processed["cleaned_text"] = content

            elif processor == "extract_text":
                # Already done by clean_html
                pass

            elif processor == "extract_links":
                import re

                links = re.findall(r'href=["\']([^"\']+)["\']', crawl_result.get("content", ""))
                processed["extracted_links"] = links[:50]  # Limit to 50

            elif processor == "extract_meta":
                import re

                meta_pattern = r'<meta[^>]+(?:name|property)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']+)["\']'
                metas = re.findall(meta_pattern, crawl_result.get("content", ""), re.IGNORECASE)
                processed["meta"] = dict(metas)

        except Exception as e:
            logger.warning(f"Processor {processor} failed: {e}")

    return processed


@actor(
    queue_name="extract",
    priority=10,
)
def extract_entities(
    text: str,
    entity_types: list[str] | None = None,
) -> dict[str, Any]:
    """Extract named entities from text.

    Args:
        text: Text to process
        entity_types: Types of entities to extract

    Returns:
        Extracted entities by type
    """
    entity_types = entity_types or ["company", "siret", "location", "amount"]
    entities: dict[str, list[str]] = {et: [] for et in entity_types}

    import re

    # SIRET extraction
    if "siret" in entity_types:
        siret_pattern = r"\b\d{3}\s?\d{3}\s?\d{3}\s?\d{5}\b"
        sirets = re.findall(siret_pattern, text)
        entities["siret"] = list({s.replace(" ", "") for s in sirets})

    # SIREN extraction (9 digits)
    if "siren" in entity_types:
        siren_pattern = r"\b\d{3}\s?\d{3}\s?\d{3}\b"
        sirens = re.findall(siren_pattern, text)
        entities["siren"] = list({s.replace(" ", "") for s in sirens})[:20]

    # Amount extraction (euros)
    if "amount" in entity_types:
        amount_pattern = r"(\d[\d\s,\.]+)\s*(?:€|euros?|EUR)"
        amounts = re.findall(amount_pattern, text, re.IGNORECASE)
        entities["amount"] = amounts[:20]

    # French postal codes
    if "postal_code" in entity_types:
        postal_pattern = r"\b(?:75|77|78|91|92|93|94|95|\d{2})\d{3}\b"
        postals = re.findall(postal_pattern, text)
        entities["postal_code"] = list(set(postals))[:20]

    # Department extraction
    if "department" in entity_types:
        dept_pattern = r"\b(?:0[1-9]|[1-8]\d|9[0-5]|2[AB]|97[1-6])\b"
        depts = re.findall(dept_pattern, text)
        entities["department"] = list(set(depts))

    return {
        "entity_count": sum(len(v) for v in entities.values()),
        "entities": entities,
    }


# Convenience functions for non-Dramatiq usage


def crawl_url_sync(url: str, source_id: str, options: dict | None = None) -> dict:
    """Synchronous version of crawl_url for direct use."""
    return crawl_url(url, source_id, options)


def crawl_batch_sync(urls: list[str], source_id: str, options: dict | None = None) -> dict:
    """Synchronous version of crawl_batch for direct use."""
    return crawl_batch(urls, source_id, options)
