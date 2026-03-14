"""
Retry logic with exponential backoff and jitter.

Features:
- Exponential backoff (delay doubles each retry)
- Jitter (random variation to prevent thundering herd)
- Configurable exceptions to retry on
- Automatic logging
- Type-safe with async support
"""

import asyncio
import random
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from loguru import logger

P = ParamSpec("P")
T = TypeVar("T")


class RetryConfig:
    """Configuration for retry logic."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: tuple[type[Exception], ...] = (Exception,),
        retry_on_return: Callable[[Any], bool] | None = None,
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts (including first try)
            base_delay: Initial delay in seconds
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential backoff (2.0 = double each time)
            jitter: Add random jitter to prevent thundering herd
            exceptions: Tuple of exceptions to retry on
            retry_on_return: Optional function to check if return value should trigger retry
                           Example: lambda x: x is None or x.get("status") == "error"
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if base_delay <= 0:
            raise ValueError("base_delay must be > 0")
        if max_delay < base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if exponential_base < 1:
            raise ValueError("exponential_base must be >= 1")

        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions
        self.retry_on_return = retry_on_return

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Calculate exponential delay
        delay = min(self.base_delay * (self.exponential_base**attempt), self.max_delay)

        # Add jitter (±25%)
        if self.jitter:
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)

        return max(0, delay)


def with_retry(config: RetryConfig | None = None):
    """
    Decorator to add retry logic to async functions.

    Usage:
        @with_retry(RetryConfig(max_attempts=5, base_delay=2.0))
        async def call_api():
            return await client.get("/endpoint")

        @with_retry()  # Use default config
        async def fragile_operation():
            # May fail, will retry automatically
            pass

        # Retry on specific exceptions only
        @with_retry(RetryConfig(exceptions=(httpx.TimeoutException, httpx.ConnectError)))
        async def network_call():
            pass

        # Retry based on return value
        @with_retry(RetryConfig(retry_on_return=lambda x: x is None))
        async def might_return_none():
            return None  # Will retry

    Args:
        config: Retry configuration (None = use defaults)

    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            last_result = None

            for attempt in range(config.max_attempts):
                try:
                    # Try to execute function
                    result = await func(*args, **kwargs)

                    # Check if result should trigger retry
                    if config.retry_on_return and config.retry_on_return(result):
                        if attempt < config.max_attempts - 1:
                            delay = config.get_delay(attempt)
                            logger.warning(
                                f"⚠️ {func.__name__} returned retry-triggering value "
                                f"(attempt {attempt + 1}/{config.max_attempts}), "
                                f"retrying in {delay:.2f}s"
                            )
                            await asyncio.sleep(delay)
                            last_result = result
                            continue
                        else:
                            logger.warning(
                                f"⚠️ {func.__name__} returned retry-triggering value "
                                f"after {config.max_attempts} attempts, giving up"
                            )
                            return result

                    # Log success if this was a retry
                    if attempt > 0:
                        logger.info(f"✅ {func.__name__} succeeded on attempt {attempt + 1}")

                    return result

                except config.exceptions as e:
                    last_exception = e

                    # Don't retry on last attempt
                    if attempt == config.max_attempts - 1:
                        logger.error(
                            f"❌ {func.__name__} failed after {config.max_attempts} attempts: {e}"
                        )
                        break

                    # Calculate delay and wait
                    delay = config.get_delay(attempt)
                    logger.warning(
                        f"⚠️ {func.__name__} failed (attempt {attempt + 1}/{config.max_attempts}), "
                        f"retrying in {delay:.2f}s: {type(e).__name__}: {e}"
                    )
                    await asyncio.sleep(delay)

            # All attempts failed
            if last_exception:
                raise last_exception

            # All attempts returned retry-triggering value
            return last_result

        return wrapper

    return decorator


async def retry_async[**P, T](
    func: Callable[P, T], *args: P.args, config: RetryConfig | None = None, **kwargs: P.kwargs
) -> T:
    """
    Retry an async function with exponential backoff.

    Functional alternative to @with_retry decorator.

    Usage:
        result = await retry_async(
            call_api,
            "arg1", "arg2",
            config=RetryConfig(max_attempts=5),
            kwarg1="value"
        )

    Args:
        func: Async function to retry
        *args: Positional arguments to pass to func
        config: Retry configuration
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result from func

    Raises:
        Last exception if all retries fail
    """
    if config is None:
        config = RetryConfig()

    @with_retry(config)
    async def _wrapper():
        return await func(*args, **kwargs)

    return await _wrapper()


# Predefined retry configs for common scenarios

# Network operations (longer delays, more retries)
RETRY_NETWORK = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
)

# Database operations (quick retries)
RETRY_DATABASE = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    exponential_base=2.0,
    jitter=True,
)

# File I/O operations
RETRY_FILE_IO = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=False,  # No jitter for file I/O
)

# Quick operations (fast retries, fewer attempts)
RETRY_QUICK = RetryConfig(
    max_attempts=2,
    base_delay=0.1,
    max_delay=1.0,
    exponential_base=2.0,
    jitter=False,
)

# Long operations (patient retries)
RETRY_PATIENT = RetryConfig(
    max_attempts=10,
    base_delay=5.0,
    max_delay=120.0,
    exponential_base=1.5,  # Slower growth
    jitter=True,
)
