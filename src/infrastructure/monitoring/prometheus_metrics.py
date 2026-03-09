"""Prometheus metrics for monitoring.

This module provides Prometheus metrics for monitoring the application's
performance, ML operations, and business metrics.
"""

from prometheus_client import Counter, Gauge, Histogram, Summary

# ==============================================================================
# API Metrics
# ==============================================================================

# HTTP requests
http_requests_total = Counter(
    "tawiza_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "tawiza_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ==============================================================================
# ML Model Metrics
# ==============================================================================

# Model training
training_jobs_total = Counter(
    "tawiza_training_jobs_total",
    "Total training jobs",
    ["status", "trigger"],
)

training_duration_seconds = Histogram(
    "tawiza_training_duration_seconds",
    "Training job duration",
    ["status"],
    buckets=(60, 300, 600, 1800, 3600, 7200, 14400),  # 1min to 4h
)

training_accuracy = Gauge(
    "tawiza_training_accuracy",
    "Model training accuracy",
    ["model_name", "version"],
)

training_loss = Gauge(
    "tawiza_training_loss",
    "Model training loss",
    ["model_name", "version"],
)

# Model deployment
models_deployed_total = Counter(
    "tawiza_models_deployed_total",
    "Total models deployed",
    ["deployment_strategy"],
)

models_active = Gauge(
    "tawiza_models_active",
    "Number of currently active/deployed models",
)

model_traffic_percentage = Gauge(
    "tawiza_model_traffic_percentage",
    "Traffic percentage for canary deployments",
    ["model_id", "model_name", "version"],
)

# ==============================================================================
# Inference Metrics
# ==============================================================================

# Predictions
predictions_total = Counter(
    "tawiza_predictions_total",
    "Total predictions made",
    ["model_id", "model_name", "status"],
)

prediction_latency_seconds = Histogram(
    "tawiza_prediction_latency_seconds",
    "Prediction latency",
    ["model_id", "model_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)

prediction_tokens_generated = Histogram(
    "tawiza_prediction_tokens_generated",
    "Number of tokens generated per prediction",
    ["model_id"],
    buckets=(10, 50, 100, 250, 500, 1000, 2000),
)

# Prediction errors
prediction_errors_total = Counter(
    "tawiza_prediction_errors_total",
    "Total prediction errors",
    ["model_id", "error_type"],
)

# ==============================================================================
# Feedback and Learning Metrics
# ==============================================================================

# User feedback
feedback_total = Counter(
    "tawiza_feedback_total",
    "Total user feedback received",
    ["feedback_type", "model_id"],
)

feedback_positive_ratio = Gauge(
    "tawiza_feedback_positive_ratio",
    "Ratio of positive feedback",
    ["model_id"],
)

# Dataset metrics
dataset_size = Gauge(
    "tawiza_dataset_size",
    "Dataset size (number of samples)",
    ["dataset_name", "dataset_type"],
)

annotation_progress = Gauge(
    "tawiza_annotation_progress",
    "Dataset annotation progress percentage",
    ["dataset_name"],
)

# Retraining triggers
retraining_triggered_total = Counter(
    "tawiza_retraining_triggered_total",
    "Total retraining triggers",
    ["trigger_reason"],
)

# ==============================================================================
# Data Quality Metrics
# ==============================================================================

# Data drift
data_drift_score = Gauge(
    "tawiza_data_drift_score",
    "Data drift score",
    ["model_id"],
)

data_drift_detected_total = Counter(
    "tawiza_data_drift_detected_total",
    "Total data drift detections",
    ["model_id"],
)

# Model performance degradation
model_accuracy_current = Gauge(
    "tawiza_model_accuracy_current",
    "Current model accuracy in production",
    ["model_id", "model_name"],
)

model_performance_degradation = Counter(
    "tawiza_model_performance_degradation_total",
    "Total performance degradation events",
    ["model_id"],
)

# ==============================================================================
# Resource Metrics
# ==============================================================================

# GPU utilization (if available)
gpu_utilization_percent = Gauge(
    "tawiza_gpu_utilization_percent",
    "GPU utilization percentage",
    ["gpu_id"],
)

gpu_memory_used_bytes = Gauge(
    "tawiza_gpu_memory_used_bytes",
    "GPU memory used in bytes",
    ["gpu_id"],
)

# MLflow metrics
mlflow_experiments_total = Gauge(
    "tawiza_mlflow_experiments_total",
    "Total number of MLflow experiments",
)

mlflow_runs_total = Gauge(
    "tawiza_mlflow_runs_total",
    "Total number of MLflow runs",
)

# Storage
storage_models_bytes = Gauge(
    "tawiza_storage_models_bytes",
    "Total storage used by models in bytes",
)

storage_datasets_bytes = Gauge(
    "tawiza_storage_datasets_bytes",
    "Total storage used by datasets in bytes",
)

# ==============================================================================
# Cache Metrics
# ==============================================================================

# Multi-level cache
cache_hits_total = Counter(
    "tawiza_cache_hits_total",
    "Total cache hits",
    ["level", "cache_name"],  # level: l1, l2, l3
)

cache_misses_total = Counter(
    "tawiza_cache_misses_total",
    "Total cache misses",
    ["cache_name"],
)

cache_operations_total = Counter(
    "tawiza_cache_operations_total",
    "Total cache operations",
    ["operation", "cache_name"],  # operation: get, put, delete
)

cache_size = Gauge(
    "tawiza_cache_size",
    "Current cache size (items)",
    ["level", "cache_name"],
)

cache_capacity = Gauge(
    "tawiza_cache_capacity",
    "Cache capacity",
    ["level", "cache_name"],
)

cache_hit_rate = Gauge(
    "tawiza_cache_hit_rate",
    "Cache hit rate percentage",
    ["level", "cache_name"],
)

cache_evictions_total = Counter(
    "tawiza_cache_evictions_total",
    "Total cache evictions",
    ["level", "cache_name"],
)

# Redis specific
redis_connection_status = Gauge(
    "tawiza_redis_connection_status",
    "Redis connection status (1=connected, 0=disconnected)",
)

redis_latency_seconds = Histogram(
    "tawiza_redis_latency_seconds",
    "Redis operation latency",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

# ==============================================================================
# Database Metrics
# ==============================================================================

# Connection pool
db_pool_size = Gauge(
    "tawiza_db_pool_size",
    "Database connection pool size",
)

db_pool_checked_out = Gauge(
    "tawiza_db_pool_checked_out",
    "Database connections checked out from pool",
)

db_pool_overflow = Gauge(
    "tawiza_db_pool_overflow",
    "Database connection pool overflow count",
)

# Query statistics
db_queries_total = Counter(
    "tawiza_db_queries_total",
    "Total database queries",
    ["query_type"],  # select, insert, update, delete
)

db_query_duration_seconds = Histogram(
    "tawiza_db_query_duration_seconds",
    "Database query duration",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

db_slow_queries_total = Counter(
    "tawiza_db_slow_queries_total",
    "Total slow database queries",
)

db_errors_total = Counter(
    "tawiza_db_errors_total",
    "Total database errors",
    ["error_type"],
)

db_connection_status = Gauge(
    "tawiza_db_connection_status",
    "Database connection status (1=healthy, 0=unhealthy)",
)

# ==============================================================================
# Business Metrics
# ==============================================================================

# Active users
active_users_total = Gauge(
    "tawiza_active_users_total",
    "Number of active users",
    ["time_period"],  # "1h", "24h", "7d"
)

# API usage
api_calls_per_user = Summary(
    "tawiza_api_calls_per_user",
    "API calls per user",
)

# Cost metrics (if tracking costs)
inference_cost_usd = Counter(
    "tawiza_inference_cost_usd",
    "Estimated inference cost in USD",
    ["model_id"],
)

training_cost_usd = Counter(
    "tawiza_training_cost_usd",
    "Estimated training cost in USD",
    ["model_id"],
)

# ==============================================================================
# LLM Cache Metrics
# ==============================================================================

# LLM cache hits/misses
llm_cache_hits_total = Counter(
    "tawiza_llm_cache_hits_total",
    "Total LLM cache hits",
    ["model_type"],  # embedding, code, chat, vision
)

llm_cache_misses_total = Counter(
    "tawiza_llm_cache_misses_total",
    "Total LLM cache misses",
    ["model_type"],
)

llm_cache_skipped_total = Counter(
    "tawiza_llm_cache_skipped_total",
    "Total requests skipped (high temperature)",
    ["model_type"],
)

# Tokens saved by caching
llm_cache_tokens_saved = Counter(
    "tawiza_llm_cache_tokens_saved",
    "Estimated tokens saved by LLM cache",
    ["model_type"],
)

# Cache hit rate gauge
llm_cache_hit_rate = Gauge(
    "tawiza_llm_cache_hit_rate",
    "LLM cache hit rate percentage",
    ["model_type"],
)

# Response latency comparison
llm_cached_response_latency = Histogram(
    "tawiza_llm_cached_response_latency_seconds",
    "Latency for cached LLM responses",
    ["model_type"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05),  # sub-ms to 50ms
)

llm_uncached_response_latency = Histogram(
    "tawiza_llm_uncached_response_latency_seconds",
    "Latency for uncached LLM responses (actual inference)",
    ["model_type"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),  # 100ms to 60s
)
