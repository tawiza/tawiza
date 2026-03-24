"""SQLite database for dashboard persistence.

Stores analyses history, alerts, watchlist, and statistics.
Database location: ~/.tawiza/dashboard.db
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import aiosqlite

# Default database path
DEFAULT_DB_PATH = Path.home() / ".tawiza" / "dashboard.db"

SCHEMA = """
-- Historique des analyses
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    sources_used TEXT,  -- JSON array
    results_count INTEGER DEFAULT 0,
    confidence FLOAT,
    duration_ms INTEGER,
    metadata TEXT  -- JSON for extra data
);

-- Index pour recherche rapide
CREATE INDEX IF NOT EXISTS idx_analyses_timestamp ON analyses(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_query ON analyses(query);

-- Alertes de veille
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,  -- 'bodacc', 'boamp', 'gdelt'
    type TEXT NOT NULL,    -- 'creation', 'radiation', 'marche', 'news'
    title TEXT NOT NULL,
    content TEXT,
    url TEXT,
    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    read INTEGER DEFAULT 0,  -- SQLite uses INTEGER for boolean
    data TEXT  -- JSON payload complet
);

-- Index pour alertes
CREATE INDEX IF NOT EXISTS idx_alerts_source ON alerts(source);
CREATE INDEX IF NOT EXISTS idx_alerts_read ON alerts(read);
CREATE INDEX IF NOT EXISTS idx_alerts_detected ON alerts(detected_at DESC);

-- Configuration de veille (watchlist)
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keywords TEXT NOT NULL,  -- JSON array
    sources TEXT NOT NULL,   -- JSON array
    active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Stats agrégées (cache)
CREATE TABLE IF NOT EXISTS stats (
    key TEXT PRIMARY KEY,
    value TEXT,  -- JSON
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Métadonnées polling
CREATE TABLE IF NOT EXISTS poll_status (
    source TEXT PRIMARY KEY,
    last_poll DATETIME,
    next_poll DATETIME,
    last_error TEXT,
    polls_count INTEGER DEFAULT 0
);

-- Source status tracking
CREATE TABLE IF NOT EXISTS source_status (
    source TEXT PRIMARY KEY,
    status TEXT DEFAULT 'unknown',  -- 'ok', 'error', 'unknown'
    last_call DATETIME,
    last_error TEXT,
    calls_count INTEGER DEFAULT 0
);
"""


def init_database(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Initialize the database with schema.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Database connection
    """
    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()

    return conn


async def async_init_database(db_path: Path = DEFAULT_DB_PATH) -> aiosqlite.Connection:
    """Initialize the database asynchronously.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Async database connection
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA)
    await conn.commit()

    return conn


class DashboardDB:
    """Database operations for the dashboard.

    Provides sync and async methods for CRUD operations.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._async_conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create sync connection."""
        if self._conn is None:
            self._conn = init_database(self.db_path)
        return self._conn

    async def get_async_conn(self) -> aiosqlite.Connection:
        """Get or create async connection."""
        if self._async_conn is None:
            self._async_conn = await async_init_database(self.db_path)
        return self._async_conn

    def close(self):
        """Close sync connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    async def async_close(self):
        """Close async connection."""
        if self._async_conn:
            await self._async_conn.close()
            self._async_conn = None

    # =========== Analyses ===========

    def add_analysis(
        self,
        query: str,
        sources_used: list[str],
        results_count: int,
        confidence: float | None = None,
        duration_ms: int | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Record a new analysis."""
        cursor = self.conn.execute(
            """
            INSERT INTO analyses (query, sources_used, results_count, confidence, duration_ms, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                query,
                json.dumps(sources_used),
                results_count,
                confidence,
                duration_ms,
                json.dumps(metadata) if metadata else None,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    async def async_add_analysis(
        self,
        query: str,
        sources_used: list[str],
        results_count: int,
        confidence: float | None = None,
        duration_ms: int | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Record a new analysis (async)."""
        conn = await self.get_async_conn()
        cursor = await conn.execute(
            """
            INSERT INTO analyses (query, sources_used, results_count, confidence, duration_ms, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                query,
                json.dumps(sources_used),
                results_count,
                confidence,
                duration_ms,
                json.dumps(metadata) if metadata else None,
            ),
        )
        await conn.commit()
        return cursor.lastrowid

    def get_recent_analyses(self, limit: int = 10) -> list[dict]:
        """Get recent analyses."""
        cursor = self.conn.execute(
            """
            SELECT id, query, timestamp, sources_used, results_count, confidence, duration_ms
            FROM analyses
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "query": row["query"],
                "timestamp": row["timestamp"],
                "sources_used": json.loads(row["sources_used"]) if row["sources_used"] else [],
                "results_count": row["results_count"],
                "confidence": row["confidence"],
                "duration_ms": row["duration_ms"],
            }
            for row in rows
        ]

    async def async_get_recent_analyses(self, limit: int = 10) -> list[dict]:
        """Get recent analyses (async)."""
        conn = await self.get_async_conn()
        cursor = await conn.execute(
            """
            SELECT id, query, timestamp, sources_used, results_count, confidence, duration_ms
            FROM analyses
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "query": row["query"],
                "timestamp": row["timestamp"],
                "sources_used": json.loads(row["sources_used"]) if row["sources_used"] else [],
                "results_count": row["results_count"],
                "confidence": row["confidence"],
                "duration_ms": row["duration_ms"],
            }
            for row in rows
        ]

    def get_analyses_count(self, days: int = 7) -> dict:
        """Get analyses count for the last N days."""
        cursor = self.conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(results_count) as total_results,
                AVG(confidence) as avg_confidence
            FROM analyses
            WHERE timestamp > datetime('now', ?)
            """,
            (f"-{days} days",),
        )
        row = cursor.fetchone()
        return {
            "total": row["total"] or 0,
            "total_results": row["total_results"] or 0,
            "avg_confidence": round(row["avg_confidence"] or 0, 1),
        }

    # =========== Alerts ===========

    def add_alert(
        self,
        source: str,
        type: str,
        title: str,
        content: str | None = None,
        url: str | None = None,
        data: dict | None = None,
    ) -> int:
        """Add a new alert."""
        cursor = self.conn.execute(
            """
            INSERT INTO alerts (source, type, title, content, url, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source, type, title, content, url, json.dumps(data) if data else None),
        )
        self.conn.commit()
        return cursor.lastrowid

    async def async_add_alert(
        self,
        source: str,
        type: str,
        title: str,
        content: str | None = None,
        url: str | None = None,
        data: dict | None = None,
    ) -> int:
        """Add a new alert (async)."""
        conn = await self.get_async_conn()
        cursor = await conn.execute(
            """
            INSERT INTO alerts (source, type, title, content, url, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source, type, title, content, url, json.dumps(data) if data else None),
        )
        await conn.commit()
        return cursor.lastrowid

    def get_unread_alerts(self, limit: int = 50) -> list[dict]:
        """Get unread alerts."""
        cursor = self.conn.execute(
            """
            SELECT id, source, type, title, content, url, detected_at, data
            FROM alerts
            WHERE read = 0
            ORDER BY detected_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "source": row["source"],
                "type": row["type"],
                "title": row["title"],
                "content": row["content"],
                "url": row["url"],
                "detected_at": row["detected_at"],
                "data": json.loads(row["data"]) if row["data"] else None,
            }
            for row in rows
        ]

    async def async_get_unread_alerts(self, limit: int = 50) -> list[dict]:
        """Get unread alerts (async)."""
        conn = await self.get_async_conn()
        cursor = await conn.execute(
            """
            SELECT id, source, type, title, content, url, detected_at, data
            FROM alerts
            WHERE read = 0
            ORDER BY detected_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "source": row["source"],
                "type": row["type"],
                "title": row["title"],
                "content": row["content"],
                "url": row["url"],
                "detected_at": row["detected_at"],
                "data": json.loads(row["data"]) if row["data"] else None,
            }
            for row in rows
        ]

    def get_alerts_count(self) -> dict:
        """Get alerts count by source and read status."""
        cursor = self.conn.execute(
            """
            SELECT
                source,
                SUM(CASE WHEN read = 0 THEN 1 ELSE 0 END) as unread,
                COUNT(*) as total
            FROM alerts
            GROUP BY source
            """
        )
        by_source = {}
        total_unread = 0
        for row in cursor.fetchall():
            by_source[row["source"]] = {
                "unread": row["unread"],
                "total": row["total"],
            }
            total_unread += row["unread"]

        return {
            "total_unread": total_unread,
            "by_source": by_source,
        }

    async def async_get_alerts_count(self) -> dict:
        """Get alerts count (async)."""
        conn = await self.get_async_conn()
        cursor = await conn.execute(
            """
            SELECT
                source,
                SUM(CASE WHEN read = 0 THEN 1 ELSE 0 END) as unread,
                COUNT(*) as total
            FROM alerts
            GROUP BY source
            """
        )
        by_source = {}
        total_unread = 0
        async for row in cursor:
            by_source[row["source"]] = {
                "unread": row["unread"],
                "total": row["total"],
            }
            total_unread += row["unread"]

        return {
            "total_unread": total_unread,
            "by_source": by_source,
        }

    def mark_alerts_read(self, alert_ids: list[int] = None, all: bool = False) -> int:
        """Mark alerts as read."""
        if all:
            cursor = self.conn.execute("UPDATE alerts SET read = 1 WHERE read = 0")
        elif alert_ids:
            placeholders = ",".join("?" * len(alert_ids))
            cursor = self.conn.execute(
                f"UPDATE alerts SET read = 1 WHERE id IN ({placeholders})",
                alert_ids,
            )
        else:
            return 0
        self.conn.commit()
        return cursor.rowcount

    async def async_mark_alerts_read(self, alert_ids: list[int] = None, all: bool = False) -> int:
        """Mark alerts as read (async)."""
        conn = await self.get_async_conn()
        if all:
            cursor = await conn.execute("UPDATE alerts SET read = 1 WHERE read = 0")
        elif alert_ids:
            placeholders = ",".join("?" * len(alert_ids))
            cursor = await conn.execute(
                f"UPDATE alerts SET read = 1 WHERE id IN ({placeholders})",
                alert_ids,
            )
        else:
            return 0
        await conn.commit()
        return cursor.rowcount

    def get_alert_detail(self, alert_id: int) -> dict | None:
        """Get full alert details."""
        cursor = self.conn.execute(
            "SELECT * FROM alerts WHERE id = ?",
            (alert_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "source": row["source"],
            "type": row["type"],
            "title": row["title"],
            "content": row["content"],
            "url": row["url"],
            "detected_at": row["detected_at"],
            "read": bool(row["read"]),
            "data": json.loads(row["data"]) if row["data"] else None,
        }

    # =========== Watchlist ===========

    def add_watchlist_item(self, keywords: list[str], sources: list[str]) -> int:
        """Add keywords to watchlist."""
        cursor = self.conn.execute(
            """
            INSERT INTO watchlist (keywords, sources)
            VALUES (?, ?)
            """,
            (json.dumps(keywords), json.dumps(sources)),
        )
        self.conn.commit()
        return cursor.lastrowid

    async def async_add_watchlist_item(self, keywords: list[str], sources: list[str]) -> int:
        """Add keywords to watchlist (async)."""
        conn = await self.get_async_conn()
        cursor = await conn.execute(
            """
            INSERT INTO watchlist (keywords, sources)
            VALUES (?, ?)
            """,
            (json.dumps(keywords), json.dumps(sources)),
        )
        await conn.commit()
        return cursor.lastrowid

    def get_watchlist(self, active_only: bool = True) -> list[dict]:
        """Get watchlist items."""
        query = "SELECT * FROM watchlist"
        if active_only:
            query += " WHERE active = 1"
        cursor = self.conn.execute(query)
        return [
            {
                "id": row["id"],
                "keywords": json.loads(row["keywords"]),
                "sources": json.loads(row["sources"]),
                "active": bool(row["active"]),
                "created_at": row["created_at"],
            }
            for row in cursor.fetchall()
        ]

    async def async_get_watchlist(self, active_only: bool = True) -> list[dict]:
        """Get watchlist items (async)."""
        conn = await self.get_async_conn()
        query = "SELECT * FROM watchlist"
        if active_only:
            query += " WHERE active = 1"
        cursor = await conn.execute(query)
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "keywords": json.loads(row["keywords"]),
                "sources": json.loads(row["sources"]),
                "active": bool(row["active"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def remove_watchlist_keywords(self, keywords: list[str]) -> int:
        """Remove keywords from watchlist (deactivate matching items)."""
        # Find items containing any of the keywords
        cursor = self.conn.execute("SELECT id, keywords FROM watchlist WHERE active = 1")
        to_deactivate = []
        for row in cursor.fetchall():
            item_keywords = json.loads(row["keywords"])
            if any(k in item_keywords for k in keywords):
                to_deactivate.append(row["id"])

        if to_deactivate:
            placeholders = ",".join("?" * len(to_deactivate))
            self.conn.execute(
                f"UPDATE watchlist SET active = 0 WHERE id IN ({placeholders})",
                to_deactivate,
            )
            self.conn.commit()

        return len(to_deactivate)

    # =========== Poll Status ===========

    def update_poll_status(
        self,
        source: str,
        next_poll: datetime | None = None,
        last_error: str | None = None,
    ):
        """Update poll status for a source."""
        self.conn.execute(
            """
            INSERT INTO poll_status (source, last_poll, next_poll, last_error, polls_count)
            VALUES (?, datetime('now'), ?, ?, 1)
            ON CONFLICT(source) DO UPDATE SET
                last_poll = datetime('now'),
                next_poll = COALESCE(?, next_poll),
                last_error = ?,
                polls_count = polls_count + 1
            """,
            (source, next_poll, last_error, next_poll, last_error),
        )
        self.conn.commit()

    async def async_update_poll_status(
        self,
        source: str,
        next_poll: datetime | None = None,
        last_error: str | None = None,
    ):
        """Update poll status (async)."""
        conn = await self.get_async_conn()
        await conn.execute(
            """
            INSERT INTO poll_status (source, last_poll, next_poll, last_error, polls_count)
            VALUES (?, datetime('now'), ?, ?, 1)
            ON CONFLICT(source) DO UPDATE SET
                last_poll = datetime('now'),
                next_poll = COALESCE(?, next_poll),
                last_error = ?,
                polls_count = polls_count + 1
            """,
            (source, next_poll, last_error, next_poll, last_error),
        )
        await conn.commit()

    def get_poll_status(self) -> dict:
        """Get poll status for all sources."""
        cursor = self.conn.execute("SELECT * FROM poll_status")
        return {
            row["source"]: {
                "last_poll": row["last_poll"],
                "next_poll": row["next_poll"],
                "last_error": row["last_error"],
                "polls_count": row["polls_count"],
            }
            for row in cursor.fetchall()
        }

    async def async_get_poll_status(self) -> dict:
        """Get poll status (async)."""
        conn = await self.get_async_conn()
        cursor = await conn.execute("SELECT * FROM poll_status")
        rows = await cursor.fetchall()
        return {
            row["source"]: {
                "last_poll": row["last_poll"],
                "next_poll": row["next_poll"],
                "last_error": row["last_error"],
                "polls_count": row["polls_count"],
            }
            for row in rows
        }

    # =========== Source Status ===========

    def update_source_status(self, source: str, status: str, error: str | None = None):
        """Update source status after a call."""
        self.conn.execute(
            """
            INSERT INTO source_status (source, status, last_call, last_error, calls_count)
            VALUES (?, ?, datetime('now'), ?, 1)
            ON CONFLICT(source) DO UPDATE SET
                status = ?,
                last_call = datetime('now'),
                last_error = ?,
                calls_count = calls_count + 1
            """,
            (source, status, error, status, error),
        )
        self.conn.commit()

    async def async_update_source_status(self, source: str, status: str, error: str | None = None):
        """Update source status (async)."""
        conn = await self.get_async_conn()
        await conn.execute(
            """
            INSERT INTO source_status (source, status, last_call, last_error, calls_count)
            VALUES (?, ?, datetime('now'), ?, 1)
            ON CONFLICT(source) DO UPDATE SET
                status = ?,
                last_call = datetime('now'),
                last_error = ?,
                calls_count = calls_count + 1
            """,
            (source, status, error, status, error),
        )
        await conn.commit()

    def get_sources_status(self) -> dict:
        """Get status for all sources."""
        cursor = self.conn.execute("SELECT * FROM source_status")
        return {
            row["source"]: {
                "status": row["status"],
                "last_call": row["last_call"],
                "last_error": row["last_error"],
                "calls_count": row["calls_count"],
            }
            for row in cursor.fetchall()
        }

    # =========== Stats ===========

    def get_database_stats(self) -> dict:
        """Get database statistics."""
        cursor = self.conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM analyses) as analyses_count,
                (SELECT COUNT(*) FROM alerts) as alerts_total,
                (SELECT COUNT(*) FROM alerts WHERE read = 0) as alerts_unread,
                (SELECT COUNT(*) FROM watchlist WHERE active = 1) as watchlist_count
            """
        )
        row = cursor.fetchone()

        # Get database file size
        db_size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
        db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

        return {
            "analyses_count": row["analyses_count"],
            "alerts_total": row["alerts_total"],
            "alerts_unread": row["alerts_unread"],
            "watchlist_count": row["watchlist_count"],
            "database_size_mb": db_size_mb,
        }
