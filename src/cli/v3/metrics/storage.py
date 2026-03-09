"""SQLite-based metrics storage with retention policies."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from src.cli.v3.metrics.schema import MetricCategory, MetricPoint, MetricsSummary


class MetricsStorage:
    """SQLite-based metrics storage with automatic aggregation and retention."""

    # Retention policies (in days)
    RETENTION = {
        "raw": 1,           # 1 day for raw data
        "1min": 1,          # 1 day for 1-minute aggregates
        "5min": 7,          # 7 days for 5-minute aggregates
        "hourly": 30,       # 30 days for hourly aggregates
        "daily": 365,       # 1 year for daily aggregates
    }

    def __init__(self, db_path: Path | None = None):
        """Initialize metrics storage.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.tawiza/metrics.db
        """
        self.db_path = db_path or Path.home() / ".tawiza" / "metrics.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        """Get database connection with context management."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Raw metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT DEFAULT '',
                    tags TEXT DEFAULT '{}'
                )
            """)

            # Aggregated metrics tables
            for resolution in ["1min", "5min", "hourly", "daily"]:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS metrics_{resolution} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        category TEXT NOT NULL,
                        name TEXT NOT NULL,
                        min_value REAL,
                        max_value REAL,
                        avg_value REAL,
                        count INTEGER
                    )
                """)

            # Create indexes for efficient querying
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_raw_time
                ON metrics_raw(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_raw_category
                ON metrics_raw(category, name)
            """)

    def record(self, category: MetricCategory, name: str, value: float,
               unit: str = "", tags: dict | None = None) -> None:
        """Record a single metric point.

        Args:
            category: Metric category
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            tags: Optional tags dict
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO metrics_raw (timestamp, category, name, value, unit, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                category.value,
                name,
                value,
                unit,
                json.dumps(tags or {}),
            ))

    def record_batch(self, metrics: dict[str, dict]) -> None:
        """Record multiple metrics at once.

        Args:
            metrics: Dict of category -> name -> value
                     Example: {"gpu": {"utilization": 45.5, "temperature": 72}}
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()

            for category, values in metrics.items():
                cat = MetricCategory(category) if isinstance(category, str) else category
                for name, value in values.items():
                    if isinstance(value, (int, float)):
                        cursor.execute("""
                            INSERT INTO metrics_raw (timestamp, category, name, value)
                            VALUES (?, ?, ?, ?)
                        """, (timestamp, cat.value, name, value))

    def query(
        self,
        category: MetricCategory,
        name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        resolution: str = "raw",
        limit: int = 1000,
    ) -> list[MetricPoint]:
        """Query metrics with optional time range.

        Args:
            category: Metric category
            name: Metric name
            start_time: Start of time range
            end_time: End of time range
            resolution: "raw", "1min", "5min", "hourly", "daily"
            limit: Maximum number of points to return

        Returns:
            List of MetricPoint objects
        """
        table = f"metrics_{resolution}" if resolution != "raw" else "metrics_raw"
        value_col = "value" if resolution == "raw" else "avg_value"

        query = f"""
            SELECT timestamp, category, name, {value_col} as value
            FROM {table}
            WHERE category = ? AND name = ?
        """
        params = [category.value, name]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        query += f" ORDER BY timestamp DESC LIMIT {limit}"

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)

            return [
                MetricPoint(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    category=MetricCategory(row["category"]),
                    name=row["name"],
                    value=row["value"],
                )
                for row in cursor.fetchall()
            ]

    def get_latest(self, category: MetricCategory, name: str) -> MetricPoint | None:
        """Get the most recent value for a metric.

        Args:
            category: Metric category
            name: Metric name

        Returns:
            Latest MetricPoint or None
        """
        points = self.query(category, name, limit=1)
        return points[0] if points else None

    def get_summary(
        self,
        category: MetricCategory,
        name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> MetricsSummary | None:
        """Get summary statistics for a metric.

        Args:
            category: Metric category
            name: Metric name
            start_time: Start of time range
            end_time: End of time range

        Returns:
            MetricsSummary or None
        """
        query = """
            SELECT
                MIN(value) as min_value,
                MAX(value) as max_value,
                AVG(value) as avg_value,
                COUNT(*) as count,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time
            FROM metrics_raw
            WHERE category = ? AND name = ?
        """
        params = [category.value, name]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()

            if row and row["count"] > 0:
                return MetricsSummary(
                    name=name,
                    category=category,
                    min_value=row["min_value"],
                    max_value=row["max_value"],
                    avg_value=row["avg_value"],
                    count=row["count"],
                    start_time=datetime.fromisoformat(row["start_time"]),
                    end_time=datetime.fromisoformat(row["end_time"]),
                )

        return None

    def aggregate(self, resolution: str = "1min") -> int:
        """Aggregate raw metrics into lower resolution.

        Args:
            resolution: Target resolution ("1min", "5min", "hourly", "daily")

        Returns:
            Number of aggregates created
        """
        intervals = {
            "1min": 60,
            "5min": 300,
            "hourly": 3600,
            "daily": 86400,
        }

        seconds = intervals.get(resolution)
        if not seconds:
            raise ValueError(f"Unknown resolution: {resolution}")

        # Get distinct category/name pairs
        with self._get_conn() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT DISTINCT category, name FROM metrics_raw
            """)
            pairs = cursor.fetchall()

            count = 0
            for pair in pairs:
                # Group and aggregate
                cursor.execute(f"""
                    INSERT INTO metrics_{resolution}
                    (timestamp, category, name, min_value, max_value, avg_value, count)
                    SELECT
                        datetime((strftime('%s', timestamp) / {seconds}) * {seconds}, 'unixepoch') as ts,
                        category,
                        name,
                        MIN(value),
                        MAX(value),
                        AVG(value),
                        COUNT(*)
                    FROM metrics_raw
                    WHERE category = ? AND name = ?
                    GROUP BY ts, category, name
                """, (pair["category"], pair["name"]))
                count += cursor.rowcount

            return count

    def cleanup(self, retention_days: int | None = None) -> int:
        """Remove old metrics according to retention policy.

        Args:
            retention_days: Override retention days for all tables

        Returns:
            Total number of rows deleted
        """
        deleted = 0

        with self._get_conn() as conn:
            cursor = conn.cursor()

            for table, days in self.RETENTION.items():
                actual_days = retention_days if retention_days else days
                cutoff = (datetime.now() - timedelta(days=actual_days)).isoformat()

                table_name = f"metrics_{table}" if table != "raw" else "metrics_raw"
                cursor.execute(f"""
                    DELETE FROM {table_name} WHERE timestamp < ?
                """, (cutoff,))
                deleted += cursor.rowcount

        return deleted

    def get_categories(self) -> list[MetricCategory]:
        """Get all categories that have data.

        Returns:
            List of MetricCategory
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT category FROM metrics_raw")
            return [MetricCategory(row["category"]) for row in cursor.fetchall()]

    def get_names(self, category: MetricCategory) -> list[str]:
        """Get all metric names for a category.

        Args:
            category: Metric category

        Returns:
            List of metric names
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT name FROM metrics_raw WHERE category = ?
            """, (category.value,))
            return [row["name"] for row in cursor.fetchall()]
