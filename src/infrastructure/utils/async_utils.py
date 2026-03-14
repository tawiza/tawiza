"""
Async utilities for optimized concurrent execution.

Provides:
- ResourceLimiter: Semaphore-based concurrency limiting
- ConcurrentExecutor: Batch execution with limits
- gather_with_concurrency: Limited concurrent gather
- timeout_with_default: Timeout with fallback value
- async_cached: Memoization for async functions

Usage:
    # Limit concurrent LLM calls to 5
    limiter = ResourceLimiter(max_concurrent=5)
    async with limiter.acquire():
        response = await llm.generate(prompt)

    # Execute batch with concurrency limit
    results = await gather_with_concurrency(
        10,  # max 10 concurrent
        *[fetch(url) for url in urls]
    )
"""

import asyncio
import functools
import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import (
    Any,
    TypeVar,
)

from loguru import logger

T = TypeVar("T")
R = TypeVar("R")


class ResourceLimiter:
    """
    Semaphore-based resource limiter for concurrent operations.

    Features:
    - Configurable max concurrent operations
    - Automatic waiting when limit reached
    - Statistics tracking
    - Named instances for logging

    Usage:
        # Limit LLM calls
        llm_limiter = ResourceLimiter(max_concurrent=5, name="llm")

        async with llm_limiter.acquire():
            response = await ollama.generate(prompt)

        # Or as decorator
        @llm_limiter.limit
        async def call_llm(prompt: str):
            return await ollama.generate(prompt)
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        name: str = "resource",
        timeout: float | None = None,
    ):
        """
        Initialize resource limiter.

        Args:
            max_concurrent: Maximum concurrent operations
            name: Name for logging
            timeout: Optional timeout for acquiring semaphore
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._name = name
        self._timeout = timeout

        # Statistics
        self._acquired = 0
        self._released = 0
        self._wait_time_total = 0.0
        self._timeouts = 0

        logger.debug(f"ResourceLimiter '{name}' initialized: max={max_concurrent}")

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a slot (async context manager).

        Usage:
            async with limiter.acquire():
                await do_work()
        """
        start = time.time()

        try:
            if self._timeout:
                try:
                    await asyncio.wait_for(
                        self._semaphore.acquire(),
                        timeout=self._timeout,
                    )
                except TimeoutError:
                    self._timeouts += 1
                    logger.warning(f"ResourceLimiter '{self._name}' timeout after {self._timeout}s")
                    raise
            else:
                await self._semaphore.acquire()

            self._acquired += 1
            self._wait_time_total += time.time() - start

            yield

        finally:
            self._semaphore.release()
            self._released += 1

    def limit(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """
        Decorator to limit concurrent calls to a function.

        Usage:
            @limiter.limit
            async def call_api():
                ...
        """

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            async with self.acquire():
                return await func(*args, **kwargs)

        return wrapper

    @property
    def current_usage(self) -> int:
        """Current number of active operations."""
        return self._max_concurrent - self._semaphore._value

    @property
    def available(self) -> int:
        """Number of available slots."""
        return self._semaphore._value

    def get_stats(self) -> dict[str, Any]:
        """Get limiter statistics."""
        avg_wait = self._wait_time_total / self._acquired if self._acquired > 0 else 0.0

        return {
            "name": self._name,
            "max_concurrent": self._max_concurrent,
            "current_usage": self.current_usage,
            "available": self.available,
            "total_acquired": self._acquired,
            "total_released": self._released,
            "timeouts": self._timeouts,
            "avg_wait_time_ms": round(avg_wait * 1000, 2),
        }


async def gather_with_concurrency[T](
    limit: int,
    *coros: Awaitable[T],
    return_exceptions: bool = False,
) -> list[T | BaseException]:
    """
    Like asyncio.gather but with concurrency limit.

    Args:
        limit: Maximum concurrent coroutines
        *coros: Coroutines to execute
        return_exceptions: Return exceptions instead of raising

    Returns:
        List of results in order

    Usage:
        # Fetch 100 URLs but only 10 at a time
        results = await gather_with_concurrency(
            10,
            *[fetch(url) for url in urls]
        )
    """
    semaphore = asyncio.Semaphore(limit)

    async def limited_coro(coro: Awaitable[T]) -> T:
        async with semaphore:
            return await coro

    return await asyncio.gather(
        *[limited_coro(c) for c in coros],
        return_exceptions=return_exceptions,
    )


async def gather_with_timeout[T](
    timeout: float,
    *coros: Awaitable[T],
    return_partial: bool = True,
) -> tuple[list[T], list[BaseException]]:
    """
    Gather with timeout - returns completed results even if some timeout.

    Args:
        timeout: Timeout in seconds
        *coros: Coroutines to execute
        return_partial: Return completed results on timeout

    Returns:
        Tuple of (successful_results, exceptions/timeouts)

    Usage:
        results, errors = await gather_with_timeout(
            5.0,  # 5 second timeout
            *[slow_operation(x) for x in items]
        )
    """
    tasks = [asyncio.create_task(c) for c in coros]

    try:
        done, pending = await asyncio.wait(
            tasks,
            timeout=timeout,
            return_when=asyncio.ALL_COMPLETED,
        )
    except Exception:
        # Cancel all on unexpected error
        for task in tasks:
            task.cancel()
        raise

    results = []
    errors = []

    # Process completed tasks
    for task in done:
        try:
            results.append(task.result())
        except Exception as e:
            errors.append(e)

    # Handle pending (timed out) tasks
    for task in pending:
        task.cancel()
        errors.append(TimeoutError(f"Task timed out after {timeout}s"))

    return results, errors


async def timeout_with_default[T](
    coro: Awaitable[T],
    timeout: float,
    default: T,
) -> T:
    """
    Execute coroutine with timeout, return default on timeout.

    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds
        default: Default value to return on timeout

    Returns:
        Result or default

    Usage:
        # Try to fetch, return None on timeout
        result = await timeout_with_default(
            fetch_data(url),
            timeout=5.0,
            default=None,
        )
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except TimeoutError:
        logger.debug(f"Operation timed out after {timeout}s, using default")
        return default


class ConcurrentExecutor[T, R]:
    """
    Batch executor with concurrency control.

    Features:
    - Process items in batches
    - Configurable concurrency
    - Progress tracking
    - Error handling options

    Usage:
        async def process_item(item):
            return await expensive_operation(item)

        executor = ConcurrentExecutor(
            func=process_item,
            max_concurrent=10,
            batch_size=50,
        )

        results = await executor.execute(items)
    """

    def __init__(
        self,
        func: Callable[[T], Awaitable[R]],
        max_concurrent: int = 10,
        batch_size: int | None = None,
        stop_on_error: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """
        Initialize executor.

        Args:
            func: Async function to apply to each item
            max_concurrent: Maximum concurrent operations
            batch_size: Process items in batches (None = all at once)
            stop_on_error: Stop execution on first error
            progress_callback: Called with (completed, total)
        """
        self._func = func
        self._max_concurrent = max_concurrent
        self._batch_size = batch_size
        self._stop_on_error = stop_on_error
        self._progress_callback = progress_callback

    async def execute(
        self,
        items: list[T],
    ) -> tuple[list[R], list[tuple[T, Exception]]]:
        """
        Execute function on all items.

        Args:
            items: Items to process

        Returns:
            Tuple of (results, errors as (item, exception) pairs)
        """
        results: list[R] = []
        errors: list[tuple[T, Exception]] = []
        completed = 0
        total = len(items)

        # Process in batches if configured
        if self._batch_size:
            batches = [
                items[i : i + self._batch_size] for i in range(0, len(items), self._batch_size)
            ]
        else:
            batches = [items]

        for batch in batches:
            if self._stop_on_error and errors:
                break

            # Process batch with concurrency limit
            batch_results = await gather_with_concurrency(
                self._max_concurrent,
                *[self._process_item(item) for item in batch],
                return_exceptions=True,
            )

            # Collect results
            for item, result in zip(batch, batch_results, strict=False):
                completed += 1

                if isinstance(result, Exception):
                    errors.append((item, result))
                    if self._stop_on_error:
                        break
                else:
                    results.append(result)

                # Report progress
                if self._progress_callback:
                    self._progress_callback(completed, total)

        return results, errors

    async def _process_item(self, item: T) -> R:
        """Process single item."""
        return await self._func(item)


def async_cached(
    ttl: float | None = 300,
    maxsize: int = 128,
    key_func: Callable[..., str] | None = None,
):
    """
    Decorator for caching async function results.

    Simple in-memory cache for async functions with TTL support.

    Args:
        ttl: Time-to-live in seconds (None = no expiration)
        maxsize: Maximum cache size
        key_func: Custom key function (default: hash of args)

    Usage:
        @async_cached(ttl=60)
        async def fetch_user(user_id: str):
            return await db.get_user(user_id)
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        cache: dict[str, tuple[T, float]] = {}
        cache_order: list[str] = []

        def make_key(*args, **kwargs) -> str:
            if key_func:
                return key_func(*args, **kwargs)

            key_data = json.dumps(
                {"args": args, "kwargs": kwargs},
                sort_keys=True,
                default=str,
            )
            return hashlib.sha256(key_data.encode()).hexdigest()[:16]

        def evict_if_needed():
            while len(cache) > maxsize:
                oldest_key = cache_order.pop(0)
                cache.pop(oldest_key, None)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            key = make_key(*args, **kwargs)
            now = time.time()

            # Check cache
            if key in cache:
                value, timestamp = cache[key]
                if ttl is None or (now - timestamp) < ttl:
                    return value
                else:
                    # Expired
                    del cache[key]
                    cache_order.remove(key)

            # Cache miss - execute
            result = await func(*args, **kwargs)

            # Store in cache
            cache[key] = (result, now)
            cache_order.append(key)
            evict_if_needed()

            return result

        def cache_clear():
            cache.clear()
            cache_order.clear()

        def cache_info() -> dict[str, Any]:
            return {
                "size": len(cache),
                "maxsize": maxsize,
                "ttl": ttl,
            }

        wrapper.cache_clear = cache_clear
        wrapper.cache_info = cache_info

        return wrapper

    return decorator


# Pre-configured resource limiters
LLM_LIMITER = ResourceLimiter(max_concurrent=5, name="llm")
DB_LIMITER = ResourceLimiter(max_concurrent=20, name="database")
HTTP_LIMITER = ResourceLimiter(max_concurrent=50, name="http")
BROWSER_LIMITER = ResourceLimiter(max_concurrent=3, name="browser")
