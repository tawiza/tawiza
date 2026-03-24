"""Agent Resilience - Retry and circuit breaker patterns.

This module provides robust retry patterns for agent operations:
- Exponential backoff with jitter
- Configurable retry policies
- Circuit breaker pattern for cascade failure prevention
- Fallback handlers

Main components:
- RetryHandler: Executes functions with retry logic
- RetryConfig: Configuration for retry behavior
- CircuitBreaker: Protects against cascade failures
- ResilientExecutor: Combines retry and circuit breaker
- Decorators: @with_retry, @with_circuit_breaker

Example:
    >>> from src.infrastructure.agents.resilience import (
    ...     with_retry,
    ...     RetryStrategy,
    ...     ResilientExecutor,
    ... )
    >>>
    >>> # Using decorator
    >>> @with_retry(max_attempts=5, backoff_base=2.0)
    >>> async def fetch_data():
    ...     return await external_api_call()
    >>>
    >>> # Using ResilientExecutor
    >>> executor = ResilientExecutor("api_service")
    >>> result = await executor.execute(
    ...     api_call,
    ...     fallback=lambda: {"cached": True}
    ... )
"""

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

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitOpenError",
    "CircuitState",
    "ResilientExecutor",
    "RetryConfig",
    "RetryHandler",
    "RetryResult",
    "RetryStrategy",
    "with_circuit_breaker",
    "with_retry",
]
