"""Tests for CLI v3 metrics system."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.cli.v3.metrics.collector import MetricsCollector
from src.cli.v3.metrics.schema import METRICS_SCHEMA, MetricCategory, MetricPoint
from src.cli.v3.metrics.storage import MetricsStorage


class TestMetricSchema:
    """Tests for metrics schema."""

    def test_all_categories_defined(self):
        """Should have all expected categories."""
        expected = {"gpu", "system", "ollama", "agents", "training", "services"}
        actual = {cat.value for cat in MetricCategory}
        assert expected == actual

    def test_schema_has_metrics(self):
        """Each category should have metrics defined."""
        for category in MetricCategory:
            assert category in METRICS_SCHEMA
            assert len(METRICS_SCHEMA[category]) > 0


class TestMetricsStorage:
    """Tests for MetricsStorage."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_metrics.db"
            yield MetricsStorage(db_path)

    def test_record_single_metric(self, temp_storage):
        """Should record a single metric."""
        temp_storage.record(MetricCategory.GPU, "utilization", 45.5)

        point = temp_storage.get_latest(MetricCategory.GPU, "utilization")
        assert point is not None
        assert point.value == 45.5

    def test_record_batch(self, temp_storage):
        """Should record multiple metrics at once."""
        temp_storage.record_batch(
            {
                "gpu": {"utilization": 50.0, "temperature": 72.0},
                "system": {"cpu_percent": 30.0},
            }
        )

        gpu = temp_storage.get_latest(MetricCategory.GPU, "utilization")
        cpu = temp_storage.get_latest(MetricCategory.SYSTEM, "cpu_percent")

        assert gpu is not None
        assert gpu.value == 50.0
        assert cpu is not None
        assert cpu.value == 30.0

    def test_query_with_time_range(self, temp_storage):
        """Should filter by time range."""
        # Record some metrics
        temp_storage.record(MetricCategory.GPU, "utilization", 40.0)
        temp_storage.record(MetricCategory.GPU, "utilization", 50.0)

        now = datetime.now()
        results = temp_storage.query(
            MetricCategory.GPU,
            "utilization",
            start_time=now - timedelta(hours=1),
        )

        assert len(results) >= 2

    def test_get_summary(self, temp_storage):
        """Should return summary statistics."""
        for value in [10, 20, 30, 40, 50]:
            temp_storage.record(MetricCategory.GPU, "utilization", float(value))

        summary = temp_storage.get_summary(MetricCategory.GPU, "utilization")

        assert summary is not None
        assert summary.min_value == 10.0
        assert summary.max_value == 50.0
        assert summary.avg_value == 30.0
        assert summary.count == 5

    def test_get_categories(self, temp_storage):
        """Should list categories with data."""
        temp_storage.record(MetricCategory.GPU, "utilization", 50.0)
        temp_storage.record(MetricCategory.SYSTEM, "cpu_percent", 30.0)

        categories = temp_storage.get_categories()

        assert MetricCategory.GPU in categories
        assert MetricCategory.SYSTEM in categories

    def test_get_names(self, temp_storage):
        """Should list metric names for category."""
        temp_storage.record(MetricCategory.GPU, "utilization", 50.0)
        temp_storage.record(MetricCategory.GPU, "temperature", 72.0)

        names = temp_storage.get_names(MetricCategory.GPU)

        assert "utilization" in names
        assert "temperature" in names


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    @pytest.fixture
    def collector(self):
        """Create collector with temp storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_metrics.db"
            storage = MetricsStorage(db_path)
            yield MetricsCollector(storage)

    def test_collect_system(self, collector):
        """Should collect system metrics."""
        metrics = collector.collect_system()

        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert metrics["cpu_percent"] >= 0

    def test_collect_gpu_graceful_failure(self, collector):
        """Should return defaults if GPU not available."""
        metrics = collector.collect_gpu()

        # Should have expected keys even if GPU unavailable
        assert "available" in metrics
        assert "utilization" in metrics

    def test_collect_agents(self, collector):
        """Should collect agent metrics."""
        metrics = collector.collect_agents()

        assert "total_tasks" in metrics
        assert "success_rate" in metrics

    def test_collect_services(self, collector):
        """Should collect service status."""
        metrics = collector.collect_services()

        # Should have status for known services
        assert "ollama_status" in metrics
