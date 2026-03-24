"""Tests for Retry and Circuit Breaker patterns."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.resilience.retry import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    CircuitState,
    ResilientExecutor,
    RetryConfig,
    RetryHandler,
    RetryResult,
    RetryStrategy,
    with_circuit_breaker,
    with_retry,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.backoff_base == 1.0
        assert config.backoff_max == 60.0
        assert config.strategy == RetryStrategy.EXPONENTIAL_JITTER

    def test_calculate_delay_fixed(self):
        """Test fixed backoff strategy."""
        config = RetryConfig(
            backoff_base=2.0,
            strategy=RetryStrategy.FIXED,
        )

        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 2.0
        assert config.calculate_delay(5) == 2.0

    def test_calculate_delay_linear(self):
        """Test linear backoff strategy."""
        config = RetryConfig(
            backoff_base=1.0,
            strategy=RetryStrategy.LINEAR,
        )

        assert config.calculate_delay(1) == 1.0
        assert config.calculate_delay(2) == 2.0
        assert config.calculate_delay(3) == 3.0

    def test_calculate_delay_exponential(self):
        """Test exponential backoff strategy."""
        config = RetryConfig(
            backoff_base=1.0,
            strategy=RetryStrategy.EXPONENTIAL,
        )

        assert config.calculate_delay(1) == 1.0
        assert config.calculate_delay(2) == 2.0
        assert config.calculate_delay(3) == 4.0
        assert config.calculate_delay(4) == 8.0

    def test_calculate_delay_fibonacci(self):
        """Test fibonacci backoff strategy."""
        config = RetryConfig(
            backoff_base=1.0,
            strategy=RetryStrategy.FIBONACCI,
        )

        assert config.calculate_delay(1) == 1.0
        assert config.calculate_delay(2) == 1.0
        assert config.calculate_delay(3) == 2.0
        assert config.calculate_delay(4) == 3.0
        assert config.calculate_delay(5) == 5.0

    def test_calculate_delay_respects_max(self):
        """Test that delay is capped at max."""
        config = RetryConfig(
            backoff_base=10.0,
            backoff_max=25.0,
            strategy=RetryStrategy.EXPONENTIAL,
        )

        assert config.calculate_delay(1) == 10.0
        assert config.calculate_delay(2) == 20.0
        assert config.calculate_delay(3) == 25.0  # Capped

    def test_should_retry_retryable(self):
        """Test retry decision for retryable exception."""
        config = RetryConfig(
            retryable_exceptions={ValueError, RuntimeError},
        )

        assert config.should_retry(ValueError("error")) is True
        assert config.should_retry(RuntimeError("error")) is True
        assert config.should_retry(TypeError("error")) is False

    def test_should_retry_non_retryable(self):
        """Test retry decision for non-retryable exception."""
        config = RetryConfig(
            retryable_exceptions={Exception},
            non_retryable_exceptions={KeyboardInterrupt, SystemExit},
        )

        assert config.should_retry(ValueError("error")) is True
        assert config.should_retry(KeyboardInterrupt()) is False
        assert config.should_retry(SystemExit()) is False


class TestRetryHandler:
    """Tests for RetryHandler."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Test successful execution on first try."""
        handler = RetryHandler()

        async def success_func():
            return "success"

        result = await handler.execute(success_func)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 1
        assert result.last_exception is None

    @pytest.mark.asyncio
    async def test_success_after_retries(self):
        """Test success after failed attempts."""
        handler = RetryHandler(
            RetryConfig(
                max_attempts=3,
                backoff_base=0.01,  # Fast for testing
            )
        )

        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = await handler.execute(flaky_func)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_all_attempts_fail(self):
        """Test failure after all attempts exhausted."""
        handler = RetryHandler(
            RetryConfig(
                max_attempts=3,
                backoff_base=0.01,
            )
        )

        async def always_fails():
            raise ValueError("Always fails")

        result = await handler.execute(always_fails)

        assert result.success is False
        assert result.attempts == 3
        assert isinstance(result.last_exception, ValueError)

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        """Test immediate failure on non-retryable exception."""

        # Create a custom non-retryable exception
        class NonRetryableError(Exception):
            pass

        handler = RetryHandler(
            RetryConfig(
                max_attempts=5,
                non_retryable_exceptions={NonRetryableError},
            )
        )

        async def raises_non_retryable():
            raise NonRetryableError("Should not retry")

        result = await handler.execute(raises_non_retryable)

        assert result.success is False
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_sync_function(self):
        """Test with synchronous function."""
        handler = RetryHandler()

        def sync_func():
            return "sync_result"

        result = await handler.execute(sync_func)

        assert result.success is True
        assert result.result == "sync_result"

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Test retry callback is called."""
        callback_calls = []

        async def on_retry(attempt, error, delay):
            callback_calls.append((attempt, str(error), delay))

        handler = RetryHandler(
            RetryConfig(
                max_attempts=3,
                backoff_base=0.01,
                on_retry=on_retry,
            )
        )

        call_count = 0

        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Fail {call_count}")
            return "success"

        await handler.execute(fails_twice)

        assert len(callback_calls) == 2
        assert callback_calls[0][0] == 1  # First retry after attempt 1
        assert callback_calls[1][0] == 2

    def test_stats(self):
        """Test statistics tracking."""
        handler = RetryHandler()

        assert handler.stats["total_calls"] == 0
        assert handler.stats["successful_calls"] == 0
        assert handler.stats["failed_calls"] == 0

    @pytest.mark.asyncio
    async def test_attempt_history(self):
        """Test attempt history is recorded."""
        handler = RetryHandler(
            RetryConfig(
                max_attempts=3,
                backoff_base=0.01,
            )
        )

        call_count = 0

        async def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First fail")
            return "success"

        result = await handler.execute(fails_once)

        assert len(result.attempt_history) == 2
        assert result.attempt_history[0]["status"] == "failed"
        assert result.attempt_history[1]["status"] == "success"


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_initial_state_closed(self):
        """Test circuit starts in closed state."""
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_keeps_closed(self):
        """Test successful calls keep circuit closed."""
        breaker = CircuitBreaker("test")

        async def success_func():
            return "ok"

        for _ in range(10):
            await breaker.call(success_func)

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self):
        """Test failures cause circuit to open."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("error")

        for i in range(3):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self):
        """Test open circuit rejects calls."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=100)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

        async def success_func():
            return "ok"

        with pytest.raises(CircuitOpenError):
            await breaker.call(success_func)

    @pytest.mark.asyncio
    async def test_open_circuit_uses_fallback(self):
        """Test open circuit uses fallback."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=100)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("error")

        async def fallback():
            return "fallback_result"

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        result = await breaker.call(fail_func, fallback=fallback)

        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        """Test circuit goes half-open after timeout."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=0.01)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

        await asyncio.sleep(0.02)

        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self):
        """Test successful calls in half-open close circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            timeout=0.01,
        )
        breaker = CircuitBreaker("test", config)

        call_count = 0

        async def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("first fail")
            return "ok"

        # First call fails, opens circuit
        with pytest.raises(ValueError):
            await breaker.call(eventually_succeeds)

        await asyncio.sleep(0.02)

        # Two successful calls should close
        await breaker.call(eventually_succeeds)
        await breaker.call(eventually_succeeds)

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        """Test failure in half-open reopens circuit."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=0.01)
        breaker = CircuitBreaker("test", config)

        async def always_fails():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await breaker.call(always_fails)

        await asyncio.sleep(0.02)

        assert breaker.state == CircuitState.HALF_OPEN

        with pytest.raises(ValueError):
            await breaker.call(always_fails)

        assert breaker.state == CircuitState.OPEN

    def test_manual_reset(self):
        """Test manual circuit reset."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)

        # Force open
        breaker._record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED


class TestResilientExecutor:
    """Tests for ResilientExecutor."""

    @pytest.mark.asyncio
    async def test_combines_retry_and_circuit(self):
        """Test executor combines retry and circuit breaker."""
        executor = ResilientExecutor(
            "test",
            retry_config=RetryConfig(max_attempts=3, backoff_base=0.01),
            circuit_config=CircuitBreakerConfig(failure_threshold=5),
        )

        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temp error")
            return "success"

        result = await executor.execute(flaky)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_uses_fallback(self):
        """Test executor uses fallback."""
        executor = ResilientExecutor(
            "test",
            retry_config=RetryConfig(max_attempts=2, backoff_base=0.01),
            circuit_config=CircuitBreakerConfig(failure_threshold=3),
        )

        async def always_fails():
            raise ValueError("error")

        async def fallback():
            return "fallback"

        # Exhaust retries to open circuit
        for _ in range(3):
            try:
                await executor.execute(always_fails)
            except ValueError:
                pass

        # Now circuit is open, use fallback
        result = await executor.execute(always_fails, fallback=fallback)

        assert result == "fallback"

    def test_is_healthy(self):
        """Test health check."""
        executor = ResilientExecutor("test")

        assert executor.is_healthy is True

    def test_stats(self):
        """Test combined stats."""
        executor = ResilientExecutor("test")
        stats = executor.stats

        assert "retry" in stats
        assert "circuit_state" in stats


class TestWithRetryDecorator:
    """Tests for @with_retry decorator."""

    @pytest.mark.asyncio
    async def test_decorator_retries(self):
        """Test decorator applies retry logic."""
        call_count = 0

        @with_retry(max_attempts=3, backoff_base=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temp")
            return "ok"

        result = await flaky()

        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_decorator_raises_on_exhausted(self):
        """Test decorator raises when retries exhausted."""

        @with_retry(max_attempts=2, backoff_base=0.01)
        async def always_fails():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await always_fails()


class TestWithCircuitBreakerDecorator:
    """Tests for @with_circuit_breaker decorator."""

    @pytest.mark.asyncio
    async def test_decorator_applies_breaker(self):
        """Test decorator applies circuit breaker."""
        call_count = 0

        @with_circuit_breaker("test", failure_threshold=2, timeout=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            raise ValueError("error")

        for i in range(2):
            with pytest.raises(ValueError):
                await flaky()

        with pytest.raises(CircuitOpenError):
            await flaky()

    @pytest.mark.asyncio
    async def test_decorator_with_fallback(self):
        """Test decorator with fallback."""

        async def fallback():
            return "fallback"

        @with_circuit_breaker("test", failure_threshold=1, fallback=fallback)
        async def fails():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await fails()

        # Circuit open, should use fallback
        result = await fails()
        assert result == "fallback"


class TestRetryResult:
    """Tests for RetryResult."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = RetryResult(
            success=True,
            result="data",
            attempts=2,
            total_delay=1.5,
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["attempts"] == 2
        assert d["total_delay"] == 1.5
        assert d["last_error"] is None

    def test_to_dict_with_error(self):
        """Test dict with error."""
        result = RetryResult(
            success=False,
            attempts=3,
            last_exception=ValueError("test error"),
        )

        d = result.to_dict()

        assert d["success"] is False
        assert d["last_error"] == "test error"
