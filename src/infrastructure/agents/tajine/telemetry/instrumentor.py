# src/infrastructure/agents/tajine/telemetry/instrumentor.py
"""Instrumentation utilities for TAJINE telemetry - decorators, context managers, and recording functions."""

import logging
import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps

from src.infrastructure.agents.tajine.telemetry.metrics import (
    autonomy_level,
    bandit_pulls,
    bandit_rewards,
    bandit_ucb_score,
    cache_hits,
    cache_misses,
    circuit_breaker_state,
    cognitive_level_duration,
    cognitive_recommendations,
    cognitive_signals,
    cognitive_theories,
    fallbacks_used,
    human_interventions,
    hunt_duration,
    hunt_total,
    llm_errors,
    llm_latency,
    llm_tokens_total,
    score_alpha,
    score_coherence,
    score_combined,
    score_fiabilite,
    trust_score,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# LANGFUSE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

# Check if Langfuse is enabled via environment (respects LANGFUSE_ENABLED=false)
_langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"

if _langfuse_enabled:
    try:
        from langfuse.decorators import langfuse_context
        from langfuse.decorators import observe as langfuse_observe

        LANGFUSE_AVAILABLE = True
    except ImportError:
        LANGFUSE_AVAILABLE = False
        langfuse_observe = None
        langfuse_context = None
else:
    # Langfuse explicitly disabled
    LANGFUSE_AVAILABLE = False
    langfuse_observe = None
    langfuse_context = None


def langfuse_available() -> bool:
    """Check if Langfuse is available."""
    return LANGFUSE_AVAILABLE


def get_langfuse_context():
    """Get the Langfuse context if available."""
    if LANGFUSE_AVAILABLE:
        return langfuse_context
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════


def trace_hunt(mode: str):
    """
    Async decorator for DataHunter.hunt() operations.

    Args:
        mode: Hunt mode (e.g., "sequential", "parallel", "adaptive")
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract territory if available
            territory = kwargs.get("territory", "unknown")

            # Increment hunt counter
            hunt_total.labels(mode=mode, territory=territory).inc()

            # Time the operation
            start_time = time.perf_counter()
            try:
                # Wrap with Langfuse if available
                if LANGFUSE_AVAILABLE:
                    langfuse_wrapped = langfuse_observe(name=f"hunt_{mode}")
                    result = await langfuse_wrapped(func)(*args, **kwargs)
                else:
                    result = await func(*args, **kwargs)

                return result
            finally:
                duration = time.perf_counter() - start_time
                hunt_duration.labels(mode=mode).observe(duration)

        return wrapper

    return decorator


def trace_cognitive(level: str):
    """
    Async decorator for cognitive level operations.

    Args:
        level: Cognitive level (e.g., "signal", "theory", "synthesis")
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Time the cognitive operation
            start_time = time.perf_counter()
            try:
                # Wrap with Langfuse if available
                if LANGFUSE_AVAILABLE:
                    langfuse_wrapped = langfuse_observe(name=f"cognitive_{level}")
                    result = await langfuse_wrapped(func)(*args, **kwargs)
                else:
                    result = await func(*args, **kwargs)

                return result
            finally:
                duration = time.perf_counter() - start_time
                cognitive_level_duration.labels(level=level).observe(duration)

        return wrapper

    return decorator


def trace_llm(model: str):
    """
    Async decorator for LLM calls.

    Args:
        model: LLM model name (e.g., "gpt-4", "claude-3")
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Time the LLM call
            start_time = time.perf_counter()

            try:
                # Wrap with Langfuse if available
                if LANGFUSE_AVAILABLE:
                    langfuse_wrapped = langfuse_observe(name=f"llm_{model}")
                    result = await langfuse_wrapped(func)(*args, **kwargs)
                else:
                    result = await func(*args, **kwargs)

                # Record latency
                duration = time.perf_counter() - start_time
                llm_latency.labels(model=model).observe(duration)

                # Extract token usage if available in result
                if hasattr(result, "usage") and result.usage:
                    usage = result.usage
                    if hasattr(usage, "input_tokens"):
                        llm_tokens_total.labels(model=model, type="input").inc(usage.input_tokens)
                    if hasattr(usage, "output_tokens"):
                        llm_tokens_total.labels(model=model, type="output").inc(usage.output_tokens)

                return result
            except Exception as e:
                # Record error
                error_type = type(e).__name__
                llm_errors.labels(model=model, error_type=error_type).inc()
                raise

        return wrapper

    return decorator


def trace_bandit(func: Callable) -> Callable:
    """
    Decorator for bandit operations.

    This decorator can be used on sync or async functions.
    """
    if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:
        # Async function
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if LANGFUSE_AVAILABLE:
                langfuse_wrapped = langfuse_observe(name="bandit_operation")
                result = await langfuse_wrapped(func)(*args, **kwargs)
            else:
                result = await func(*args, **kwargs)
            return result

        return async_wrapper
    else:
        # Sync function
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if LANGFUSE_AVAILABLE:
                langfuse_wrapped = langfuse_observe(name="bandit_operation")
                result = langfuse_wrapped(func)(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            return result

        return sync_wrapper


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT MANAGERS
# ═══════════════════════════════════════════════════════════════════════════════


@contextmanager
def track_cache(source: str, hit: bool):
    """
    Context manager for tracking cache hits and misses.

    Args:
        source: Data source name
        hit: Whether this was a cache hit (True) or miss (False)
    """
    try:
        yield
    finally:
        if hit:
            cache_hits.labels(source=source).inc()
        else:
            cache_misses.labels(source=source).inc()


@contextmanager
def track_fallback(from_source: str, to_source: str):
    """
    Context manager for tracking fallback operations.

    Args:
        from_source: Original source that failed
        to_source: Fallback source being used
    """
    try:
        yield
    finally:
        fallbacks_used.labels(from_source=from_source, to_source=to_source).inc()


# ═══════════════════════════════════════════════════════════════════════════════
# RECORDING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def record_score_3d(
    fiabilite: float, coherence: float, alpha: float, combined: float, source: str
) -> None:
    """
    Record 3D evaluation scores.

    Args:
        fiabilite: Reliability score (0-1)
        coherence: Coherence score (0-1)
        alpha: Novelty/Alpha score (0-1)
        combined: Combined score (0-1)
        source: Data source name
    """
    score_fiabilite.labels(source=source).observe(fiabilite)
    score_coherence.observe(coherence)
    score_alpha.observe(alpha)
    score_combined.observe(combined)


def record_bandit_pull(source: str, reward: float) -> None:
    """
    Record a bandit arm pull and its reward.

    Args:
        source: Data source/arm name
        reward: Reward value (typically 0-1)
    """
    bandit_pulls.labels(source=source).inc()
    bandit_rewards.labels(source=source).observe(reward)


def update_bandit_ucb(source: str, ucb_score: float) -> None:
    """
    Update the UCB score for a bandit arm.

    Args:
        source: Data source/arm name
        ucb_score: Upper Confidence Bound score
    """
    bandit_ucb_score.labels(source=source).set(ucb_score)


def record_signal(signal_type: str) -> None:
    """
    Record a cognitive signal detection.

    Args:
        signal_type: Type of signal detected
    """
    cognitive_signals.labels(type=signal_type).inc()


def record_theory(theory: str) -> None:
    """
    Record application of a theory.

    Args:
        theory: Theory name or identifier
    """
    cognitive_theories.labels(theory=theory).inc()


def record_recommendation(rec_type: str) -> None:
    """
    Record a recommendation.

    Args:
        rec_type: Type of recommendation
    """
    cognitive_recommendations.labels(type=rec_type).inc()


def update_trust(territory: str, score: float) -> None:
    """
    Update trust score for a territory.

    Args:
        territory: Territory identifier
        score: Trust score (0-1)
    """
    trust_score.labels(territory=territory).set(score)


def update_autonomy(level: int) -> None:
    """
    Update the autonomy level.

    Args:
        level: Autonomy level (1-5)
    """
    autonomy_level.set(level)


def record_human_intervention(reason: str) -> None:
    """
    Record a human intervention.

    Args:
        reason: Reason for intervention
    """
    human_interventions.labels(reason=reason).inc()


def set_circuit_breaker(source: str, is_open: bool) -> None:
    """
    Set circuit breaker state for a source.

    Args:
        source: Data source name
        is_open: True if circuit is open (broken), False if closed (working)
    """
    circuit_breaker_state.labels(source=source).set(1.0 if is_open else 0.0)
