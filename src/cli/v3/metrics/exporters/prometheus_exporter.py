"""Prometheus metrics exporter."""


from src.cli.v3.metrics.schema import METRICS_SCHEMA, MetricCategory
from src.cli.v3.metrics.storage import MetricsStorage


class PrometheusExporter:
    """Export metrics in Prometheus format."""

    def __init__(self, storage: MetricsStorage):
        self.storage = storage

    def export(self, categories: list[MetricCategory] | None = None) -> str:
        """Export metrics in Prometheus exposition format.

        Args:
            categories: Categories to export (None = all)

        Returns:
            Prometheus format string
        """
        lines = []
        cats = categories or list(MetricCategory)

        for category in cats:
            names = self.storage.get_names(category)

            for name in names:
                point = self.storage.get_latest(category, name)
                if point:
                    # Get metric type info
                    METRICS_SCHEMA.get(category, {}).get(name, {})
                    metric_type = "gauge"  # Default to gauge

                    # Build Prometheus metric name
                    prom_name = f"tawiza_{category.value}_{name}"

                    # Add HELP line
                    lines.append(f"# HELP {prom_name} Tawiza {category.value} {name}")

                    # Add TYPE line
                    lines.append(f"# TYPE {prom_name} {metric_type}")

                    # Add metric value
                    if isinstance(point.value, (int, float)):
                        lines.append(f"{prom_name} {point.value}")

        return "\n".join(lines)

    def get_endpoint_handler(self):
        """Get a handler function for Prometheus scrape endpoint.

        Returns:
            Async handler function
        """

        async def prometheus_handler(request):
            """Handle Prometheus scrape requests."""
            from aiohttp import web

            content = self.export()
            return web.Response(
                text=content,
                content_type="text/plain; version=0.0.4",
            )

        return prometheus_handler
