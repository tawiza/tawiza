"""Retry Mechanism - Resilient agent execution with automatic retries.

Provides robust retry patterns for agent operations:
- Exponential backoff with jitter
- Configurable retry policies
- Circuit breaker pattern
- Fallback handlers

Example:
    >>> @with_retry(max_attempts=3, backoff_base=2.0)
    >>> async def flaky_operation():
    ...     return await external_api_call()
"""

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from functools import wraps
from typing import Any, TypeVar

from loguru import logger


class RetryStrategy(StrEnum):
    """Retry backoff strategies."""

    FIXED = "fixed"                    # Fixed delay between retries
    EXPONENTIAL = "exponential"        # Exponential backoff
    EXPONENTIAL_JITTER = "exp_jitter"  # Exponential with random jitter
    LINEAR = "linear"                  # Linear backoff
    FIBONACCI = "fibonacci"            # Fibonacci sequence backoff


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (including initial)
        backoff_base: Base delay in seconds
        backoff_max: Maximum delay cap in seconds
        strategy: Backoff strategy to use
        jitter_factor: Random jitter factor (0.0 to 1.0)
        retryable_exceptions: Exception types to retry on
        non_retryable_exceptions: Exception types to never retry
        on_retry: Callback on each retry attempt
    """

    max_attempts: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    jitter_factor: float = 0.5
    retryable_exceptions: set[type[Exception]] = field(
        default_factory=lambda: {Exception}
    )
    non_retryable_exceptions: set[type[Exception]] = field(
        default_factory=set
    )
    on_retry: Callable | None = None

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        if self.strategy == RetryStrategy.FIXED:
            delay = self.backoff_base

        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.backoff_base * attempt

        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.backoff_base * (2 ** (attempt - 1))

        elif self.strategy == RetryStrategy.EXPONENTIAL_JITTER:
            base_delay = self.backoff_base * (2 ** (attempt - 1))
            jitter = random.uniform(0, self.jitter_factor * base_delay)
            delay = base_delay + jitter

        elif self.strategy == RetryStrategy.FIBONACCI:
            # Fibonacci sequence: 1, 1, 2, 3, 5, 8, 13...
            a, b = 1, 1
            for _ in range(attempt - 1):
                a, b = b, a + b
            delay = self.backoff_base * a

        else:
            delay = self.backoff_base

        return min(delay, self.backoff_max)

    def should_retry(self, exception: Exception) -> bool:
        """Determine if exception should trigger a retry.

        Args:
            exception: The exception that occurred

        Returns:
            True if should retry, False otherwise
        """
        # Never retry these
        for exc_type in self.non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False

        # Retry if in retryable set
        return any(isinstance(exception, exc_type) for exc_type in self.retryable_exceptions)


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    result: Any = None
    attempts: int = 0
    total_delay: float = 0.0
    last_exception: Exception | None = None
    attempt_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "attempts": self.attempts,
            "total_delay": self.total_delay,
            "last_error": str(self.last_exception) if self.last_exception else None,
        }


class RetryHandler:
    """Handles retry logic for operations.

    Example:
        >>> handler = RetryHandler(RetryConfig(max_attempts=5))
        >>> result = await handler.execute(flaky_function, arg1, arg2)
    """

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_retries": 0,
        }

    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> RetryResult:
        """Execute function with retry logic.

        Args:
            func: Function to execute (sync or async)
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            RetryResult with outcome details
        """
        self._stats["total_calls"] += 1

        result = RetryResult(success=False, attempts=0)

        for attempt in range(1, self.config.max_attempts + 1):
            result.attempts = attempt

            attempt_info = {
                "attempt": attempt,
                "started_at": datetime.now(UTC).isoformat(),
            }

            try:
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    value = await func(*args, **kwargs)
                else:
                    value = func(*args, **kwargs)

                # Success
                result.success = True
                result.result = value
                attempt_info["status"] = "success"
                result.attempt_history.append(attempt_info)

                self._stats["successful_calls"] += 1
                logger.debug(f"Operation succeeded on attempt {attempt}")

                return result

            except Exception as e:
                result.last_exception = e
                attempt_info["status"] = "failed"
                attempt_info["error"] = str(e)
                result.attempt_history.append(attempt_info)

                logger.warning(
                    f"Attempt {attempt}/{self.config.max_attempts} failed: {e}"
                )

                # Check if should retry
                if not self.config.should_retry(e):
                    logger.debug(f"Exception not retryable: {type(e).__name__}")
                    break

                # Check if more attempts available
                if attempt >= self.config.max_attempts:
                    logger.debug("Max attempts reached")
                    break

                # Calculate and apply delay
                delay = self.config.calculate_delay(attempt)
                result.total_delay += delay

                logger.debug(f"Waiting {delay:.2f}s before retry")
                await asyncio.sleep(delay)

                self._stats["total_retries"] += 1

                # Callback
                if self.config.on_retry:
                    try:
                        if asyncio.iscoroutinefunction(self.config.on_retry):
                            await self.config.on_retry(attempt, e, delay)
                        else:
                            self.config.on_retry(attempt, e, delay)
                    except Exception as callback_error:
                        logger.error(f"Retry callback failed: {callback_error}")

        # All attempts exhausted
        self._stats["failed_calls"] += 1

        return result

    @property
    def stats(self) -> dict[str, int]:
        """Get retry statistics."""
        return self._stats.copy()


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker.

    Attributes:
        failure_threshold: Failures before opening circuit
        success_threshold: Successes to close from half-open
        timeout: Seconds to wait before half-open
        half_open_max_calls: Max calls allowed in half-open
    """

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 30.0
    half_open_max_calls: int = 3


class CircuitBreaker:
    """Circuit breaker for preventing cascade failures.

    Protects systems by:
    - Tracking failure rates
    - Opening circuit when threshold exceeded
    - Automatically testing recovery
    - Providing fallback options

    States:
    - CLOSED: Normal operation, tracking failures
    - OPEN: Rejecting calls, waiting for timeout
    - HALF_OPEN: Testing if service recovered

    Example:
        >>> breaker = CircuitBreaker("external_api")
        >>> try:
        ...     result = await breaker.call(api_request)
        ... except CircuitOpenError:
        ...     result = fallback_response()
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0

        logger.info(f"Circuit breaker '{name}' initialized")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        # Check if should transition from OPEN to HALF_OPEN
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
            if elapsed >= self.config.timeout:
                self._transition_to(CircuitState.HALF_OPEN)

        return self._state

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state."""
        old_state = self._state
        self._state = new_state

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0

        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0

        logger.info(
            f"Circuit '{self.name}' transitioned: {old_state.value} -> {new_state.value}"
        )

    def _record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

    def _record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now(UTC)

        if self._state == CircuitState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)

        elif self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)

    async def call(
        self,
        func: Callable,
        *args,
        fallback: Callable | None = None,
        **kwargs
    ) -> Any:
        """Execute function through circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments
            fallback: Fallback function if circuit is open
            **kwargs: Keyword arguments

        Returns:
            Function result or fallback result

        Raises:
            CircuitOpenError: If circuit is open and no fallback
        """
        current_state = self.state

        # Check if circuit allows call
        if current_state == CircuitState.OPEN:
            if fallback:
                logger.debug(f"Circuit '{self.name}' open, using fallback")
                if asyncio.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                return fallback(*args, **kwargs)
            raise CircuitOpenError(f"Circuit '{self.name}' is open")

        if current_state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.config.half_open_max_calls:
                if fallback:
                    if asyncio.iscoroutinefunction(fallback):
                        return await fallback(*args, **kwargs)
                    return fallback(*args, **kwargs)
                raise CircuitOpenError(f"Circuit '{self.name}' half-open limit reached")
            self._half_open_calls += 1

        # Execute call
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            self._record_success()
            return result

        except Exception:
            self._record_failure()
            raise

    def reset(self) -> None:
        """Manually reset circuit to closed state."""
        self._transition_to(CircuitState.CLOSED)
        logger.info(f"Circuit '{self.name}' manually reset")


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Decorator for easy retry

T = TypeVar("T")


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    backoff_max: float = 60.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER,
    retryable_exceptions: set[type[Exception]] | None = None,
    on_retry: Callable | None = None,
) -> Callable:
    """Decorator to add retry logic to a function.

    Example:
        >>> @with_retry(max_attempts=5, backoff_base=2.0)
        >>> async def fetch_data():
        ...     return await api.get("/data")
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        config = RetryConfig(
            max_attempts=max_attempts,
            backoff_base=backoff_base,
            backoff_max=backoff_max,
            strategy=strategy,
            retryable_exceptions=retryable_exceptions or {Exception},
            on_retry=on_retry,
        )
        handler = RetryHandler(config)

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            result = await handler.execute(func, *args, **kwargs)
            if not result.success:
                raise result.last_exception
            return result.result

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            result = asyncio.run(handler.execute(func, *args, **kwargs))
            if not result.success:
                raise result.last_exception
            return result.result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def with_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout: float = 30.0,
    fallback: Callable | None = None,
) -> Callable:
    """Decorator to add circuit breaker to a function.

    Example:
        >>> @with_circuit_breaker("api", failure_threshold=3)
        >>> async def call_api():
        ...     return await api.request()
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        timeout=timeout,
    )
    breaker = CircuitBreaker(name, config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await breaker.call(func, *args, fallback=fallback, **kwargs)

        return wrapper

    return decorator


# Utility: Combine retry and circuit breaker

class ResilientExecutor:
    """Combines retry and circuit breaker for maximum resilience.

    Provides:
    - Automatic retries with backoff
    - Circuit breaker protection
    - Fallback handling
    - Comprehensive metrics

    Example:
        >>> executor = ResilientExecutor("external_service")
        >>> result = await executor.execute(
        ...     api_call,
        ...     fallback=lambda: {"cached": True}
        ... )
    """

    def __init__(
        self,
        name: str,
        retry_config: RetryConfig | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
    ):
        self.name = name
        self.retry_handler = RetryHandler(retry_config)
        self.circuit_breaker = CircuitBreaker(name, circuit_config)

    async def execute(
        self,
        func: Callable,
        *args,
        fallback: Callable | None = None,
        **kwargs
    ) -> Any:
        """Execute with full resilience.

        First applies circuit breaker, then retry logic.
        """
        async def retryable_call():
            result = await self.retry_handler.execute(func, *args, **kwargs)
            if not result.success:
                raise result.last_exception
            return result.result

        return await self.circuit_breaker.call(
            retryable_call,
            fallback=fallback,
        )

    @property
    def is_healthy(self) -> bool:
        """Check if executor is healthy (circuit closed)."""
        return self.circuit_breaker.state == CircuitState.CLOSED

    @property
    def stats(self) -> dict[str, Any]:
        """Get combined statistics."""
        return {
            "retry": self.retry_handler.stats,
            "circuit_state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker._failure_count,
        }
