# src/infrastructure/agents/tajine/telemetry/metrics.py
"""Prometheus metrics for TAJINE agent."""

import logging
from typing import Optional

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Info, start_http_server

logger = logging.getLogger(__name__)

# Custom registry to avoid conflicts
TAJINE_REGISTRY = CollectorRegistry()

# ═══════════════════════════════════════════════════════════════════════════════
# DATAHUNTER METRICS
# ═══════════════════════════════════════════════════════════════════════════════

hunt_total = Counter(
    "tajine_hunt_total",
    "Total hunts executed",
    ["mode", "territory"],
    registry=TAJINE_REGISTRY,
)

hunt_duration = Histogram(
    "tajine_hunt_duration_seconds",
    "Hunt duration in seconds",
    ["mode"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
    registry=TAJINE_REGISTRY,
)

cache_hits = Counter(
    "tajine_cache_hits_total",
    "Cache hits by source",
    ["source"],
    registry=TAJINE_REGISTRY,
)

cache_misses = Counter(
    "tajine_cache_misses_total",
    "Cache misses by source",
    ["source"],
    registry=TAJINE_REGISTRY,
)

fallbacks_used = Counter(
    "tajine_fallbacks_total",
    "Fallbacks triggered",
    ["from_source", "to_source"],
    registry=TAJINE_REGISTRY,
)

circuit_breaker_state = Gauge(
    "tajine_circuit_breaker_open",
    "Circuit breaker state (1=open, 0=closed)",
    ["source"],
    registry=TAJINE_REGISTRY,
)

# ═══════════════════════════════════════════════════════════════════════════════
# BANDIT METRICS
# ═══════════════════════════════════════════════════════════════════════════════

bandit_pulls = Counter(
    "tajine_bandit_pulls_total",
    "Bandit arm pulls",
    ["source"],
    registry=TAJINE_REGISTRY,
)

bandit_rewards = Histogram(
    "tajine_bandit_reward",
    "Reward distribution by source",
    ["source"],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=TAJINE_REGISTRY,
)

bandit_ucb_score = Gauge(
    "tajine_bandit_ucb_score",
    "Current UCB score by source",
    ["source"],
    registry=TAJINE_REGISTRY,
)

# ═══════════════════════════════════════════════════════════════════════════════
# EVALUATOR METRICS (3D Score)
# ═══════════════════════════════════════════════════════════════════════════════

score_fiabilite = Histogram(
    "tajine_score_fiabilite",
    "Fiabilité (reliability) scores",
    ["source"],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=TAJINE_REGISTRY,
)

score_coherence = Histogram(
    "tajine_score_coherence",
    "Cohérence (coherence) scores",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=TAJINE_REGISTRY,
)

score_alpha = Histogram(
    "tajine_score_alpha",
    "Alpha (novelty) scores",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=TAJINE_REGISTRY,
)

score_combined = Histogram(
    "tajine_score_combined",
    "Combined 3D scores",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=TAJINE_REGISTRY,
)

# ═══════════════════════════════════════════════════════════════════════════════
# COGNITIVE ENGINE METRICS
# ═══════════════════════════════════════════════════════════════════════════════

cognitive_level_duration = Histogram(
    "tajine_cognitive_level_duration_seconds",
    "Duration per cognitive level",
    ["level"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
    registry=TAJINE_REGISTRY,
)

cognitive_signals = Counter(
    "tajine_signals_total",
    "Signals detected by type",
    ["type"],
    registry=TAJINE_REGISTRY,
)

cognitive_theories = Counter(
    "tajine_theories_applied_total",
    "Theories applied",
    ["theory"],
    registry=TAJINE_REGISTRY,
)

cognitive_recommendations = Counter(
    "tajine_recommendations_total",
    "Recommendations by type",
    ["type"],
    registry=TAJINE_REGISTRY,
)

# ═══════════════════════════════════════════════════════════════════════════════
# AUTONOMY & TRUST METRICS
# ═══════════════════════════════════════════════════════════════════════════════

trust_score = Gauge(
    "tajine_trust_score",
    "Current trust score by territory",
    ["territory"],
    registry=TAJINE_REGISTRY,
)

autonomy_level = Gauge(
    "tajine_autonomy_level",
    "Current autonomy level (1-5)",
    registry=TAJINE_REGISTRY,
)

human_interventions = Counter(
    "tajine_human_interventions_total",
    "Human interventions by reason",
    ["reason"],
    registry=TAJINE_REGISTRY,
)

# ═══════════════════════════════════════════════════════════════════════════════
# LLM METRICS
# ═══════════════════════════════════════════════════════════════════════════════

llm_tokens_total = Counter(
    "tajine_llm_tokens_total",
    "Tokens consumed",
    ["model", "type"],  # type: input|output
    registry=TAJINE_REGISTRY,
)

llm_cost_dollars = Counter(
    "tajine_llm_cost_dollars",
    "LLM costs in dollars",
    ["model"],
    registry=TAJINE_REGISTRY,
)

llm_latency = Histogram(
    "tajine_llm_latency_seconds",
    "LLM call latency",
    ["model"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
    registry=TAJINE_REGISTRY,
)

llm_errors = Counter(
    "tajine_llm_errors_total",
    "LLM errors",
    ["model", "error_type"],
    registry=TAJINE_REGISTRY,
)

# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE INFO
# ═══════════════════════════════════════════════════════════════════════════════

service_info = Info(
    "tajine_service",
    "Service information",
    registry=TAJINE_REGISTRY,
)


class MetricsServer:
    """Prometheus metrics HTTP server."""

    _instance: Optional["MetricsServer"] = None
    _started: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def start(self, port: int = 8000) -> None:
        """Start the metrics server."""
        if not self._started:
            try:
                start_http_server(port, registry=TAJINE_REGISTRY)
                self._started = True
                logger.info(f"Prometheus metrics server started on port {port}")
            except OSError as e:
                if "Address already in use" in str(e):
                    logger.warning(f"Metrics server already running on port {port}")
                else:
                    raise

    @property
    def is_running(self) -> bool:
        return self._started


# Convenience function
def start_metrics_server(port: int = 8000) -> MetricsServer:
    """Start the Prometheus metrics server."""
    server = MetricsServer()
    server.start(port)
    return server
