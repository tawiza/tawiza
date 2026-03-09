"""Territorial Knowledge Graph - PostgreSQL-backed graph over real signals.

Replaces Neo4j dependency with a lightweight in-process graph built from
the signals database. Supports:
- Entity extraction from signals (departments, sources, sectors, companies)
- Relationship inference (co-occurrence, causal, temporal)
- Gap detection for active learning
- Causal chain traversal
- GraphRAG-style retrieval (subgraph extraction for LLM context)

Architecture:
    signals DB → TerritorialKG (in-memory graph) → TAJINE Agent
    
The graph is rebuilt periodically from the DB and cached in memory.
No Neo4j required.
"""

import asyncio
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import asyncpg
from loguru import logger

DB_URL = os.getenv(
    "COLLECTOR_DATABASE_URL",
    "postgresql://localhost:5433/tawiza"
).replace("postgresql+asyncpg://", "postgresql://").replace("postgresql://", "postgres://")


@dataclass
class KGNode:
    """Node in the knowledge graph."""
    id: str  # e.g. "dept:75", "source:bodacc", "sector:tech"
    type: str  # department, source, sector, signal_type, metric
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class KGEdge:
    """Edge in the knowledge graph."""
    source_id: str
    target_id: str
    relation: str  # has_signal, co_occurs, causes, temporal_lag, anomaly_in
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class KGSubgraph:
    """A subgraph extracted for context."""
    nodes: list[KGNode]
    edges: list[KGEdge]
    query: str
    relevance_score: float = 0.0

    def to_text(self) -> str:
        """Convert subgraph to natural language for LLM context."""
        lines = []
        # Group by department
        dept_nodes = [n for n in self.nodes if n.type == "department"]
        for dept in dept_nodes:
            dept_edges = [e for e in self.edges if e.source_id == dept.id or e.target_id == dept.id]
            lines.append(f"\n## {dept.label} ({dept.id})")
            lines.append(f"  Signaux: {dept.properties.get('total_signals', '?')}")
            lines.append(f"  Sources: {dept.properties.get('num_sources', '?')}")
            
            for edge in dept_edges:
                other_id = edge.target_id if edge.source_id == dept.id else edge.source_id
                other = next((n for n in self.nodes if n.id == other_id), None)
                if other:
                    lines.append(f"  → {edge.relation}: {other.label} (poids={edge.weight:.2f})")
                    if edge.properties:
                        for k, v in edge.properties.items():
                            lines.append(f"    {k}: {v}")
        
        # Causal chains
        causal = [e for e in self.edges if e.relation == "causes"]
        if causal:
            lines.append("\n## Chaînes causales")
            for e in causal:
                src = next((n for n in self.nodes if n.id == e.source_id), None)
                tgt = next((n for n in self.nodes if n.id == e.target_id), None)
                if src and tgt:
                    lag = e.properties.get("lag_months", "?")
                    lines.append(f"  {src.label} → {tgt.label} (corrélation={e.weight:.2f}, lag={lag} mois)")
        
        # Anomalies
        anomalies = [e for e in self.edges if e.relation == "anomaly_in"]
        if anomalies:
            lines.append("\n## Anomalies détectées")
            for e in anomalies:
                tgt = next((n for n in self.nodes if n.id == e.target_id), None)
                if tgt:
                    lines.append(f"  Score={e.weight:.2f}: {e.properties.get('description', tgt.label)}")
        
        return "\n".join(lines)


class TerritorialKG:
    """In-memory knowledge graph built from the signals database.
    
    Features:
    - Auto-builds from PostgreSQL signals + micro_signals tables
    - Supports subgraph extraction for GraphRAG
    - Causal inference between sources/dimensions
    - Gap detection for active learning
    - Thread-safe rebuilds with asyncio.Lock
    """

    def __init__(self):
        self.nodes: dict[str, KGNode] = {}
        self.edges: list[KGEdge] = []
        self._adjacency: dict[str, list[KGEdge]] = defaultdict(list)
        self._reverse_adjacency: dict[str, list[KGEdge]] = defaultdict(list)
        self._built_at: datetime | None = None
        self._build_lock = asyncio.Lock()
        self._causal_rules: list[dict] = self._init_causal_rules()

    def _init_causal_rules(self) -> list[dict]:
        """Define known causal relationships between signal dimensions."""
        return [
            {
                "cause": "metric:liquidations_count",
                "effect": "metric:offres_emploi_count",
                "relation": "causes",
                "direction": "negative",  # more liquidations → fewer jobs
                "lag_months": 3,
                "base_confidence": 0.7,
            },
            {
                "cause": "metric:creations_count",
                "effect": "metric:offres_emploi_count",
                "relation": "causes",
                "direction": "positive",
                "lag_months": 6,
                "base_confidence": 0.6,
            },
            {
                "cause": "metric:prix_m2_median",
                "effect": "metric:creations_count",
                "relation": "causes",
                "direction": "negative",  # high prices → fewer new businesses
                "lag_months": 6,
                "base_confidence": 0.5,
            },
            {
                "cause": "metric:offres_emploi_count",
                "effect": "metric:prix_m2_median",
                "relation": "causes",
                "direction": "positive",  # more jobs → higher prices
                "lag_months": 12,
                "base_confidence": 0.5,
            },
            {
                "cause": "source:bodacc",
                "effect": "source:france_travail",
                "relation": "leads",
                "direction": "predictive",
                "lag_months": 3,
                "base_confidence": 0.6,
            },
            {
                "cause": "source:dvf",
                "effect": "source:sirene",
                "relation": "leads",
                "direction": "predictive",
                "lag_months": 6,
                "base_confidence": 0.5,
            },
        ]

    async def build(self, force: bool = False) -> None:
        """Build/rebuild the knowledge graph from the database.
        
        Args:
            force: Force rebuild even if recently built
        """
        if not force and self._built_at and (datetime.now() - self._built_at).seconds < 3600:
            return  # Skip if built less than 1 hour ago
        
        async with self._build_lock:
            logger.info("Building Territorial Knowledge Graph from signals DB...")
            start = datetime.now()
            
            self.nodes.clear()
            self.edges.clear()
            self._adjacency.clear()
            self._reverse_adjacency.clear()
            
            try:
                conn = await asyncpg.connect(DB_URL, timeout=10)
                try:
                    await self._build_department_nodes(conn)
                    await self._build_source_nodes(conn)
                    await self._build_dept_source_edges(conn)
                    await self._build_signal_type_nodes(conn)
                    await self._build_metric_nodes(conn)
                    await self._build_microsignal_edges(conn)
                    self._build_causal_edges()
                    await self._detect_temporal_correlations(conn)
                finally:
                    await conn.close()
                
                self._built_at = datetime.now()
                elapsed = (datetime.now() - start).total_seconds()
                logger.info(
                    f"KG built: {len(self.nodes)} nodes, {len(self.edges)} edges "
                    f"in {elapsed:.1f}s"
                )
            except Exception as e:
                logger.error(f"Failed to build KG: {e}")

    async def _build_department_nodes(self, conn: asyncpg.Connection) -> None:
        """Create nodes for each department with signal stats."""
        rows = await conn.fetch("""
            SELECT code_dept, count(*) as total, 
                   count(DISTINCT source) as sources,
                   min(event_date) as earliest,
                   max(event_date) as latest
            FROM signals WHERE code_dept IS NOT NULL
            GROUP BY code_dept
        """)
        for r in rows:
            node_id = f"dept:{r['code_dept']}"
            self.nodes[node_id] = KGNode(
                id=node_id,
                type="department",
                label=f"Département {r['code_dept']}",
                properties={
                    "code": r["code_dept"],
                    "total_signals": r["total"],
                    "num_sources": r["sources"],
                    "earliest": str(r["earliest"]) if r["earliest"] else None,
                    "latest": str(r["latest"]) if r["latest"] else None,
                },
            )

    async def _build_source_nodes(self, conn: asyncpg.Connection) -> None:
        """Create nodes for each data source."""
        rows = await conn.fetch("""
            SELECT source, count(*) as total,
                   count(DISTINCT code_dept) as depts_covered
            FROM signals GROUP BY source
        """)
        for r in rows:
            node_id = f"source:{r['source']}"
            self.nodes[node_id] = KGNode(
                id=node_id,
                type="source",
                label=r["source"].replace("_", " ").title(),
                properties={
                    "total_signals": r["total"],
                    "departments_covered": r["depts_covered"],
                },
            )

    async def _build_dept_source_edges(self, conn: asyncpg.Connection) -> None:
        """Create edges between departments and sources with signal counts."""
        rows = await conn.fetch("""
            SELECT code_dept, source, count(*) as n
            FROM signals WHERE code_dept IS NOT NULL
            GROUP BY code_dept, source
        """)
        for r in rows:
            edge = KGEdge(
                source_id=f"dept:{r['code_dept']}",
                target_id=f"source:{r['source']}",
                relation="has_signals_from",
                weight=r["n"],
                properties={"signal_count": r["n"]},
            )
            self._add_edge(edge)

    async def _build_signal_type_nodes(self, conn: asyncpg.Connection) -> None:
        """Create nodes for signal types."""
        rows = await conn.fetch("""
            SELECT signal_type, count(*) as total
            FROM signals WHERE signal_type IS NOT NULL
            GROUP BY signal_type ORDER BY total DESC
        """)
        for r in rows:
            node_id = f"type:{r['signal_type']}"
            self.nodes[node_id] = KGNode(
                id=node_id,
                type="signal_type",
                label=r["signal_type"],
                properties={"total": r["total"]},
            )

    async def _build_metric_nodes(self, conn: asyncpg.Connection) -> None:
        """Create nodes for metrics with stats."""
        rows = await conn.fetch("""
            SELECT metric_name, count(*) as total,
                   avg(metric_value) as avg_val,
                   stddev(metric_value) as std_val
            FROM signals 
            WHERE metric_name IS NOT NULL AND metric_value IS NOT NULL
            GROUP BY metric_name
            HAVING count(*) >= 5
        """)
        for r in rows:
            node_id = f"metric:{r['metric_name']}"
            self.nodes[node_id] = KGNode(
                id=node_id,
                type="metric",
                label=r["metric_name"],
                properties={
                    "total": r["total"],
                    "avg": round(float(r["avg_val"]), 2) if r["avg_val"] else None,
                    "std": round(float(r["std_val"]), 2) if r["std_val"] else None,
                },
            )

    async def _build_microsignal_edges(self, conn: asyncpg.Connection) -> None:
        """Create edges from micro-signals (anomalies, convergences)."""
        rows = await conn.fetch("""
            SELECT territory_code, signal_type, sources, dimensions,
                   score, description
            FROM micro_signals
            WHERE is_active = true AND score > 0.3
        """)
        for r in rows:
            dept_id = f"dept:{r['territory_code']}"
            # Create anomaly edge
            edge = KGEdge(
                source_id=dept_id,
                target_id=f"anomaly:{r['territory_code']}:{r['signal_type']}",
                relation="anomaly_in",
                weight=float(r["score"]) if r["score"] else 0,
                properties={
                    "type": r["signal_type"],
                    "sources": r["sources"],
                    "dimensions": r["dimensions"],
                    "description": r["description"],
                },
            )
            # Create anomaly node if not exists
            anomaly_id = f"anomaly:{r['territory_code']}:{r['signal_type']}"
            if anomaly_id not in self.nodes:
                self.nodes[anomaly_id] = KGNode(
                    id=anomaly_id,
                    type="anomaly",
                    label=f"{r['signal_type']} in {r['territory_code']}",
                    properties={
                        "score": float(r["score"]) if r["score"] else 0,
                        "description": r["description"],
                    },
                )
            self._add_edge(edge)

    def _build_causal_edges(self) -> None:
        """Add known causal relationship edges."""
        for rule in self._causal_rules:
            if rule["cause"] in self.nodes and rule["effect"] in self.nodes:
                edge = KGEdge(
                    source_id=rule["cause"],
                    target_id=rule["effect"],
                    relation="causes",
                    weight=rule["base_confidence"],
                    properties={
                        "direction": rule["direction"],
                        "lag_months": rule["lag_months"],
                    },
                )
                self._add_edge(edge)

    async def _detect_temporal_correlations(self, conn: asyncpg.Connection) -> None:
        """Detect temporal correlations between sources for each department."""
        # For top 20 departments, check if source volumes correlate over time
        top_depts = await conn.fetch("""
            SELECT code_dept, count(*) as n FROM signals 
            WHERE code_dept IS NOT NULL
            GROUP BY code_dept ORDER BY n DESC LIMIT 20
        """)
        
        for dept_row in top_depts:
            dept = dept_row["code_dept"]
            # Get monthly counts per source
            rows = await conn.fetch("""
                SELECT source, date_trunc('month', event_date) as month, count(*) as n
                FROM signals
                WHERE code_dept = $1 AND event_date IS NOT NULL
                GROUP BY source, month
                ORDER BY month
            """, dept)
            
            # Group by source
            source_series: dict[str, dict[str, int]] = defaultdict(dict)
            for r in rows:
                if r["month"]:
                    source_series[r["source"]][str(r["month"].date())] = r["n"]
            
            # Check co-occurrence patterns (simple: sources active in same months)
            sources = list(source_series.keys())
            for i in range(len(sources)):
                for j in range(i + 1, len(sources)):
                    s1, s2 = sources[i], sources[j]
                    months_s1 = set(source_series[s1].keys())
                    months_s2 = set(source_series[s2].keys())
                    overlap = len(months_s1 & months_s2)
                    total = len(months_s1 | months_s2)
                    if total > 0 and overlap / total > 0.5:
                        edge = KGEdge(
                            source_id=f"dept:{dept}",
                            target_id=f"cooccurrence:{dept}:{s1}:{s2}",
                            relation="co_occurrence",
                            weight=overlap / total,
                            properties={
                                "source_a": s1,
                                "source_b": s2,
                                "overlap_months": overlap,
                                "total_months": total,
                            },
                        )
                        self._add_edge(edge)

    def _add_edge(self, edge: KGEdge) -> None:
        """Add an edge and update adjacency lists."""
        self.edges.append(edge)
        self._adjacency[edge.source_id].append(edge)
        self._reverse_adjacency[edge.target_id].append(edge)

    # --- Query Methods ---

    def get_subgraph(self, center_id: str, depth: int = 2) -> KGSubgraph:
        """Extract a subgraph around a center node.
        
        Args:
            center_id: Center node ID (e.g. "dept:75")
            depth: How many hops from center
            
        Returns:
            KGSubgraph with relevant nodes and edges
        """
        visited_nodes: set[str] = set()
        relevant_edges: list[KGEdge] = []
        queue = [(center_id, 0)]
        
        while queue:
            node_id, d = queue.pop(0)
            if node_id in visited_nodes or d > depth:
                continue
            visited_nodes.add(node_id)
            
            # Get outgoing edges
            for edge in self._adjacency.get(node_id, []):
                relevant_edges.append(edge)
                if edge.target_id not in visited_nodes and d + 1 <= depth:
                    queue.append((edge.target_id, d + 1))
            
            # Get incoming edges
            for edge in self._reverse_adjacency.get(node_id, []):
                relevant_edges.append(edge)
                if edge.source_id not in visited_nodes and d + 1 <= depth:
                    queue.append((edge.source_id, d + 1))
        
        nodes = [self.nodes[nid] for nid in visited_nodes if nid in self.nodes]
        return KGSubgraph(nodes=nodes, edges=relevant_edges, query=center_id)

    def get_department_context(self, dept_code: str) -> str:
        """Get rich text context for a department, suitable for LLM injection.
        
        This is the main GraphRAG interface - extracts a subgraph and
        converts it to structured text that an LLM can reason over.
        """
        subgraph = self.get_subgraph(f"dept:{dept_code}", depth=2)
        return subgraph.to_text()

    def find_causal_chain(
        self, cause_id: str, effect_id: str, max_depth: int = 4
    ) -> list[KGEdge] | None:
        """Find a causal chain between two nodes using BFS."""
        visited = set()
        queue = [(cause_id, [])]
        
        while queue:
            current, path = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            
            if current == effect_id and path:
                return path
            
            if len(path) >= max_depth:
                continue
            
            for edge in self._adjacency.get(current, []):
                if edge.relation in ("causes", "leads") and edge.target_id not in visited:
                    queue.append((edge.target_id, path + [edge]))
        
        return None

    def find_gaps(self) -> list[dict[str, Any]]:
        """Detect knowledge gaps for active learning.
        
        Returns:
            List of gaps with suggestions for what data to collect
        """
        gaps = []
        
        # 1. Departments with few sources
        for node_id, node in self.nodes.items():
            if node.type == "department":
                num_sources = node.properties.get("num_sources", 0)
                total = node.properties.get("total_signals", 0)
                dept = node.properties.get("code", "")
                
                if num_sources < 4:
                    # Find which sources are missing
                    active_sources = set()
                    for edge in self._adjacency.get(node_id, []):
                        if edge.relation == "has_signals_from":
                            active_sources.add(edge.target_id.replace("source:", ""))
                    
                    all_sources = {"bodacc", "france_travail", "dvf", "sirene", "insee", "ofgl", "urssaf", "presse"}
                    missing = all_sources - active_sources
                    
                    gaps.append({
                        "type": "missing_sources",
                        "department": dept,
                        "priority": 1 if num_sources < 2 else 2,
                        "current_sources": num_sources,
                        "missing_sources": list(missing),
                        "suggestion": f"Collect data from {', '.join(list(missing)[:3])} for dept {dept}",
                    })
                
                if total < 100 and dept:
                    gaps.append({
                        "type": "low_coverage",
                        "department": dept,
                        "priority": 1,
                        "total_signals": total,
                        "suggestion": f"Run full collection for dept {dept} (only {total} signals)",
                    })
        
        # 2. Sources not covering enough departments
        for node_id, node in self.nodes.items():
            if node.type == "source":
                depts = node.properties.get("departments_covered", 0)
                source_name = node_id.replace("source:", "")
                if depts < 50:
                    gaps.append({
                        "type": "source_low_coverage",
                        "source": source_name,
                        "priority": 2,
                        "departments_covered": depts,
                        "suggestion": f"Expand {source_name} collection to more departments",
                    })
        
        # 3. No micro-signals detected for well-covered departments
        depts_with_anomalies = set()
        for edge in self.edges:
            if edge.relation == "anomaly_in":
                dept_code = edge.source_id.replace("dept:", "")
                depts_with_anomalies.add(dept_code)
        
        for node_id, node in self.nodes.items():
            if node.type == "department":
                dept = node.properties.get("code", "")
                total = node.properties.get("total_signals", 0)
                if total > 500 and dept not in depts_with_anomalies:
                    gaps.append({
                        "type": "no_anomalies_detected",
                        "department": dept,
                        "priority": 3,
                        "total_signals": total,
                        "suggestion": f"Re-run anomaly detection for dept {dept} ({total} signals, no anomalies)",
                    })
        
        gaps.sort(key=lambda g: g["priority"])
        return gaps

    def get_stats(self) -> dict[str, Any]:
        """Get graph statistics."""
        type_counts = defaultdict(int)
        for node in self.nodes.values():
            type_counts[node.type] += 1
        
        relation_counts = defaultdict(int)
        for edge in self.edges:
            relation_counts[edge.relation] += 1
        
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": dict(type_counts),
            "edge_types": dict(relation_counts),
            "built_at": str(self._built_at) if self._built_at else None,
        }


# Singleton instance
_kg_instance: TerritorialKG | None = None


async def get_territorial_kg() -> TerritorialKG:
    """Get or create the singleton TerritorialKG instance."""
    global _kg_instance
    if _kg_instance is None:
        _kg_instance = TerritorialKG()
    await _kg_instance.build()
    return _kg_instance
