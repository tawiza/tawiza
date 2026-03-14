"""Signals Bridge - Connect TAJINE agent to the unified signals database.

This is the critical integration layer that connects the TAJINE agentic system
to the collector pipeline's PostgreSQL database (82K+ signals, micro-signals,
scoring composite).

Provides tools for:
1. Querying aggregated signals by department/source/date
2. Retrieving active micro-signals (anomalies, convergences, alerts)
3. Fetching composite scores and rankings
4. Searching signals by keyword/entity
5. Getting temporal trends and cross-source convergences
"""

import os
from datetime import datetime, timedelta
from typing import Any

import asyncpg
from loguru import logger

from src.infrastructure.agents.tools.registry import (
    BaseTool,
    ToolCategory,
    ToolMetadata,
)

# DB connection string
DB_URL = (
    os.getenv("COLLECTOR_DATABASE_URL", "postgresql://localhost:5433/tawiza")
    .replace("postgresql+asyncpg://", "postgresql://")
    .replace("postgresql://", "postgres://")
)


async def _get_conn() -> asyncpg.Connection:
    """Get a database connection."""
    return await asyncpg.connect(DB_URL, timeout=10)


class SignalsQueryTool(BaseTool):
    """Query the unified signals database.

    Access 82K+ signals from 10 sources: BODACC, France Travail, DVF,
    SIRENE, Presse locale, INSEE, OFGL, URSSAF, Google Trends.
    """

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="signals_query",
            description=(
                "Query the Tawiza signals database. "
                "Retrieve signals by department, source, date range, or keyword. "
                "Returns aggregated counts and recent signal details."
            ),
            category=ToolCategory.DATA,
            tags=["territorial", "signals", "database", "tawiza"],
            timeout=30.0,
        )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute signals query.

        Params:
            department: str - Department code (e.g. "75", "93")
            source: str - Filter by source (bodacc, france_travail, dvf, etc.)
            days: int - Look back N days (default 90)
            keyword: str - Search in extracted_text/entities
            limit: int - Max results for detail (default 20)
            aggregate: bool - Return aggregates only (default True)
        """
        dept = params.get("department")
        source = params.get("source")
        days = params.get("days", 90)
        keyword = params.get("keyword")
        limit = min(params.get("limit", 20), 100)
        aggregate = params.get("aggregate", True)

        conn = await _get_conn()
        try:
            results: dict[str, Any] = {}

            # Build WHERE clause
            conditions = []
            args = []
            arg_idx = 1

            if dept:
                conditions.append(f"code_dept = ${arg_idx}")
                args.append(dept)
                arg_idx += 1
            if source:
                conditions.append(f"source = ${arg_idx}")
                args.append(source)
                arg_idx += 1
            if days:
                conditions.append(f"event_date >= ${arg_idx}")
                args.append(datetime.now() - timedelta(days=days))
                arg_idx += 1
            if keyword:
                conditions.append(
                    f"(extracted_text ILIKE ${arg_idx} OR entities::text ILIKE ${arg_idx})"
                )
                args.append(f"%{keyword}%")
                arg_idx += 1

            where = " AND ".join(conditions) if conditions else "TRUE"

            # Aggregates
            if aggregate:
                # Total count
                row = await conn.fetchrow(
                    f"SELECT count(*) as total FROM signals WHERE {where}", *args
                )
                results["total_signals"] = row["total"]

                # By source
                rows = await conn.fetch(
                    f"SELECT source, count(*) as n FROM signals WHERE {where} GROUP BY source ORDER BY n DESC",
                    *args,
                )
                results["by_source"] = {r["source"]: r["n"] for r in rows}

                # By department (top 10)
                if not dept:
                    rows = await conn.fetch(
                        f"""SELECT code_dept, count(*) as n
                        FROM signals WHERE {where} AND code_dept IS NOT NULL
                        GROUP BY code_dept ORDER BY n DESC LIMIT 10""",
                        *args,
                    )
                    results["top_departments"] = {r["code_dept"]: r["n"] for r in rows}

                # Temporal distribution (by month)
                rows = await conn.fetch(
                    f"""SELECT date_trunc('month', event_date) as month, count(*) as n
                    FROM signals WHERE {where} AND event_date IS NOT NULL
                    GROUP BY month ORDER BY month DESC LIMIT 12""",
                    *args,
                )
                results["monthly_distribution"] = {str(r["month"].date()): r["n"] for r in rows}

                # Signal types distribution
                rows = await conn.fetch(
                    f"""SELECT signal_type, count(*) as n
                    FROM signals WHERE {where} AND signal_type IS NOT NULL
                    GROUP BY signal_type ORDER BY n DESC LIMIT 10""",
                    *args,
                )
                results["by_type"] = {r["signal_type"]: r["n"] for r in rows}

            # Recent signals detail
            rows = await conn.fetch(
                f"""SELECT source, event_date, code_dept, signal_type, metric_name,
                       metric_value, confidence, extracted_text
                FROM signals WHERE {where}
                ORDER BY event_date DESC NULLS LAST
                LIMIT {limit}""",
                *args,
            )
            results["recent_signals"] = [
                {
                    "source": r["source"],
                    "date": str(r["event_date"]) if r["event_date"] else None,
                    "dept": r["code_dept"],
                    "type": r["signal_type"],
                    "metric": r["metric_name"],
                    "value": float(r["metric_value"]) if r["metric_value"] else None,
                    "confidence": float(r["confidence"]) if r["confidence"] else None,
                    "text": (r["extracted_text"] or "")[:200],
                }
                for r in rows
            ]

            return {
                "status": "success",
                "query": {"department": dept, "source": source, "days": days, "keyword": keyword},
                "data": results,
            }
        except Exception as e:
            logger.error(f"SignalsQuery error: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            await conn.close()


class MicroSignalsTool(BaseTool):
    """Retrieve active micro-signals (anomalies, convergences, alerts)."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="microsignals_query",
            description=(
                "Retrieve active micro-signals detected by the anomaly engine. "
                "Includes Z-score anomalies, cross-source convergences, "
                "ratio alerts, and temporal trends."
            ),
            category=ToolCategory.DATA,
            tags=["territorial", "anomalies", "microsignals", "alerts"],
            timeout=15.0,
        )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute micro-signals query.

        Params:
            department: str - Filter by territory code
            min_score: float - Minimum score threshold (default 0.3)
            signal_type: str - Filter by type (anomaly, convergence, alert, trend)
        """
        dept = params.get("department")
        min_score = params.get("min_score", 0.3)
        signal_type = params.get("signal_type")

        conn = await _get_conn()
        try:
            conditions = ["is_active = true", f"score >= {min_score}"]
            args = []
            arg_idx = 1

            if dept:
                conditions.append(f"territory_code = ${arg_idx}")
                args.append(dept)
                arg_idx += 1
            if signal_type:
                conditions.append(f"signal_type = ${arg_idx}")
                args.append(signal_type)
                arg_idx += 1

            where = " AND ".join(conditions)

            rows = await conn.fetch(
                f"""SELECT territory_code, signal_type, sources, dimensions,
                       score, confidence, impact, novelty, description,
                       evidence, detected_at
                FROM micro_signals
                WHERE {where}
                ORDER BY score DESC
                LIMIT 50""",
                *args,
            )

            micro_signals = []
            for r in rows:
                ms = {
                    "territory": r["territory_code"],
                    "type": r["signal_type"],
                    "sources": r["sources"],
                    "dimensions": r["dimensions"],
                    "score": float(r["score"]) if r["score"] else 0,
                    "confidence": float(r["confidence"]) if r["confidence"] else 0,
                    "impact": r["impact"],
                    "novelty": float(r["novelty"]) if r["novelty"] else 0,
                    "description": r["description"],
                    "evidence": r["evidence"],
                    "detected_at": str(r["detected_at"]) if r["detected_at"] else None,
                }
                micro_signals.append(ms)

            # Summary stats
            summary = {}
            if micro_signals:
                by_type = {}
                by_dept = {}
                for ms in micro_signals:
                    by_type[ms["type"]] = by_type.get(ms["type"], 0) + 1
                    by_dept[ms["territory"]] = by_dept.get(ms["territory"], 0) + 1
                summary = {
                    "total_active": len(micro_signals),
                    "by_type": by_type,
                    "by_department": by_dept,
                    "avg_score": sum(ms["score"] for ms in micro_signals) / len(micro_signals),
                    "max_score_signal": max(micro_signals, key=lambda x: x["score"]),
                }

            return {
                "status": "success",
                "summary": summary,
                "micro_signals": micro_signals,
            }
        except Exception as e:
            logger.error(f"MicroSignals error: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            await conn.close()


class TerritorialScoringTool(BaseTool):
    """Fetch composite territorial scores and rankings."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="territorial_scoring",
            description=(
                "Get composite territorial scores for all 101 departments. "
                "6 dimensions: sante_entreprises, tension_emploi, dynamisme_immo, "
                "sante_financiere, declin_ratio, sentiment. Scores 0-100."
            ),
            category=ToolCategory.DATA,
            tags=["territorial", "scoring", "ranking", "departments"],
            timeout=15.0,
        )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute scoring query.

        Params:
            department: str - Get score for specific department
            top_n: int - Return top N departments (default 10)
            bottom_n: int - Return bottom N departments (default 10)
            dimension: str - Sort by specific dimension
        """
        dept = params.get("department")
        top_n = params.get("top_n", 10)
        bottom_n = params.get("bottom_n", 10)

        conn = await _get_conn()
        try:
            # Check if scoring table exists
            exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'department_scores'
                )
            """)

            if not exists:
                # Fallback: compute from signals
                return await self._compute_from_signals(conn, dept, top_n, bottom_n)

            if dept:
                row = await conn.fetchrow(
                    "SELECT * FROM department_scores WHERE code_dept = $1", dept
                )
                if row:
                    return {"status": "success", "department": dict(row)}
                return {"status": "not_found", "department": dept}

            # Top departments
            top_rows = await conn.fetch(
                f"SELECT * FROM department_scores ORDER BY score_global DESC LIMIT {top_n}"
            )
            bottom_rows = await conn.fetch(
                f"SELECT * FROM department_scores ORDER BY score_global ASC LIMIT {bottom_n}"
            )

            return {
                "status": "success",
                "top_departments": [dict(r) for r in top_rows],
                "bottom_departments": [dict(r) for r in bottom_rows],
            }
        except Exception as e:
            logger.error(f"TerritorialScoring error: {e}")
            # Fallback
            return await self._compute_from_signals(conn, dept, top_n, bottom_n)
        finally:
            await conn.close()

    async def _compute_from_signals(
        self, conn: asyncpg.Connection, dept: str | None, top_n: int, bottom_n: int
    ) -> dict[str, Any]:
        """Compute basic scores from signals table."""
        rows = await conn.fetch("""
            SELECT code_dept,
                   count(*) as total_signals,
                   count(DISTINCT source) as num_sources,
                   count(*) FILTER (WHERE source = 'bodacc') as bodacc,
                   count(*) FILTER (WHERE source = 'france_travail') as ft,
                   count(*) FILTER (WHERE source = 'dvf') as dvf,
                   count(*) FILTER (WHERE source = 'sirene') as sirene
            FROM signals
            WHERE code_dept IS NOT NULL
            GROUP BY code_dept
            ORDER BY total_signals DESC
        """)

        if dept:
            for r in rows:
                if r["code_dept"] == dept:
                    return {"status": "success", "department": dict(r)}
            return {"status": "not_found"}

        return {
            "status": "success",
            "source": "computed_from_signals",
            "top_departments": [dict(r) for r in rows[:top_n]],
            "bottom_departments": [dict(r) for r in rows[-bottom_n:]],
            "total_departments": len(rows),
        }


class SignalSearchTool(BaseTool):
    """Full-text search across signals."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="signal_search",
            description=(
                "Search signals by keyword across extracted text and entities. "
                "Useful for finding specific companies, sectors, or events."
            ),
            category=ToolCategory.DATA,
            tags=["search", "signals", "entities", "text"],
            timeout=20.0,
        )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search signals.

        Params:
            query: str - Search query (required)
            department: str - Filter by department
            source: str - Filter by source
            limit: int - Max results (default 30)
        """
        query = params.get("query", "")
        if not query:
            return {"status": "error", "error": "query is required"}

        dept = params.get("department")
        source = params.get("source")
        limit = min(params.get("limit", 30), 100)

        conn = await _get_conn()
        try:
            conditions = [
                "(extracted_text ILIKE $1 OR entities::text ILIKE $1 OR raw_data::text ILIKE $1)"
            ]
            args: list[Any] = [f"%{query}%"]
            arg_idx = 2

            if dept:
                conditions.append(f"code_dept = ${arg_idx}")
                args.append(dept)
                arg_idx += 1
            if source:
                conditions.append(f"source = ${arg_idx}")
                args.append(source)
                arg_idx += 1

            where = " AND ".join(conditions)

            # Count
            total = await conn.fetchval(f"SELECT count(*) FROM signals WHERE {where}", *args)

            # Results
            rows = await conn.fetch(
                f"""SELECT source, event_date, code_dept, signal_type,
                       metric_name, metric_value, extracted_text, entities
                FROM signals WHERE {where}
                ORDER BY event_date DESC NULLS LAST
                LIMIT {limit}""",
                *args,
            )

            results = [
                {
                    "source": r["source"],
                    "date": str(r["event_date"]) if r["event_date"] else None,
                    "dept": r["code_dept"],
                    "type": r["signal_type"],
                    "metric": r["metric_name"],
                    "value": float(r["metric_value"]) if r["metric_value"] else None,
                    "text": (r["extracted_text"] or "")[:300],
                    "entities": r["entities"],
                }
                for r in rows
            ]

            return {
                "status": "success",
                "query": query,
                "total_matches": total,
                "results": results,
            }
        except Exception as e:
            logger.error(f"SignalSearch error: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            await conn.close()


class DepartmentProfileTool(BaseTool):
    """Get a complete territorial profile for a department."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="department_profile",
            description=(
                "Get a complete intelligence profile for a French department. "
                "Combines signal stats, micro-signals, source breakdown, "
                "temporal trends, and key metrics into a single view."
            ),
            category=ToolCategory.DATA,
            tags=["territorial", "department", "profile", "intelligence"],
            timeout=20.0,
        )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Get department profile.

        Params:
            department: str - Department code (required, e.g. "75")
        """
        dept = params.get("department")
        if not dept:
            return {"status": "error", "error": "department code is required"}

        conn = await _get_conn()
        try:
            profile: dict[str, Any] = {"code_dept": dept}

            # 1. Signal stats by source
            rows = await conn.fetch(
                """
                SELECT source, count(*) as n,
                       min(event_date) as earliest,
                       max(event_date) as latest
                FROM signals WHERE code_dept = $1
                GROUP BY source ORDER BY n DESC
            """,
                dept,
            )
            profile["sources"] = {
                r["source"]: {
                    "count": r["n"],
                    "earliest": str(r["earliest"]) if r["earliest"] else None,
                    "latest": str(r["latest"]) if r["latest"] else None,
                }
                for r in rows
            }
            profile["total_signals"] = sum(r["n"] for r in rows)

            # 2. Signal types
            rows = await conn.fetch(
                """
                SELECT signal_type, count(*) as n
                FROM signals WHERE code_dept = $1 AND signal_type IS NOT NULL
                GROUP BY signal_type ORDER BY n DESC
            """,
                dept,
            )
            profile["signal_types"] = {r["signal_type"]: r["n"] for r in rows}

            # 3. Active micro-signals
            rows = await conn.fetch(
                """
                SELECT signal_type, dimensions, score, confidence,
                       description, evidence, detected_at
                FROM micro_signals
                WHERE territory_code = $1 AND is_active = true
                ORDER BY score DESC
            """,
                dept,
            )
            profile["micro_signals"] = [
                {
                    "type": r["signal_type"],
                    "dimensions": r["dimensions"],
                    "score": float(r["score"]) if r["score"] else 0,
                    "confidence": float(r["confidence"]) if r["confidence"] else 0,
                    "description": r["description"],
                    "evidence": r["evidence"],
                    "detected_at": str(r["detected_at"]) if r["detected_at"] else None,
                }
                for r in rows
            ]

            # 4. Recent notable signals (high confidence or notable metrics)
            rows = await conn.fetch(
                """
                SELECT source, event_date, signal_type, metric_name,
                       metric_value, confidence, extracted_text
                FROM signals
                WHERE code_dept = $1 AND (confidence > 0.7 OR metric_value IS NOT NULL)
                ORDER BY event_date DESC NULLS LAST
                LIMIT 15
            """,
                dept,
            )
            profile["notable_signals"] = [
                {
                    "source": r["source"],
                    "date": str(r["event_date"]) if r["event_date"] else None,
                    "type": r["signal_type"],
                    "metric": r["metric_name"],
                    "value": float(r["metric_value"]) if r["metric_value"] else None,
                    "text": (r["extracted_text"] or "")[:200],
                }
                for r in rows
            ]

            # 5. Temporal trend (signals per month, last 12 months)
            rows = await conn.fetch(
                """
                SELECT date_trunc('month', event_date) as month, count(*) as n
                FROM signals
                WHERE code_dept = $1 AND event_date >= NOW() - INTERVAL '12 months'
                GROUP BY month ORDER BY month
            """,
                dept,
            )
            profile["monthly_trend"] = [
                {"month": str(r["month"].date()), "count": r["n"]} for r in rows
            ]

            # 6. Key metrics summary
            metrics = await conn.fetch(
                """
                SELECT metric_name,
                       avg(metric_value) as avg_val,
                       min(metric_value) as min_val,
                       max(metric_value) as max_val,
                       count(*) as n
                FROM signals
                WHERE code_dept = $1 AND metric_name IS NOT NULL AND metric_value IS NOT NULL
                GROUP BY metric_name
                ORDER BY n DESC LIMIT 10
            """,
                dept,
            )
            profile["key_metrics"] = [
                {
                    "name": r["metric_name"],
                    "avg": round(float(r["avg_val"]), 2) if r["avg_val"] else None,
                    "min": round(float(r["min_val"]), 2) if r["min_val"] else None,
                    "max": round(float(r["max_val"]), 2) if r["max_val"] else None,
                    "count": r["n"],
                }
                for r in metrics
            ]

            return {"status": "success", "profile": profile}
        except Exception as e:
            logger.error(f"DepartmentProfile error: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            await conn.close()


# --- Tool Registry Integration ---


def register_signals_tools(registry) -> None:
    """Register all signals bridge tools with the tool registry."""
    tools = [
        SignalsQueryTool(),
        MicroSignalsTool(),
        TerritorialScoringTool(),
        SignalSearchTool(),
        DepartmentProfileTool(),
    ]
    for tool in tools:
        registry.register(tool)
    logger.info(f"Registered {len(tools)} signals bridge tools")


# Convenience: list all tool names
SIGNALS_TOOLS = [
    "signals_query",
    "microsignals_query",
    "territorial_scoring",
    "signal_search",
    "department_profile",
]
