"""Tests for async utilities.

This module tests:
- ResourceLimiter
- gather_with_concurrency
- gather_with_timeout
- timeout_with_default
- ConcurrentExecutor
- async_cached
"""

import asyncio
import time

import pytest

from src.infrastructure.utils.async_utils import (
    BROWSER_LIMITER,
    DB_LIMITER,
    HTTP_LIMITER,
    LLM_LIMITER,
    ConcurrentExecutor,
    ResourceLimiter,
    async_cached,
    gather_with_concurrency,
    gather_with_timeout,
    timeout_with_default,
)


class TestResourceLimiter:
    """Test suite for ResourceLimiter."""

    @pytest.mark.asyncio
    async def test_limiter_basic_acquire(self):
        """Should allow acquiring within limit."""
        limiter = ResourceLimiter(max_concurrent=5, name="test")

        async with limiter.acquire():
            assert limiter.current_usage == 1

        assert limiter.current_usage == 0

    @pytest.mark.asyncio
    async def test_limiter_tracks_acquired_count(self):
        """Should track total acquired count."""
        limiter = ResourceLimiter(max_concurrent=5, name="test")

        async with limiter.acquire():
            pass
        async with limiter.acquire():
            pass

        stats = limiter.get_stats()
        assert stats["total_acquired"] == 2
        assert stats["total_released"] == 2

    @pytest.mark.asyncio
    async def test_limiter_respects_concurrency_limit(self):
        """Should block when limit is reached."""
        limiter = ResourceLimiter(max_concurrent=2, name="test")
        results = []

        async def task(id):
            async with limiter.acquire():
                results.append(f"start-{id}")
                await asyncio.sleep(0.01)
                results.append(f"end-{id}")

        # Run 4 tasks with limit of 2
        await asyncio.gather(task(1), task(2), task(3), task(4))

        # All should complete
        assert len(results) == 8

    @pytest.mark.asyncio
    async def test_limiter_with_timeout(self):
        """Should timeout when waiting too long."""
        limiter = ResourceLimiter(max_concurrent=1, name="test", timeout=0.01)

        async with limiter.acquire():
            # Another acquire should timeout
            with pytest.raises(asyncio.TimeoutError):
                async with limiter.acquire():
                    pass

        stats = limiter.get_stats()
        assert stats["timeouts"] == 1

    @pytest.mark.asyncio
    async def test_limiter_decorator(self):
        """Should work as decorator."""
        limiter = ResourceLimiter(max_concurrent=2, name="test")
        call_count = 0

        @limiter.limit
        async def limited_func():
            nonlocal call_count
            call_count += 1
            return "done"

        results = await asyncio.gather(
            limited_func(),
            limited_func(),
            limited_func(),
        )

        assert results == ["done", "done", "done"]
        assert call_count == 3

    def test_limiter_available_slots(self):
        """Should report available slots correctly."""
        limiter = ResourceLimiter(max_concurrent=10, name="test")
        assert limiter.available == 10

    def test_limiter_get_stats(self):
        """Should return statistics."""
        limiter = ResourceLimiter(max_concurrent=5, name="test_stats")
        stats = limiter.get_stats()

        assert stats["name"] == "test_stats"
        assert stats["max_concurrent"] == 5
        assert stats["current_usage"] == 0
        assert stats["available"] == 5


class TestGatherWithConcurrency:
    """Test suite for gather_with_concurrency."""

    @pytest.mark.asyncio
    async def test_gather_basic(self):
        """Should gather results with concurrency limit."""
        results = []

        async def coro(x):
            results.append(x)
            return x * 2

        output = await gather_with_concurrency(
            2,
            coro(1),
            coro(2),
            coro(3),
        )

        assert output == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_gather_respects_limit(self):
        """Should respect concurrency limit."""
        concurrent = 0
        max_concurrent = 0

        async def coro(x):
            nonlocal concurrent, max_concurrent
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            await asyncio.sleep(0.01)
            concurrent -= 1
            return x

        await gather_with_concurrency(
            2,  # Limit to 2 concurrent
            *[coro(i) for i in range(10)],
        )

        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_gather_return_exceptions(self):
        """Should return exceptions when configured."""

        async def coro(x):
            if x == 2:
                raise ValueError("Error at 2")
            return x

        results = await gather_with_concurrency(
            5,
            coro(1),
            coro(2),
            coro(3),
            return_exceptions=True,
        )

        assert results[0] == 1
        assert isinstance(results[1], ValueError)
        assert results[2] == 3


class TestGatherWithTimeout:
    """Test suite for gather_with_timeout."""

    @pytest.mark.asyncio
    async def test_gather_all_complete(self):
        """Should return all results when completed in time."""

        async def fast_coro(x):
            return x * 2

        results, errors = await gather_with_timeout(
            1.0,
            fast_coro(1),
            fast_coro(2),
            fast_coro(3),
        )

        # Results may not be in order due to concurrent execution
        assert sorted(results) == [2, 4, 6]
        assert errors == []

    @pytest.mark.asyncio
    async def test_gather_partial_timeout(self):
        """Should return partial results on timeout."""

        async def coro(x, delay):
            await asyncio.sleep(delay)
            return x

        results, errors = await gather_with_timeout(
            0.05,
            coro(1, 0.01),  # Fast - should complete
            coro(2, 0.1),  # Slow - should timeout
        )

        assert 1 in results
        assert len(errors) >= 1


class TestTimeoutWithDefault:
    """Test suite for timeout_with_default."""

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self):
        """Should return result when completed in time."""

        async def fast_coro():
            return "success"

        result = await timeout_with_default(fast_coro(), 1.0, "default")
        assert result == "success"

    @pytest.mark.asyncio
    async def test_returns_default_on_timeout(self):
        """Should return default when timeout."""

        async def slow_coro():
            await asyncio.sleep(1.0)
            return "success"

        result = await timeout_with_default(slow_coro(), 0.01, "default")
        assert result == "default"

    @pytest.mark.asyncio
    async def test_returns_none_default(self):
        """Should work with None as default."""

        async def slow_coro():
            await asyncio.sleep(1.0)
            return "success"

        result = await timeout_with_default(slow_coro(), 0.01, None)
        assert result is None


class TestConcurrentExecutor:
    """Test suite for ConcurrentExecutor."""

    @pytest.mark.asyncio
    async def test_execute_all_items(self):
        """Should execute function on all items."""

        async def double(x):
            return x * 2

        executor = ConcurrentExecutor(func=double, max_concurrent=5)
        results, errors = await executor.execute([1, 2, 3, 4, 5])

        assert sorted(results) == [2, 4, 6, 8, 10]
        assert errors == []

    @pytest.mark.asyncio
    async def test_execute_with_batch_size(self):
        """Should process in batches."""
        call_order = []

        async def track(x):
            call_order.append(x)
            return x

        executor = ConcurrentExecutor(
            func=track,
            max_concurrent=10,
            batch_size=3,
        )
        results, errors = await executor.execute([1, 2, 3, 4, 5])

        assert sorted(results) == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_execute_with_errors(self):
        """Should collect errors."""

        async def fail_on_3(x):
            if x == 3:
                raise ValueError("Error on 3")
            return x

        executor = ConcurrentExecutor(func=fail_on_3, max_concurrent=5)
        results, errors = await executor.execute([1, 2, 3, 4, 5])

        assert sorted(results) == [1, 2, 4, 5]
        assert len(errors) == 1
        assert errors[0][0] == 3

    @pytest.mark.asyncio
    async def test_execute_stop_on_error(self):
        """Should stop on first error when configured."""
        processed = []

        async def fail_on_2(x):
            if x == 2:
                raise ValueError("Error on 2")
            processed.append(x)
            return x

        executor = ConcurrentExecutor(
            func=fail_on_2,
            max_concurrent=1,  # Sequential - ensures order
            batch_size=1,  # One at a time to ensure predictable order
            stop_on_error=True,
        )
        results, errors = await executor.execute([1, 2, 3, 4])

        # Should stop after error on 2, so 3 and 4 not in same batch
        assert 1 in processed
        # With batch_size=1 and stop_on_error, we should stop after the error
        assert len(errors) >= 1
        assert errors[0][0] == 2

    @pytest.mark.asyncio
    async def test_execute_progress_callback(self):
        """Should call progress callback."""
        progress_calls = []

        async def identity(x):
            return x

        def progress(completed, total):
            progress_calls.append((completed, total))

        executor = ConcurrentExecutor(
            func=identity,
            max_concurrent=5,
            progress_callback=progress,
        )
        await executor.execute([1, 2, 3])

        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)


class TestAsyncCached:
    """Test suite for async_cached decorator."""

    @pytest.mark.asyncio
    async def test_caches_result(self):
        """Should cache function result."""
        call_count = 0

        @async_cached(ttl=60)
        async def expensive_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = await expensive_func(5)
        result2 = await expensive_func(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_different_args_different_cache(self):
        """Should cache separately for different args."""
        call_count = 0

        @async_cached(ttl=60)
        async def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        await func(1)
        await func(2)
        await func(1)

        assert call_count == 2  # 1 and 2, then 1 from cache

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Should expire cached values."""
        call_count = 0

        @async_cached(ttl=0.01)  # 10ms TTL
        async def func(x):
            nonlocal call_count
            call_count += 1
            return x

        await func(1)
        await asyncio.sleep(0.02)  # Wait for expiration
        await func(1)

        assert call_count == 2  # Called twice due to expiration

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Should support cache_clear."""
        call_count = 0

        @async_cached(ttl=60)
        async def func(x):
            nonlocal call_count
            call_count += 1
            return x

        await func(1)
        func.cache_clear()
        await func(1)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cache_info(self):
        """Should provide cache_info."""

        @async_cached(ttl=60, maxsize=100)
        async def func(x):
            return x

        await func(1)
        await func(2)

        info = func.cache_info()
        assert info["size"] == 2
        assert info["maxsize"] == 100
        assert info["ttl"] == 60

    @pytest.mark.asyncio
    async def test_maxsize_eviction(self):
        """Should evict old entries when maxsize reached."""

        @async_cached(ttl=60, maxsize=3)
        async def func(x):
            return x

        # Fill cache beyond maxsize
        for i in range(5):
            await func(i)

        info = func.cache_info()
        assert info["size"] <= 3


class TestPreConfiguredLimiters:
    """Test suite for pre-configured resource limiters."""

    def test_llm_limiter_config(self):
        """LLM_LIMITER should have correct config."""
        stats = LLM_LIMITER.get_stats()
        assert stats["name"] == "llm"
        assert stats["max_concurrent"] == 5

    def test_db_limiter_config(self):
        """DB_LIMITER should have correct config."""
        stats = DB_LIMITER.get_stats()
        assert stats["name"] == "database"
        assert stats["max_concurrent"] == 20

    def test_http_limiter_config(self):
        """HTTP_LIMITER should have correct config."""
        stats = HTTP_LIMITER.get_stats()
        assert stats["name"] == "http"
        assert stats["max_concurrent"] == 50

    def test_browser_limiter_config(self):
        """BROWSER_LIMITER should have correct config."""
        stats = BROWSER_LIMITER.get_stats()
        assert stats["name"] == "browser"
        assert stats["max_concurrent"] == 3
