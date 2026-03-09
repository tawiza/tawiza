"""JSON metrics exporter."""

import json
from datetime import datetime
from pathlib import Path

from src.cli.v3.metrics.schema import MetricCategory
from src.cli.v3.metrics.storage import MetricsStorage


class JSONExporter:
    """Export metrics to JSON format."""

    def __init__(self, storage: MetricsStorage):
        self.storage = storage

    def export(
        self,
        output_path: Path,
        categories: list[MetricCategory] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """Export metrics to JSON file.

        Args:
            output_path: Path to output file
            categories: Categories to export (None = all)
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Number of metrics exported
        """
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "metrics": {},
        }

        cats = categories or list(MetricCategory)
        count = 0

        for category in cats:
            names = self.storage.get_names(category)
            export_data["metrics"][category.value] = {}

            for name in names:
                points = self.storage.query(
                    category,
                    name,
                    start_time=start_time,
                    end_time=end_time,
                    limit=10000,
                )

                export_data["metrics"][category.value][name] = [
                    {
                        "timestamp": p.timestamp.isoformat(),
                        "value": p.value,
                    }
                    for p in points
                ]
                count += len(points)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(export_data, indent=2))

        return count

    def export_latest(self, output_path: Path | None = None) -> dict:
        """Export latest values for all metrics.

        Args:
            output_path: Optional path to save to

        Returns:
            Dict of latest metrics
        """
        latest = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
        }

        for category in MetricCategory:
            names = self.storage.get_names(category)
            latest["metrics"][category.value] = {}

            for name in names:
                point = self.storage.get_latest(category, name)
                if point:
                    latest["metrics"][category.value][name] = {
                        "value": point.value,
                        "timestamp": point.timestamp.isoformat(),
                    }

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(latest, indent=2))

        return latest
