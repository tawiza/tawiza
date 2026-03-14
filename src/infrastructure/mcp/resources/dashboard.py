"""Dashboard MCP resources for Cherry Studio.

Provides dynamic resources for dashboard display:
- tawiza://dashboard/status - System status
- tawiza://dashboard/alerts - Unread alerts
- tawiza://dashboard/history - Recent analyses
- tawiza://dashboard/stats - Usage statistics
"""

import json
from datetime import datetime

import httpx
from mcp.server.fastmcp import FastMCP

from ...dashboard import DashboardDB
from ...watcher import WatcherDaemon

# Global dashboard database instance
_db: DashboardDB | None = None
_daemon: WatcherDaemon | None = None


def get_db() -> DashboardDB:
    """Get or create dashboard database instance."""
    global _db
    if _db is None:
        _db = DashboardDB()
    return _db


def get_daemon() -> WatcherDaemon:
    """Get or create daemon instance (for status only)."""
    global _daemon
    if _daemon is None:
        _daemon = WatcherDaemon()
    return _daemon


def register_dashboard_resources(mcp: FastMCP) -> None:
    """Register dashboard resources on the MCP server."""

    @mcp.resource("tawiza://dashboard/status")
    def get_dashboard_status() -> str:
        """État du système en temps réel.

        Retourne le status de chaque source de données, du watcher,
        et des statistiques de la base de données.
        """
        db = get_db()

        # Get source status
        sources_status = db.get_sources_status()

        # Format sources for display
        sources = {}
        for source in ["sirene", "bodacc", "boamp", "ban", "gdelt"]:
            status_info = sources_status.get(source, {})
            last_call = status_info.get("last_call")

            # Format last call time
            if last_call:
                try:
                    if isinstance(last_call, str):
                        last_dt = datetime.fromisoformat(last_call.replace("Z", "+00:00"))
                    else:
                        last_dt = last_call
                    diff = (datetime.now() - last_dt).total_seconds()
                    if diff < 60:
                        time_ago = "just now"
                    elif diff < 3600:
                        time_ago = f"{int(diff / 60)}min ago"
                    elif diff < 86400:
                        time_ago = f"{int(diff / 3600)}h ago"
                    else:
                        time_ago = f"{int(diff / 86400)}d ago"
                except Exception:
                    time_ago = "unknown"
            else:
                time_ago = "never"

            sources[source] = {
                "status": status_info.get("status", "unknown"),
                "last_call": time_ago,
                "calls_count": status_info.get("calls_count", 0),
            }

        # Get watcher status
        poll_status = db.get_poll_status()
        watcher_running = False  # Would need to check actual daemon process

        watcher = {
            "running": watcher_running,
            "next_poll": {},
        }

        for source in ["bodacc", "boamp", "gdelt"]:
            ps = poll_status.get(source, {})
            next_poll = ps.get("next_poll")
            if next_poll:
                try:
                    if isinstance(next_poll, str):
                        np_dt = datetime.fromisoformat(next_poll.replace("Z", "+00:00"))
                    else:
                        np_dt = next_poll
                    diff = (np_dt - datetime.now()).total_seconds()
                    if diff <= 0:
                        watcher["next_poll"][source] = "now"
                    elif diff < 3600:
                        watcher["next_poll"][source] = f"in {int(diff / 60)}min"
                    else:
                        watcher["next_poll"][source] = f"in {int(diff / 3600)}h"
                except Exception:
                    watcher["next_poll"][source] = "unknown"
            else:
                watcher["next_poll"][source] = "not scheduled"

        # Get database stats
        db_stats = db.get_database_stats()

        # Check Ollama status
        ollama_status = {"status": "unknown", "models": []}
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    ollama_status = {"status": "ok", "models": models[:5]}
        except Exception:
            ollama_status = {"status": "error", "models": []}

        sources["ollama"] = ollama_status

        result = {
            "sources": sources,
            "watcher": watcher,
            "database": {
                "size_mb": db_stats["database_size_mb"],
                "alerts_total": db_stats["alerts_total"],
                "alerts_unread": db_stats["alerts_unread"],
                "analyses_count": db_stats["analyses_count"],
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.resource("tawiza://dashboard/alerts")
    def get_dashboard_alerts() -> str:
        """Alertes non-lues du watcher.

        Retourne le nombre d'alertes par source et les dernières alertes.
        """
        db = get_db()

        # Get alert counts
        alert_counts = db.get_alerts_count()

        # Get latest unread alerts
        unread = db.get_unread_alerts(limit=20)

        # Format for display
        latest = []
        for alert in unread[:10]:
            detected = alert.get("detected_at", "")
            if detected:
                try:
                    if isinstance(detected, str):
                        det_dt = datetime.fromisoformat(detected.replace("Z", "+00:00"))
                    else:
                        det_dt = detected
                    diff = (datetime.now() - det_dt).total_seconds()
                    if diff < 3600:
                        time_ago = f"{int(diff / 60)}min"
                    elif diff < 86400:
                        time_ago = f"{int(diff / 3600)}h"
                    else:
                        time_ago = f"{int(diff / 86400)}d"
                except Exception:
                    time_ago = "?"
            else:
                time_ago = "?"

            latest.append(
                {
                    "id": alert["id"],
                    "source": alert["source"],
                    "type": alert["type"],
                    "title": alert["title"][:80],
                    "time": time_ago,
                }
            )

        result = {
            "unread_count": alert_counts["total_unread"],
            "by_source": {src: info["unread"] for src, info in alert_counts["by_source"].items()},
            "latest": latest,
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.resource("tawiza://dashboard/history")
    def get_dashboard_history() -> str:
        """Historique des dernières analyses.

        Retourne les analyses récentes avec leurs résultats.
        """
        db = get_db()

        # Get recent analyses
        recent = db.get_recent_analyses(limit=20)

        # Format for display
        analyses = []
        for analysis in recent:
            ts = analysis.get("timestamp", "")
            if ts:
                try:
                    if isinstance(ts, str):
                        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    else:
                        ts_dt = ts
                    diff = (datetime.now() - ts_dt).total_seconds()
                    if diff < 3600:
                        time_str = f"{int(diff / 60)}min ago"
                    elif diff < 86400:
                        time_str = f"{int(diff / 3600)}h ago"
                    else:
                        time_str = ts_dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    time_str = ts
            else:
                time_str = "unknown"

            analyses.append(
                {
                    "id": analysis["id"],
                    "query": analysis["query"][:60],
                    "results_count": analysis["results_count"],
                    "confidence": analysis.get("confidence"),
                    "sources": analysis.get("sources_used", []),
                    "time": time_str,
                }
            )

        # Get total count
        count_stats = db.get_analyses_count(days=30)

        result = {
            "recent": analyses,
            "total_analyses": count_stats["total"],
            "today_count": db.get_analyses_count(days=1)["total"],
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.resource("tawiza://dashboard/stats")
    def get_dashboard_stats() -> str:
        """Statistiques d'utilisation sur les 7 derniers jours.

        Retourne le nombre d'analyses, résultats, et utilisation des sources.
        """
        db = get_db()

        # Get stats using sync method
        from ...dashboard.stats import StatsCalculator

        calc = StatsCalculator(db)
        stats = calc.get_full_stats(days=7)

        return json.dumps(stats, ensure_ascii=False, indent=2)
