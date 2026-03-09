"""Strategic analysis tools for territorial intelligence.

Provides:
- Network analysis (connections between actors)
- Benchmarking (compare territories)
- Trend detection (emerging sectors)
- Gap identification (opportunities)
"""

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry


def register_strategy_tools(registry: ToolRegistry) -> None:
    """Register strategic analysis tools."""

    async def network_analyze(actors: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze network relationships between actors.

        Detects clusters, central actors, and potential connections based on:
        - Geographic proximity
        - Sector similarity
        - Size compatibility

        Args:
            actors: List of actor dicts with 'nom', 'type', 'activite', 'commune', etc.

        Returns:
            Dict with network analysis: clusters, central actors, connections
        """
        try:
            if not actors or len(actors) < 2:
                return {"success": False, "error": "Need at least 2 actors for network analysis"}

            # Build connections based on attributes
            connections = []
            clusters_by_commune = defaultdict(list)
            clusters_by_sector = defaultdict(list)

            for i, actor in enumerate(actors):
                # Group by commune
                commune = actor.get("commune") or actor.get("adresse", {}).get("commune")
                if commune:
                    clusters_by_commune[commune].append(actor.get("nom", f"Actor_{i}"))

                # Group by sector/activity
                sector = actor.get("activite") or actor.get("libelle_activite") or actor.get("section_activite")
                if sector:
                    clusters_by_sector[sector[:30]].append(actor.get("nom", f"Actor_{i}"))

            # Find potential connections (same commune or sector)
            for i, a1 in enumerate(actors):
                for j, a2 in enumerate(actors[i + 1:], i + 1):
                    connection_reasons = []

                    # Same commune
                    c1 = a1.get("commune") or a1.get("adresse", {}).get("commune")
                    c2 = a2.get("commune") or a2.get("adresse", {}).get("commune")
                    if c1 and c2 and c1 == c2:
                        connection_reasons.append("proximity")

                    # Similar sector
                    s1 = a1.get("activite") or a1.get("libelle_activite", "")
                    s2 = a2.get("activite") or a2.get("libelle_activite", "")
                    if s1 and s2 and (s1[:10] == s2[:10] or any(w in s2.lower() for w in s1.lower().split()[:2])):
                        connection_reasons.append("sector")

                    # Complementary types (startup + incubateur, etc.)
                    t1 = a1.get("type", "").lower()
                    t2 = a2.get("type", "").lower()
                    complementary = [
                        ("startup", "incubateur"),
                        ("startup", "investisseur"),
                        ("entreprise", "laboratoire"),
                        ("entreprise", "cluster"),
                    ]
                    for pair in complementary:
                        if (t1 in pair and t2 in pair) and t1 != t2:
                            connection_reasons.append("complementary")
                            break

                    if connection_reasons:
                        connections.append({
                            "from": a1.get("nom", f"Actor_{i}"),
                            "to": a2.get("nom", f"Actor_{j}"),
                            "reasons": connection_reasons,
                            "strength": len(connection_reasons),
                        })

            # Calculate centrality (number of connections per actor)
            centrality = Counter()
            for conn in connections:
                centrality[conn["from"]] += conn["strength"]
                centrality[conn["to"]] += conn["strength"]

            # Get top actors
            central_actors = centrality.most_common(10)

            # Format clusters (filter small ones)
            geo_clusters = {k: v for k, v in clusters_by_commune.items() if len(v) >= 2}
            sector_clusters = {k: v for k, v in clusters_by_sector.items() if len(v) >= 2}

            return {
                "success": True,
                "total_actors": len(actors),
                "connections": connections[:50],  # Top 50 connections
                "connection_count": len(connections),
                "central_actors": [{"name": name, "score": score} for name, score in central_actors],
                "clusters": {
                    "by_location": dict(list(geo_clusters.items())[:10]),
                    "by_sector": dict(list(sector_clusters.items())[:10]),
                },
                "density": round(len(connections) / (len(actors) * (len(actors) - 1) / 2) * 100, 1) if len(actors) > 1 else 0,
            }

        except Exception as e:
            logger.error(f"Network analysis failed: {e}")
            return {"success": False, "error": str(e)}

    async def benchmark_compare(
        region1_data: dict[str, Any],
        region2_data: dict[str, Any],
        criteria: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compare two territories/regions.

        Args:
            region1_data: Dict with region name and metrics (actors count, sectors, etc.)
            region2_data: Dict with region name and metrics
            criteria: List of criteria to compare (default: all available)

        Returns:
            Dict with comparison results and recommendations
        """
        try:
            r1_name = region1_data.get("name", "Region 1")
            r2_name = region2_data.get("name", "Region 2")

            default_criteria = ["actors_count", "startups_count", "sectors", "average_size"]
            criteria = criteria or default_criteria

            comparisons = []
            r1_wins = 0
            r2_wins = 0

            for criterion in criteria:
                v1 = region1_data.get(criterion)
                v2 = region2_data.get(criterion)

                if v1 is None or v2 is None:
                    continue

                if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                    diff = v1 - v2
                    diff_pct = round((diff / v2 * 100) if v2 != 0 else 0, 1)
                    winner = r1_name if v1 > v2 else r2_name if v2 > v1 else "tie"

                    if winner == r1_name:
                        r1_wins += 1
                    elif winner == r2_name:
                        r2_wins += 1

                    comparisons.append({
                        "criterion": criterion,
                        "values": {r1_name: v1, r2_name: v2},
                        "difference": diff,
                        "difference_pct": diff_pct,
                        "winner": winner,
                    })

                elif isinstance(v1, list) and isinstance(v2, list):
                    only_r1 = set(v1) - set(v2)
                    only_r2 = set(v2) - set(v1)
                    common = set(v1) & set(v2)

                    comparisons.append({
                        "criterion": criterion,
                        "values": {r1_name: len(v1), r2_name: len(v2)},
                        "unique_to_" + r1_name: list(only_r1)[:10],
                        "unique_to_" + r2_name: list(only_r2)[:10],
                        "common": list(common)[:10],
                    })

            overall_winner = r1_name if r1_wins > r2_wins else r2_name if r2_wins > r1_wins else "tie"

            # Generate recommendations
            recommendations = []
            for comp in comparisons:
                if comp.get("winner") and comp["winner"] != r1_name and comp.get("difference_pct"):
                    if abs(comp["difference_pct"]) > 20:
                        recommendations.append(
                            f"Améliorer {comp['criterion']}: écart de {abs(comp['difference_pct'])}% avec {r2_name}"
                        )

            return {
                "success": True,
                "regions": [r1_name, r2_name],
                "comparisons": comparisons,
                "summary": {
                    "wins": {r1_name: r1_wins, r2_name: r2_wins},
                    "overall_leader": overall_winner,
                },
                "recommendations": recommendations[:5],
            }

        except Exception as e:
            logger.error(f"Benchmark comparison failed: {e}")
            return {"success": False, "error": str(e)}

    async def trends_detect(
        actors: list[dict[str, Any]],
        time_field: str = "date_creation",
    ) -> dict[str, Any]:
        """Detect trends in actor data.

        Analyzes:
        - Growing sectors (by creation date or count)
        - Emerging activities
        - Geographic hotspots

        Args:
            actors: List of actor data
            time_field: Field containing date for temporal analysis

        Returns:
            Dict with detected trends
        """
        try:
            if not actors:
                return {"success": False, "error": "No actors provided"}

            # Analyze sectors
            sector_counts = Counter()
            sector_recent = Counter()  # Created in last 3 years
            type_counts = Counter()
            commune_counts = Counter()

            current_year = datetime.now().year

            for actor in actors:
                # Count sectors
                sector = actor.get("activite") or actor.get("libelle_activite") or actor.get("section_activite")
                if sector:
                    sector_key = sector[:40]
                    sector_counts[sector_key] += 1

                    # Check if recent
                    date_str = actor.get(time_field, "")
                    if date_str:
                        try:
                            year = int(str(date_str)[:4])
                            if current_year - year <= 3:
                                sector_recent[sector_key] += 1
                        except (ValueError, IndexError):
                            pass

                # Count types
                actor_type = actor.get("type")
                if actor_type:
                    type_counts[actor_type] += 1

                # Count communes
                commune = actor.get("commune") or actor.get("adresse", {}).get("commune")
                if commune:
                    commune_counts[commune] += 1

            # Calculate growth rates
            growing_sectors = []
            for sector, total in sector_counts.most_common(20):
                recent = sector_recent.get(sector, 0)
                if total >= 3:
                    growth_rate = round(recent / total * 100, 1)
                    growing_sectors.append({
                        "sector": sector,
                        "total": total,
                        "recent": recent,
                        "growth_rate": growth_rate,
                    })

            # Sort by growth rate
            growing_sectors.sort(key=lambda x: x["growth_rate"], reverse=True)

            return {
                "success": True,
                "total_actors": len(actors),
                "trends": {
                    "growing_sectors": growing_sectors[:10],
                    "top_sectors": [{"sector": s, "count": c} for s, c in sector_counts.most_common(10)],
                    "actor_types": [{"type": t, "count": c} for t, c in type_counts.most_common(10)],
                    "hotspot_communes": [{"commune": c, "count": n} for c, n in commune_counts.most_common(10)],
                },
                "insights": {
                    "fastest_growing": growing_sectors[0]["sector"] if growing_sectors else None,
                    "dominant_sector": sector_counts.most_common(1)[0][0] if sector_counts else None,
                    "main_hotspot": commune_counts.most_common(1)[0][0] if commune_counts else None,
                },
            }

        except Exception as e:
            logger.error(f"Trend detection failed: {e}")
            return {"success": False, "error": str(e)}

    async def gaps_identify(
        actors: list[dict[str, Any]],
        reference_sectors: list[str] | None = None,
    ) -> dict[str, Any]:
        """Identify gaps and opportunities in the ecosystem.

        Compares current actors against reference sectors to find:
        - Missing sectors
        - Underrepresented activities
        - Value chain gaps

        Args:
            actors: List of actor data from the territory
            reference_sectors: Optional list of expected sectors for comparison

        Returns:
            Dict with identified gaps and opportunities
        """
        try:
            if not actors:
                return {"success": False, "error": "No actors provided"}

            # Default reference sectors for innovation ecosystem
            if not reference_sectors:
                reference_sectors = [
                    "Intelligence artificielle",
                    "Cybersécurité",
                    "Biotechnologie",
                    "Énergie renouvelable",
                    "Hydrogène",
                    "Mobilité durable",
                    "Économie circulaire",
                    "Industrie 4.0",
                    "Santé numérique",
                    "AgriTech",
                    "FinTech",
                    "EdTech",
                    "PropTech",
                    "CleanTech",
                    "DeepTech",
                ]

            # Analyze current sectors
            current_sectors = set()
            sector_details = defaultdict(list)

            for actor in actors:
                sector = actor.get("activite") or actor.get("libelle_activite") or ""
                if sector:
                    current_sectors.add(sector.lower()[:30])
                    sector_details[sector.lower()[:30]].append(actor.get("nom", "Unknown"))

            # Check for presence of reference sectors
            present = []
            missing = []
            weak = []  # Present but underrepresented

            for ref_sector in reference_sectors:
                ref_lower = ref_sector.lower()

                # Check if any current sector matches
                found = False
                matching_actors = []

                for curr_sector in current_sectors:
                    # Fuzzy match
                    if ref_lower in curr_sector or curr_sector in ref_lower or \
                       any(word in curr_sector for word in ref_lower.split()):
                        found = True
                        matching_actors.extend(sector_details.get(curr_sector, []))

                if found:
                    if len(matching_actors) < 3:
                        weak.append({
                            "sector": ref_sector,
                            "actors_count": len(matching_actors),
                            "actors": matching_actors[:5],
                            "recommendation": f"Renforcer {ref_sector}: seulement {len(matching_actors)} acteur(s)",
                        })
                    else:
                        present.append({
                            "sector": ref_sector,
                            "actors_count": len(matching_actors),
                        })
                else:
                    missing.append({
                        "sector": ref_sector,
                        "recommendation": f"Opportunité: développer {ref_sector} (absent du territoire)",
                    })

            # Identify value chain gaps (simplified)
            value_chain_roles = ["recherche", "incubateur", "startup", "entreprise", "investisseur"]
            present_roles = set()
            for actor in actors:
                actor_type = (actor.get("type") or "").lower()
                for role in value_chain_roles:
                    if role in actor_type:
                        present_roles.add(role)

            missing_roles = set(value_chain_roles) - present_roles

            return {
                "success": True,
                "total_actors": len(actors),
                "analysis": {
                    "present_sectors": present[:10],
                    "missing_sectors": missing[:10],
                    "weak_sectors": weak[:10],
                },
                "value_chain": {
                    "present_roles": list(present_roles),
                    "missing_roles": list(missing_roles),
                },
                "opportunities": [
                    *[m["recommendation"] for m in missing[:5]],
                    *[w["recommendation"] for w in weak[:5]],
                    *[f"Attirer des {role}s" for role in missing_roles],
                ][:10],
                "summary": {
                    "sectors_present": len(present),
                    "sectors_missing": len(missing),
                    "sectors_weak": len(weak),
                },
            }

        except Exception as e:
            logger.error(f"Gap identification failed: {e}")
            return {"success": False, "error": str(e)}

    async def network_export_graph(
        actors: list[dict[str, Any]],
        connections: list[dict[str, Any]] | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Export network as GEXF graph file for Gephi visualization.

        Args:
            actors: List of actors (nodes)
            connections: Optional pre-computed connections (from network_analyze)
            output_path: Where to save the GEXF file

        Returns:
            Dict with file path
        """
        try:
            import networkx as nx
        except ImportError:
            return {"success": False, "error": "networkx not installed. Run: pip install networkx"}

        try:
            G = nx.Graph()

            # Add nodes
            for i, actor in enumerate(actors):
                node_id = actor.get("siret") or actor.get("siren") or f"actor_{i}"
                G.add_node(
                    node_id,
                    nom=actor.get("nom", "Unknown"),
                    type=actor.get("type", "unknown"),
                    commune=actor.get("commune") or actor.get("adresse", {}).get("commune", ""),
                    activite=actor.get("activite") or actor.get("libelle_activite", ""),
                )

            # Add edges if connections provided
            if connections:
                for conn in connections:
                    # Find node IDs by name
                    from_id = None
                    to_id = None
                    for node_id, data in G.nodes(data=True):
                        if data.get("nom") == conn.get("from"):
                            from_id = node_id
                        if data.get("nom") == conn.get("to"):
                            to_id = node_id
                    if from_id and to_id:
                        G.add_edge(
                            from_id,
                            to_id,
                            weight=conn.get("strength", 1),
                            type=",".join(conn.get("reasons", [])),
                        )

            # Determine output path
            if not output_path:
                output_dir = Path("./outputs/networks")
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = str(output_dir / f"{timestamp}_network.gexf")

            # Save
            nx.write_gexf(G, output_path)
            abs_path = str(Path(output_path).absolute())

            return {
                "success": True,
                "file_path": abs_path,
                "nodes": G.number_of_nodes(),
                "edges": G.number_of_edges(),
            }

        except Exception as e:
            logger.error(f"Graph export failed: {e}")
            return {"success": False, "error": str(e)}

    # Register tools
    registry._tools["network.analyze"] = Tool(
        name="network.analyze",
        func=network_analyze,
        category=ToolCategory.STRATEGY,
        description="Analyze connections between actors. Returns clusters, central actors, network density.",
    )

    registry._tools["benchmark.compare"] = Tool(
        name="benchmark.compare",
        func=benchmark_compare,
        category=ToolCategory.STRATEGY,
        description="Compare two territories on multiple criteria. Returns differences and recommendations.",
    )

    registry._tools["trends.detect"] = Tool(
        name="trends.detect",
        func=trends_detect,
        category=ToolCategory.STRATEGY,
        description="Detect trends: growing sectors, hotspots, emerging activities.",
    )

    registry._tools["gaps.identify"] = Tool(
        name="gaps.identify",
        func=gaps_identify,
        category=ToolCategory.STRATEGY,
        description="Find missing sectors and opportunities compared to reference ecosystem.",
    )

    registry._tools["network.export_graph"] = Tool(
        name="network.export_graph",
        func=network_export_graph,
        category=ToolCategory.STRATEGY,
        description="Export actor network as GEXF file for Gephi visualization.",
    )

    logger.debug("Registered 5 strategy tools")
