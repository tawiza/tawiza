"""Statistics calculation for the dashboard."""

import json
from collections import Counter
from datetime import datetime, timedelta

from .database import DashboardDB


class StatsCalculator:
    """Calculate dashboard statistics."""

    def __init__(self, db: DashboardDB):
        self.db = db

    def get_analyses_by_day(self, days: int = 7) -> list[int]:
        """Get analysis count per day for the last N days."""
        cursor = self.db.conn.execute(
            """
            SELECT DATE(timestamp) as day, COUNT(*) as count
            FROM analyses
            WHERE timestamp > datetime('now', ?)
            GROUP BY DATE(timestamp)
            ORDER BY day ASC
            """,
            (f"-{days} days",),
        )

        # Create a dict with all days initialized to 0
        today = datetime.now().date()
        counts_by_day = {
            (today - timedelta(days=i)).isoformat(): 0 for i in range(days - 1, -1, -1)
        }

        # Fill in actual counts
        for row in cursor.fetchall():
            if row["day"] in counts_by_day:
                counts_by_day[row["day"]] = row["count"]

        return list(counts_by_day.values())

    def get_top_queries(self, limit: int = 10) -> list[str]:
        """Get most frequent query terms."""
        cursor = self.db.conn.execute(
            """
            SELECT query FROM analyses
            ORDER BY timestamp DESC
            LIMIT 100
            """
        )

        # Extract words from queries
        words = []
        for row in cursor.fetchall():
            query = row["query"].lower()
            # Simple word extraction
            for word in query.split():
                if len(word) > 2 and word not in [
                    "les",
                    "des",
                    "une",
                    "dans",
                    "pour",
                    "sur",
                    "avec",
                ]:
                    words.append(word)

        # Count and return top words
        counter = Counter(words)
        return [word for word, _ in counter.most_common(limit)]

    def get_sources_usage(self, days: int = 7) -> dict[str, int]:
        """Get usage count per source."""
        cursor = self.db.conn.execute(
            """
            SELECT sources_used FROM analyses
            WHERE timestamp > datetime('now', ?)
            """,
            (f"-{days} days",),
        )

        usage = Counter()
        for row in cursor.fetchall():
            if row["sources_used"]:
                sources = json.loads(row["sources_used"])
                usage.update(sources)

        return dict(usage)

    def get_total_results(self, days: int = 7) -> int:
        """Get total results found in the last N days."""
        cursor = self.db.conn.execute(
            """
            SELECT COALESCE(SUM(results_count), 0) as total
            FROM analyses
            WHERE timestamp > datetime('now', ?)
            """,
            (f"-{days} days",),
        )
        row = cursor.fetchone()
        return row["total"] if row else 0

    def get_full_stats(self, days: int = 7) -> dict:
        """Get complete statistics for the dashboard."""
        analyses_count = self.db.get_analyses_count(days)

        return {
            "period": f"last_{days}_days",
            "analyses": {
                "total": analyses_count["total"],
                "by_day": self.get_analyses_by_day(days),
            },
            "companies_found": self.get_total_results(days),
            "sources_usage": self.get_sources_usage(days),
            "top_queries": self.get_top_queries(10),
            "avg_confidence": analyses_count["avg_confidence"],
        }


async def get_async_stats(db: DashboardDB, days: int = 7) -> dict:
    """Get statistics asynchronously."""
    conn = await db.get_async_conn()

    # Analyses count
    cursor = await conn.execute(
        """
        SELECT
            COUNT(*) as total,
            COALESCE(SUM(results_count), 0) as total_results,
            COALESCE(AVG(confidence), 0) as avg_confidence
        FROM analyses
        WHERE timestamp > datetime('now', ?)
        """,
        (f"-{days} days",),
    )
    row = await cursor.fetchone()
    analyses_total = row["total"]
    total_results = row["total_results"]
    avg_confidence = round(row["avg_confidence"], 1)

    # Sources usage
    cursor = await conn.execute(
        """
        SELECT sources_used FROM analyses
        WHERE timestamp > datetime('now', ?)
        """,
        (f"-{days} days",),
    )
    usage = Counter()
    async for row in cursor:
        if row["sources_used"]:
            sources = json.loads(row["sources_used"])
            usage.update(sources)

    # Top queries
    cursor = await conn.execute(
        """
        SELECT query FROM analyses
        ORDER BY timestamp DESC
        LIMIT 100
        """
    )
    words = []
    async for row in cursor:
        query = row["query"].lower()
        for word in query.split():
            if len(word) > 2 and word not in ["les", "des", "une", "dans", "pour", "sur", "avec"]:
                words.append(word)
    word_counter = Counter(words)
    top_queries = [word for word, _ in word_counter.most_common(10)]

    return {
        "period": f"last_{days}_days",
        "analyses_count": analyses_total,
        "companies_found": total_results,
        "sources_usage": dict(usage),
        "top_queries": top_queries,
        "avg_confidence": avg_confidence,
    }
