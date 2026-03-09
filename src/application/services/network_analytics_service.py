"""Network analytics service -- graph metrics powered by NetworkX.

Computes centrality, community detection, resilience scoring,
structural holes, Shapley value approximation, and per-actor
risk scoring from the relation graph.
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from typing import Any

import asyncpg
import networkx as nx
from loguru import logger

from src.application.services._db_pool import acquire_conn
from src.infrastructure.caching.redis_cache import get_redis_cache


def _parse_metadata(raw: Any) -> dict:
    """Safely parse metadata that asyncpg may return as str (jsonb)."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _build_networkx_graph(actors: list[dict], relations: list[dict]) -> nx.Graph:
    """Build an undirected NetworkX graph from actors and relations."""
    G = nx.Graph()
    for a in actors:
        meta = _parse_metadata(a.get("metadata"))
        G.add_node(
            a["external_id"],
            **{
                "name": a["name"],
                "type": a["type"],
                "department_code": a.get("department_code"),
                "metadata": meta,
            },
        )
    for r in relations:
        G.add_edge(
            r["src_ext"],
            r["tgt_ext"],
            weight=float(r.get("confidence", 0.5)),
            subtype=r.get("subtype", ""),
            relation_type=r.get("relation_type", ""),
        )
    return G


def _network_value(G_sub: nx.Graph) -> float:
    """Value function for Shapley: connectivity * density blend."""
    if len(G_sub) == 0:
        return 0.0
    largest_cc = max(nx.connected_components(G_sub), key=len)
    connectivity = len(largest_cc) / len(G_sub)
    dens = nx.density(G_sub)
    return connectivity * 0.7 + dens * 0.3


def _compute_shapley_values(G: nx.Graph) -> dict[str, float]:
    """Monte Carlo Shapley approximation.

    For efficiency on large graphs (396+ nodes), only compute for the
    top 50 nodes by degree.  All other nodes get shapley=0.0.

    The value function blends largest-component connectivity (70%) with
    density (30%).  Marginal contributions are averaged over random
    permutations.  Non-sampled nodes still participate in the coalition
    but their individual marginal contribution is not measured -- instead,
    the cumulative effect of non-sampled additions is attributed to the
    next sampled node (acceptable approximation for ranking).
    """
    nodes_list = list(G.nodes())
    n = len(nodes_list)
    if n == 0:
        return {}

    # Sampling: only top 50 by degree to keep computation tractable
    TOP_K = 50
    degree_sorted = sorted(nodes_list, key=lambda nd: G.degree(nd), reverse=True)
    sampled_nodes = set(degree_sorted[:TOP_K])

    shapley: dict[str, float] = dict.fromkeys(nodes_list, 0.0)

    # Scale permutations: adaptive based on graph size
    # Small graphs (<100 nodes): up to 200 perms for accuracy
    # Large graphs (>300 nodes): cap at 30 perms for speed (<2s)
    if n > 300:
        n_perms = 30
    elif n > 100:
        n_perms = 50
    else:
        n_perms = min(200, max(50, n * 2))
    rng = random.Random(42)  # Deterministic seed for reproducibility

    for _ in range(n_perms):
        perm = nodes_list[:]
        rng.shuffle(perm)
        coalition: set[str] = set()
        prev_val = 0.0
        for node in perm:
            coalition.add(node)
            if node in sampled_nodes:
                cur_val = _network_value(G.subgraph(coalition))
                shapley[node] += cur_val - prev_val
                prev_val = cur_val
            # Non-sampled nodes: coalition grows silently.
            # The next sampled node absorbs their cumulative marginal
            # contribution -- this is a deliberate speed/accuracy trade-off.

    # Average over permutations
    for node in shapley:
        shapley[node] /= n_perms

    # Normalize to [0, 1]
    max_shap = max(shapley.values()) if shapley else 1.0
    if max_shap > 0:
        shapley = {nd: round(v / max_shap, 4) for nd, v in shapley.items()}

    return shapley


def _compute_risk_scores(G: nx.Graph) -> dict[str, float]:
    """Compute a composite risk score for each actor.

    Combines four weighted factors:
    - BODACC danger signals (liquidation/redressement): 0.40
    - Network isolation (low degree):                   0.25
    - Dependency concentration (single-edge fragility): 0.20
    - Sector default rate (placeholder):                0.15
    """
    risk_scores: dict[str, float] = {}

    for node_id in G.nodes():
        node_attrs = G.nodes[node_id]
        node_meta: dict = node_attrs.get("metadata", {})
        if not isinstance(node_meta, dict):
            node_meta = {}

        # Factor 1: BODACC danger signals
        events = node_meta.get("bodacc_events", [])
        if isinstance(events, str):
            try:
                events = json.loads(events)
            except (json.JSONDecodeError, TypeError):
                events = []
        if not isinstance(events, list):
            events = []
        danger_count = sum(
            1
            for e in events
            if isinstance(e, dict) and e.get("type") in ("liquidation", "redressement")
        )
        bodacc_risk = min(danger_count * 0.3, 1.0)

        # Factor 2: Network isolation (degree <= 1 = high risk)
        deg = G.degree(node_id)
        isolation_risk = 1.0 if deg <= 1 else max(0.0, 1.0 - deg / 10.0)

        # Factor 3: Dependency concentration
        neighbors = list(G.neighbors(node_id))
        if neighbors:
            weights = [G[node_id][nb].get("weight", 1.0) for nb in neighbors]
            total_w = sum(weights)
            max_w = max(weights)
            dependency_risk = (max_w / total_w) if total_w > 0 else 0.0
        else:
            dependency_risk = 1.0

        # Factor 4: Sector default rate (placeholder, enrichable with INSEE)
        sector_risk = 0.3

        risk = (
            bodacc_risk * 0.40 + isolation_risk * 0.25 + dependency_risk * 0.20 + sector_risk * 0.15
        )
        risk_scores[node_id] = round(min(risk, 1.0), 4)

    return risk_scores


async def save_snapshot(department_code: str, discover_result: dict) -> None:
    """Save a metrics snapshot after discover().

    Persists key counts from the discover result into the
    ``relation_snapshots`` table so we can track evolution over time.
    """
    try:
        async with acquire_conn() as conn:
            await conn.execute(
                """
                INSERT INTO relation_snapshots
                (department_code, total_actors, total_relations, l1_count, l2_count, l3_count,
                 coverage_score, resilience_score, density, communities_count, metrics_json)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                department_code,
                discover_result.get("actors_upserted", 0),
                discover_result.get("relations_upserted", 0),
                discover_result.get("l1_relations", 0),
                discover_result.get("l2_relations", 0),
                discover_result.get("l3_relations", 0),
                0.0,  # Coverage is computed separately via get_coverage()
                0.0,  # Resilience -- skip full analytics computation for snapshot
                0.0,  # Density
                0,  # Communities
                json.dumps(
                    {
                        "sources_run": discover_result.get("sources_run", []),
                        "inferrers_run": discover_result.get("inferrers_run", []),
                        "predictors_run": discover_result.get("predictors_run", []),
                    }
                ),
            )
            logger.info("Snapshot saved for dept {}", department_code)
    except Exception as e:
        logger.warning("Failed to save snapshot for dept {}: {}", department_code, e)


async def get_timeline(department_code: str, limit: int = 20) -> dict:
    """Get historical snapshots for a department.

    Returns the *limit* most recent snapshots in chronological order
    (oldest first) so frontends can render trend charts directly.
    """
    async with acquire_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT snapshot_at, total_actors, total_relations,
                   l1_count, l2_count, l3_count,
                   coverage_score, resilience_score, density, communities_count
            FROM relation_snapshots
            WHERE department_code = $1
            ORDER BY snapshot_at DESC
            LIMIT $2
            """,
            department_code,
            limit,
        )

        points = []
        for row in rows:
            points.append(
                {
                    "timestamp": row["snapshot_at"].isoformat(),
                    "total_actors": row["total_actors"],
                    "total_relations": row["total_relations"],
                    "l1_count": row["l1_count"],
                    "l2_count": row["l2_count"],
                    "l3_count": row["l3_count"],
                    "coverage_score": row["coverage_score"],
                    "resilience_score": row["resilience_score"],
                    "density": row["density"],
                    "communities_count": row["communities_count"],
                }
            )

        return {
            "department_code": department_code,
            "total_snapshots": len(points),
            "points": list(reversed(points)),  # Chronological order
        }


async def compute_network_analytics(department_code: str | None = None) -> dict[str, Any]:
    """Compute full network analytics for a department (or all departments if None)."""

    # Try cache first (analytics is expensive: Shapley + NetworkX)
    _cache_label = department_code or "all"
    _analytics_cache_key = f"relations:{_cache_label}:analytics"
    try:
        cache = await get_redis_cache()
        cached = await cache.get(_analytics_cache_key)
        if cached is not None:
            logger.debug("Cache hit for network analytics dept={}", _cache_label)
            return cached
    except Exception:
        logger.debug("Cache miss/error for analytics dept={}", _cache_label)

    async with acquire_conn() as conn:
        if department_code is not None:
            actors = await conn.fetch(
                "SELECT external_id, name, type::text, department_code, metadata FROM actors WHERE department_code = $1",
                department_code,
            )
            relations = await conn.fetch(
                """
                SELECT a_src.external_id AS src_ext, a_tgt.external_id AS tgt_ext,
                       r.relation_type::text, r.subtype, r.confidence, r.weight
                FROM relations r
                JOIN actors a_src ON r.source_actor_id = a_src.id
                JOIN actors a_tgt ON r.target_actor_id = a_tgt.id
                WHERE a_src.department_code = $1 OR a_tgt.department_code = $1
                """,
                department_code,
            )
        else:
            actors = await conn.fetch(
                "SELECT external_id, name, type::text, department_code, metadata FROM actors",
            )
            relations = await conn.fetch(
                """
                SELECT a_src.external_id AS src_ext, a_tgt.external_id AS tgt_ext,
                       r.relation_type::text, r.subtype, r.confidence, r.weight
                FROM relations r
                JOIN actors a_src ON r.source_actor_id = a_src.id
                JOIN actors a_tgt ON r.target_actor_id = a_tgt.id
                """,
            )

    if not actors or not relations:
        return {"error": "No data for this department"}

    actor_list = [dict(a) for a in actors]
    rel_list = [dict(r) for r in relations]
    G = _build_networkx_graph(actor_list, rel_list)

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    if n_nodes == 0:
        return {"error": "Empty graph"}

    # --- 1. Centrality metrics ---
    betweenness = nx.betweenness_centrality(G, weight="weight")
    pagerank = nx.pagerank(G, weight="weight", max_iter=100)
    degree_cent = nx.degree_centrality(G)
    try:
        eigenvector = nx.eigenvector_centrality(G, weight="weight", max_iter=200)
    except nx.PowerIterationFailedConvergence:
        eigenvector = dict.fromkeys(G.nodes(), 0.0)

    # --- 2. Community detection (Louvain) ---
    try:
        communities = nx.community.louvain_communities(G, weight="weight", seed=42)
    except (nx.NetworkXError, ValueError, ZeroDivisionError) as e:
        logger.warning("Louvain community detection failed: {}", e)
        communities = [set(G.nodes())]

    node_community: dict[str, int] = {}
    community_details: list[dict] = []
    for i, comm in enumerate(communities):
        for node in comm:
            node_community[node] = i
        types_in_comm: dict[str, int] = defaultdict(int)
        for node in comm:
            ntype = G.nodes[node].get("type", "unknown")
            types_in_comm[ntype] += 1
        dominant_type = max(types_in_comm, key=types_in_comm.get)
        community_details.append(
            {
                "id": i,
                "size": len(comm),
                "composition": dict(types_in_comm),
                "dominant_type": dominant_type,
            }
        )

    # --- 3. Resilience score ---
    density = nx.density(G)
    avg_clustering = nx.average_clustering(G, weight="weight")

    # Robustness: remove top-3 betweenness nodes, check fragmentation
    top_betweenness = sorted(betweenness, key=betweenness.get, reverse=True)[:3]
    G_copy = G.copy()
    G_copy.remove_nodes_from(top_betweenness)
    components_after = nx.number_connected_components(G_copy)
    largest_cc_after = (
        len(max(nx.connected_components(G_copy), key=len)) if G_copy.number_of_nodes() > 0 else 0
    )
    fragmentation = 1.0 - (largest_cc_after / max(n_nodes - 3, 1))

    # Sector diversity (Shannon entropy of actor types)
    type_counts: dict[str, int] = defaultdict(int)
    for _, data in G.nodes(data=True):
        type_counts[data.get("type", "unknown")] += 1
    total = sum(type_counts.values())
    entropy = -sum((c / total) * math.log2(c / total) for c in type_counts.values() if c > 0)
    max_entropy = math.log2(max(len(type_counts), 1))
    diversity = entropy / max_entropy if max_entropy > 0 else 0

    resilience_score = round(
        diversity * 0.30 + avg_clustering * 0.25 + density * 0.20 + (1 - fragmentation) * 0.25,
        4,
    )

    # --- 4. Structural holes (Burt's constraint) ---
    constraint = nx.constraint(G, weight="weight")
    structural_holes = []
    for node, c_val in sorted(constraint.items(), key=lambda x: x[1]):
        if c_val < 0.5:
            structural_holes.append(
                {
                    "actor_external_id": node,
                    "actor_name": G.nodes[node].get("name", node),
                    "actor_type": G.nodes[node].get("type", "unknown"),
                    "constraint": round(c_val, 4),
                    "brokerage_potential": round(1.0 - c_val, 4),
                }
            )
    structural_holes = structural_holes[:20]

    # --- 5. Shapley values (Monte Carlo approximation) ---
    shapley = _compute_shapley_values(G)

    # --- 6. Risk scoring ---
    risk_scores = _compute_risk_scores(G)

    # --- 7. Node-level metrics (includes shapley + risk) ---
    node_metrics: dict[str, dict] = {}
    for node in G.nodes():
        node_metrics[node] = {
            "betweenness": round(betweenness.get(node, 0), 6),
            "pagerank": round(pagerank.get(node, 0), 6),
            "degree": round(degree_cent.get(node, 0), 6),
            "eigenvector": round(eigenvector.get(node, 0), 6),
            "community_id": node_community.get(node, -1),
            "shapley": shapley.get(node, 0.0),
            "risk_score": risk_scores.get(node, 0.0),
        }

    # --- 8. Critical actors (top betweenness = bridges) ---
    critical_actors = []
    for node in top_betweenness:
        critical_actors.append(
            {
                "actor_external_id": node,
                "actor_name": G.nodes[node].get("name", node),
                "actor_type": G.nodes[node].get("type", "unknown"),
                "betweenness": round(betweenness[node], 6),
                "pagerank": round(pagerank.get(node, 0), 6),
                "degree": G.degree(node),
            }
        )

    # --- 9. Shapley top 10 ---
    shapley_sorted = sorted(shapley.items(), key=lambda x: x[1], reverse=True)[:10]
    shapley_top = [
        {
            "actor_external_id": nid,
            "actor_name": G.nodes[nid].get("name", nid),
            "actor_type": G.nodes[nid].get("type", "unknown"),
            "shapley_value": val,
        }
        for nid, val in shapley_sorted
    ]

    # --- 10. Risk ranking top 10 ---
    risk_sorted = sorted(risk_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    risk_ranking = [
        {
            "actor_external_id": nid,
            "actor_name": G.nodes[nid].get("name", nid),
            "actor_type": G.nodes[nid].get("type", "unknown"),
            "risk_score": val,
        }
        for nid, val in risk_sorted
    ]

    logger.info(
        "NetworkAnalytics dept={}: {} nodes, {} edges, {} communities, "
        "resilience={:.3f}, shapley_computed={}, risk_computed={}",
        _cache_label,
        n_nodes,
        n_edges,
        len(communities),
        resilience_score,
        len([v for v in shapley.values() if v > 0]),
        len(risk_scores),
    )

    result = {
        "department_code": _cache_label,
        "graph_summary": {
            "total_nodes": n_nodes,
            "total_edges": n_edges,
            "density": round(density, 6),
            "avg_clustering": round(avg_clustering, 6),
            "connected_components": nx.number_connected_components(G),
            "type_distribution": dict(type_counts),
        },
        "resilience": {
            "score": resilience_score,
            "diversity": round(diversity, 4),
            "clustering": round(avg_clustering, 4),
            "density": round(density, 4),
            "robustness": round(1 - fragmentation, 4),
            "components_after_removal": components_after,
            "removed_hubs": [G.nodes[n].get("name", n) for n in top_betweenness],
        },
        "communities": community_details,
        "critical_actors": critical_actors,
        "structural_holes": structural_holes,
        "node_metrics": node_metrics,
        "shapley_top": shapley_top,
        "risk_ranking": risk_ranking,
    }

    # Cache the result (TTL 900s = 15 min)
    try:
        cache = await get_redis_cache()
        await cache.set(_analytics_cache_key, result, ttl=3600)
    except Exception:
        logger.debug("Cache set error for analytics dept={}", _cache_label)

    return result
