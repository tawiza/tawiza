"""Storage operations for the watcher daemon.

Wraps DashboardDB with watcher-specific operations.
"""

import json
from datetime import datetime, timedelta

from loguru import logger

from ..dashboard import Alert, DashboardDB


class WatcherStorage:
    """Storage operations for the watcher daemon."""

    def __init__(self, db: DashboardDB | None = None):
        self.db = db or DashboardDB()

    # =========== Alerts ===========

    def save_alert(self, alert: Alert) -> int:
        """Save a new alert to the database."""
        return self.db.add_alert(
            source=alert.source.value if hasattr(alert.source, "value") else alert.source,
            type=alert.type.value if hasattr(alert.type, "value") else alert.type,
            title=alert.title,
            content=alert.content,
            url=alert.url,
            data=alert.data,
        )

    async def async_save_alert(self, alert: Alert) -> int:
        """Save a new alert (async)."""
        return await self.db.async_add_alert(
            source=alert.source.value if hasattr(alert.source, "value") else alert.source,
            type=alert.type.value if hasattr(alert.type, "value") else alert.type,
            title=alert.title,
            content=alert.content,
            url=alert.url,
            data=alert.data,
        )

    def save_alerts(self, alerts: list[Alert]) -> int:
        """Save multiple alerts. Returns count of saved alerts."""
        count = 0
        for alert in alerts:
            try:
                self.save_alert(alert)
                count += 1
            except Exception as e:
                logger.debug(f"Failed to save alert '{alert.title}': {e}")
                pass  # Skip duplicates or errors
        return count

    async def async_save_alerts(self, alerts: list[Alert]) -> int:
        """Save multiple alerts (async)."""
        count = 0
        for alert in alerts:
            try:
                await self.async_save_alert(alert)
                count += 1
            except Exception as e:
                logger.debug(f"Failed to save alert '{alert.title}' (async): {e}")
                pass
        return count

    def alert_exists(self, source: str, title: str, url: str | None = None) -> bool:
        """Check if an alert already exists (for deduplication)."""
        if url:
            cursor = self.db.conn.execute(
                "SELECT 1 FROM alerts WHERE source = ? AND url = ? LIMIT 1",
                (source, url),
            )
        else:
            cursor = self.db.conn.execute(
                "SELECT 1 FROM alerts WHERE source = ? AND title = ? LIMIT 1",
                (source, title),
            )
        return cursor.fetchone() is not None

    async def async_alert_exists(self, source: str, title: str, url: str | None = None) -> bool:
        """Check if alert exists (async)."""
        conn = await self.db.get_async_conn()
        if url:
            cursor = await conn.execute(
                "SELECT 1 FROM alerts WHERE source = ? AND url = ? LIMIT 1",
                (source, url),
            )
        else:
            cursor = await conn.execute(
                "SELECT 1 FROM alerts WHERE source = ? AND title = ? LIMIT 1",
                (source, title),
            )
        row = await cursor.fetchone()
        return row is not None

    def get_alerts(
        self,
        source: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Get alerts with optional filters."""
        query = "SELECT * FROM alerts WHERE 1=1"
        params: list = []
        if source:
            query += " AND source = ?"
            params.append(source)
        if unread_only:
            query += " AND read = 0"
        query += " ORDER BY detected_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self.db.conn.execute(query, params)
        results = []
        for row in cursor.fetchall():
            data = json.loads(row["data"]) if row["data"] else {}
            results.append(
                {
                    "id": row["id"],
                    "source": row["source"],
                    "title": row["title"],
                    "url": row["url"],
                    "summary": row["content"],
                    "keywords_matched": data.get("keywords_matched", []),
                    "score": data.get("score", 0.0),
                    "read": bool(row["read"]),
                    "created_at": row["detected_at"] or "",
                }
            )
        return results

    def count_alerts(
        self,
        source: str | None = None,
        unread_only: bool = False,
    ) -> int:
        """Count alerts with optional filters."""
        query = "SELECT COUNT(*) as cnt FROM alerts WHERE 1=1"
        params: list = []
        if source:
            query += " AND source = ?"
            params.append(source)
        if unread_only:
            query += " AND read = 0"
        cursor = self.db.conn.execute(query, params)
        row = cursor.fetchone()
        return row["cnt"] if row else 0

    def get_alert(self, alert_id: int) -> dict | None:
        """Get a single alert by ID."""
        cursor = self.db.conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
        row = cursor.fetchone()
        if not row:
            return None
        data = json.loads(row["data"]) if row["data"] else {}
        return {
            "id": row["id"],
            "source": row["source"],
            "title": row["title"],
            "url": row["url"],
            "summary": row["content"],
            "keywords_matched": data.get("keywords_matched", []),
            "score": data.get("score", 0.0),
            "read": bool(row["read"]),
            "created_at": row["detected_at"] or "",
        }

    def mark_read(self, alert_id: int) -> bool:
        """Mark a single alert as read."""
        cursor = self.db.conn.execute("UPDATE alerts SET read = 1 WHERE id = ?", (alert_id,))
        self.db.conn.commit()
        return cursor.rowcount > 0

    def delete_alert(self, alert_id: int) -> bool:
        """Delete a single alert."""
        cursor = self.db.conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        self.db.conn.commit()
        return cursor.rowcount > 0

    # =========== Watchlist ===========

    def get_all_keywords(self) -> list[str]:
        """Get all unique keywords from active watchlist items."""
        watchlist = self.db.get_watchlist(active_only=True)
        keywords = set()
        for item in watchlist:
            keywords.update(item["keywords"])
        return list(keywords)

    async def async_get_all_keywords(self) -> list[str]:
        """Get all keywords (async)."""
        watchlist = await self.db.async_get_watchlist(active_only=True)
        keywords = set()
        for item in watchlist:
            keywords.update(item["keywords"])
        return list(keywords)

    def get_keywords_for_source(self, source: str) -> list[str]:
        """Get keywords that should be monitored for a specific source."""
        watchlist = self.db.get_watchlist(active_only=True)
        keywords = set()
        for item in watchlist:
            if source in item["sources"]:
                keywords.update(item["keywords"])
        return list(keywords)

    async def async_get_keywords_for_source(self, source: str) -> list[str]:
        """Get keywords for source (async)."""
        watchlist = await self.db.async_get_watchlist(active_only=True)
        keywords = set()
        for item in watchlist:
            if source in item["sources"]:
                keywords.update(item["keywords"])
        return list(keywords)

    # =========== Poll Status ===========

    def should_poll(self, source: str, interval_seconds: int) -> bool:
        """Check if a source should be polled based on last poll time."""
        poll_status = self.db.get_poll_status()
        if source not in poll_status:
            return True  # Never polled

        last_poll = poll_status[source]["last_poll"]
        if not last_poll:
            return True

        # Parse timestamp
        if isinstance(last_poll, str):
            last_poll = datetime.fromisoformat(last_poll.replace("Z", "+00:00"))

        next_poll_time = last_poll + timedelta(seconds=interval_seconds)
        return datetime.now() >= next_poll_time

    async def async_should_poll(self, source: str, interval_seconds: int) -> bool:
        """Check if should poll (async)."""
        poll_status = await self.db.async_get_poll_status()
        if source not in poll_status:
            return True

        last_poll = poll_status[source]["last_poll"]
        if not last_poll:
            return True

        if isinstance(last_poll, str):
            last_poll = datetime.fromisoformat(last_poll.replace("Z", "+00:00"))

        next_poll_time = last_poll + timedelta(seconds=interval_seconds)
        return datetime.now() >= next_poll_time

    def record_poll(self, source: str, interval_seconds: int, error: str | None = None):
        """Record a poll attempt."""
        next_poll = datetime.now() + timedelta(seconds=interval_seconds)
        self.db.update_poll_status(source, next_poll=next_poll, last_error=error)

    async def async_record_poll(self, source: str, interval_seconds: int, error: str | None = None):
        """Record poll (async)."""
        next_poll = datetime.now() + timedelta(seconds=interval_seconds)
        await self.db.async_update_poll_status(source, next_poll=next_poll, last_error=error)

    def get_next_poll_times(self) -> dict[str, str]:
        """Get human-readable next poll times for all sources."""
        poll_status = self.db.get_poll_status()
        result = {}
        now = datetime.now()

        for source, status in poll_status.items():
            next_poll = status.get("next_poll")
            if not next_poll:
                result[source] = "unknown"
                continue

            if isinstance(next_poll, str):
                next_poll = datetime.fromisoformat(next_poll.replace("Z", "+00:00"))

            diff = (next_poll - now).total_seconds()
            if diff <= 0:
                result[source] = "now"
            elif diff < 60:
                result[source] = f"in {int(diff)}s"
            elif diff < 3600:
                result[source] = f"in {int(diff / 60)}min"
            else:
                result[source] = f"in {int(diff / 3600)}h"

        return result

    # =========== Watchlist CRUD ===========

    def get_watchlist(self) -> list[dict]:
        """Get all active watchlist items."""
        return self.db.get_watchlist(active_only=True)

    def add_keyword(self, keyword: str, sources: list[str] | None = None) -> int:
        """Add a keyword to the watchlist."""
        return self.db.add_watchlist_item(
            keywords=[keyword],
            sources=sources or ["bodacc", "boamp", "gdelt"],
        )

    def remove_keyword(self, keyword_id: int) -> bool:
        """Remove a watchlist item by ID."""
        try:
            self.db.conn.execute("DELETE FROM watchlist WHERE id = ?", (keyword_id,))
            self.db.conn.commit()
            return self.db.conn.total_changes > 0
        except Exception:
            return False

    # =========== Default Watchlist ===========

    def ensure_default_watchlist(self):
        """Ensure there's at least one watchlist item with default keywords."""
        watchlist = self.db.get_watchlist(active_only=True)
        if not watchlist:
            # Add default keywords
            self.db.add_watchlist_item(
                keywords=["startup", "IA", "intelligence artificielle", "machine learning"],
                sources=["bodacc", "boamp", "gdelt"],
            )

    async def async_ensure_default_watchlist(self):
        """Ensure default watchlist (async)."""
        watchlist = await self.db.async_get_watchlist(active_only=True)
        if not watchlist:
            await self.db.async_add_watchlist_item(
                keywords=["startup", "IA", "intelligence artificielle", "machine learning"],
                sources=["bodacc", "boamp", "gdelt"],
            )
