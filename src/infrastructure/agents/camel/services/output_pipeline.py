"""Output pipeline for territorial intelligence analysis.

Generates multi-format outputs: CSV, JSONL, Markdown, HTML (graph/map).
"""

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from .enrichment_service import EnrichmentResult


@dataclass
class OutputConfig:
    """Configuration for output generation."""

    output_dir: str
    query: str
    formats: list[str] = None  # ['csv', 'jsonl', 'md', 'html', 'graph']
    include_enrichment: bool = True
    include_map: bool = True
    include_graph: bool = True

    def __post_init__(self):
        if self.formats is None:
            self.formats = ["csv", "jsonl", "md", "html"]


class OutputPipeline:
    """Pipeline for generating all output formats."""

    def __init__(self, config: OutputConfig):
        """Initialize the output pipeline.

        Args:
            config: Output configuration
        """
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.output_dir / "data").mkdir(exist_ok=True)
        (self.output_dir / "maps").mkdir(exist_ok=True)
        (self.output_dir / "reports").mkdir(exist_ok=True)

    def generate_csv(
        self,
        enterprises: list[dict[str, Any]],
        enrichments: list[EnrichmentResult] | None = None,
    ) -> str:
        """Generate CSV export of enterprises.

        Args:
            enterprises: List of enterprise data
            enrichments: Optional list of enrichment results

        Returns:
            Path to generated CSV file
        """
        csv_path = self.output_dir / "data" / "entreprises.csv"

        # Build enrichment lookup
        enrichment_map = {}
        if enrichments:
            for e in enrichments:
                enrichment_map[e.siret] = e

        # Define columns
        base_columns = [
            "siret",
            "nom",
            "activite",
            "naf_code",
            "effectif",
            "commune",
            "code_postal",
            "adresse",
            "lat",
            "lon",
            "date_creation",
            "forme_juridique",
        ]

        enriched_columns = [
            "website",
            "description",
            "services",
            "email",
            "phone",
            "linkedin",
            "twitter",
            "clients",
            "enrichment_quality",
        ]

        columns = base_columns + (enriched_columns if enrichments else [])

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()

            for ent in enterprises:
                row = {
                    "siret": ent.get("siret", ""),
                    "nom": ent.get("nom", ""),
                    "activite": ent.get("activite", ""),
                    "naf_code": ent.get("naf_code", ""),
                    "effectif": ent.get("effectif", ""),
                    "commune": ent.get("adresse", {}).get("commune", ""),
                    "code_postal": ent.get("adresse", {}).get("code_postal", ""),
                    "adresse": ent.get("adresse", {}).get("adresse", ""),
                    "lat": ent.get("geo", {}).get("lat", ""),
                    "lon": ent.get("geo", {}).get("lon", ""),
                    "date_creation": ent.get("date_creation", ""),
                    "forme_juridique": ent.get("forme_juridique", ""),
                }

                # Add enrichment data if available
                siret = ent.get("siret", "")
                if siret in enrichment_map:
                    enr = enrichment_map[siret]
                    row.update(
                        {
                            "website": enr.url_found or "",
                            "description": (enr.description or "")[:200],
                            "services": "; ".join(enr.services[:5]),
                            "email": enr.contact.get("email", ""),
                            "phone": enr.contact.get("phone", ""),
                            "linkedin": enr.social_media.get("linkedin", ""),
                            "twitter": enr.social_media.get("twitter", ""),
                            "clients": "; ".join(enr.clients_references[:5]),
                            "enrichment_quality": f"{enr.enrichment_quality:.2f}",
                        }
                    )

                writer.writerow(row)

        logger.info(f"Generated CSV: {csv_path}")
        return str(csv_path)

    def generate_jsonl(
        self,
        enterprises: list[dict[str, Any]],
        enrichments: list[EnrichmentResult] | None = None,
    ) -> str:
        """Generate JSONL for annotation and fine-tuning.

        Args:
            enterprises: List of enterprise data
            enrichments: Optional list of enrichment results

        Returns:
            Path to generated JSONL file
        """
        jsonl_path = self.output_dir / "data" / "dataset.jsonl"

        # Build enrichment lookup
        enrichment_map = {}
        if enrichments:
            for e in enrichments:
                enrichment_map[e.siret] = e

        with open(jsonl_path, "w", encoding="utf-8") as f:
            for ent in enterprises:
                siret = ent.get("siret", "")

                record = {
                    "id": siret,
                    "source": "sirene",
                    "timestamp": datetime.now().isoformat(),
                    "query": self.config.query,
                    "enterprise": {
                        "siret": siret,
                        "nom": ent.get("nom", ""),
                        "activite": ent.get("activite", ""),
                        "naf_code": ent.get("naf_code", ""),
                        "effectif": ent.get("effectif", ""),
                        "adresse": ent.get("adresse", {}),
                        "geo": ent.get("geo", {}),
                        "date_creation": ent.get("date_creation", ""),
                        "forme_juridique": ent.get("forme_juridique", ""),
                    },
                    "enrichment": None,
                    "annotations": {
                        "labels": [],
                        "notes": "",
                        "quality_score": None,
                        "reviewed": False,
                    },
                }

                # Add enrichment if available
                if siret in enrichment_map:
                    enr = enrichment_map[siret]
                    record["enrichment"] = enr.to_dict()

                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info(f"Generated JSONL: {jsonl_path}")
        return str(jsonl_path)

    def generate_markdown_report(
        self,
        enterprises: list[dict[str, Any]],
        enrichments: list[EnrichmentResult] | None = None,
        map_file: str | None = None,
        graph_file: str | None = None,
    ) -> str:
        """Generate comprehensive Markdown report.

        Args:
            enterprises: List of enterprise data
            enrichments: Optional list of enrichment results
            map_file: Optional path to map file
            graph_file: Optional path to graph file

        Returns:
            Path to generated Markdown file
        """
        md_path = self.output_dir / "reports" / "rapport.md"

        # Build enrichment lookup
        enrichment_map = {}
        if enrichments:
            for e in enrichments:
                enrichment_map[e.siret] = e

        # Calculate statistics
        total = len(enterprises)
        with_geo = sum(1 for e in enterprises if e.get("geo", {}).get("lat"))
        with_enrichment = len(enrichment_map)
        avg_quality = 0
        if enrichment_map:
            avg_quality = sum(e.enrichment_quality for e in enrichment_map.values()) / len(
                enrichment_map
            )

        # Group by city
        cities = {}
        for ent in enterprises:
            city = ent.get("adresse", {}).get("commune", "Inconnu")
            cities[city] = cities.get(city, 0) + 1

        # Sort cities by count
        top_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)[:10]

        # Generate report
        report = f"""# Analyse Territoriale : {self.config.query}

**Date de génération** : {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

## Résumé Exécutif

Cette analyse couvre **{total} entreprises** identifiées pour la requête "{self.config.query}".

### Chiffres Clés

| Métrique | Valeur |
|----------|--------|
| Entreprises identifiées | {total} |
| Avec géolocalisation | {with_geo} ({100 * with_geo // max(total, 1)}%) |
| Enrichies (web) | {with_enrichment} ({100 * with_enrichment // max(total, 1)}%) |
| Qualité enrichissement moyenne | {avg_quality:.0%} |

### Répartition Géographique

| Ville | Nombre |
|-------|--------|
"""
        for city, count in top_cities:
            report += f"| {city} | {count} |\n"

        report += """
---

## Top 10 Entreprises

"""
        for i, ent in enumerate(enterprises[:10], 1):
            nom = ent.get("nom", "N/A")
            commune = ent.get("adresse", {}).get("commune", "?")
            effectif = ent.get("effectif", "?")
            siret = ent.get("siret", "")

            report += f"### {i}. {nom}\n\n"
            report += f"- **SIRET** : {siret}\n"
            report += f"- **Localisation** : {commune}\n"
            report += f"- **Effectif** : {effectif}\n"

            if siret in enrichment_map:
                enr = enrichment_map[siret]
                if enr.url_found:
                    report += f"- **Site web** : [{enr.url_found}]({enr.url_found})\n"
                if enr.description:
                    report += f"- **Description** : {enr.description[:200]}...\n"
                if enr.services:
                    report += f"- **Services** : {', '.join(enr.services[:3])}\n"
                if enr.social_media:
                    for platform, url in enr.social_media.items():
                        report += f"- **{platform.title()}** : [{url}]({url})\n"

            report += "\n"

        # Add visualizations section
        report += """---

## Visualisations

"""
        if map_file:
            report += f"### Carte Interactive\n\n[Ouvrir la carte]({map_file})\n\n"

        if graph_file:
            report += f"### Graphe de Relations\n\n[Ouvrir le graphe]({graph_file})\n\n"

        # Add data files section
        report += """---

## Fichiers de Données

| Fichier | Description |
|---------|-------------|
| `data/entreprises.csv` | Données tabulaires complètes |
| `data/dataset.jsonl` | Format annotation/fine-tuning |
"""
        if map_file:
            report += "| `maps/carte.html` | Carte interactive Folium |\n"
        if graph_file:
            report += "| `maps/graphe.html` | Graphe de relations |\n"

        report += """
---

## Méthodologie

1. **Collecte** : Données issues de l'API Sirene (INSEE)
2. **Géolocalisation** : API Adresse data.gouv.fr
3. **Enrichissement** : Crawling des sites web identifiés
4. **Analyse** : Agrégation et synthèse automatisée

---

*Rapport généré automatiquement par Tawiza - Intelligence Territoriale*
"""

        md_path.write_text(report, encoding="utf-8")
        logger.info(f"Generated Markdown report: {md_path}")
        return str(md_path)

    def generate_relation_graph(
        self,
        enterprises: list[dict[str, Any]],
        enrichments: list[EnrichmentResult] | None = None,
    ) -> str:
        """Generate interactive HTML graph of relations.

        Args:
            enterprises: List of enterprise data
            enrichments: Optional list of enrichment results

        Returns:
            Path to generated HTML file
        """
        graph_path = self.output_dir / "maps" / "graphe.html"

        # Build enrichment lookup
        enrichment_map = {}
        if enrichments:
            for e in enrichments:
                enrichment_map[e.siret] = e

        # Build nodes and edges
        nodes = []
        edges = []
        node_ids = set()

        # Add enterprise nodes
        for i, ent in enumerate(enterprises[:50]):  # Limit to 50 for performance
            siret = ent.get("siret", f"ent_{i}")
            nom = ent.get("nom", "N/A")
            city = ent.get("adresse", {}).get("commune", "")

            nodes.append(
                {
                    "id": siret,
                    "label": nom[:30],
                    "title": f"{nom}\n{city}",
                    "group": "enterprise",
                    "size": 20,
                }
            )
            node_ids.add(siret)

            # Add city node and edge
            if city and city not in node_ids:
                nodes.append(
                    {
                        "id": city,
                        "label": city,
                        "group": "city",
                        "size": 30,
                        "shape": "box",
                    }
                )
                node_ids.add(city)

            if city:
                edges.append(
                    {
                        "from": siret,
                        "to": city,
                        "label": "situé à",
                        "color": "#cccccc",
                    }
                )

            # Add client relations from enrichment
            if siret in enrichment_map:
                enr = enrichment_map[siret]
                for client in enr.clients_references[:3]:
                    client_id = f"client_{client}"
                    if client_id not in node_ids:
                        nodes.append(
                            {
                                "id": client_id,
                                "label": client[:20],
                                "group": "client",
                                "size": 15,
                                "shape": "diamond",
                            }
                        )
                        node_ids.add(client_id)

                    edges.append(
                        {
                            "from": siret,
                            "to": client_id,
                            "label": "client",
                            "color": "#4CAF50",
                        }
                    )

        # Generate HTML with vis.js
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Graphe de Relations - {self.config.query}</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        #header {{
            background: #1a1a2e;
            color: white;
            padding: 15px 20px;
        }}
        #header h1 {{
            margin: 0;
            font-size: 1.5em;
        }}
        #header p {{
            margin: 5px 0 0 0;
            opacity: 0.7;
            font-size: 0.9em;
        }}
        #graph {{
            width: 100%;
            height: calc(100vh - 80px);
        }}
        #legend {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 10px 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}
        .legend-color {{
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Graphe de Relations</h1>
        <p>{self.config.query} - {len(enterprises)} entreprises</p>
    </div>
    <div id="graph"></div>
    <div id="legend">
        <div class="legend-item">
            <div class="legend-color" style="background: #6C5CE7;"></div>
            <span>Entreprise</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #00CEC9; border-radius: 3px;"></div>
            <span>Ville</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #4CAF50; transform: rotate(45deg);"></div>
            <span>Client</span>
        </div>
    </div>
    <script>
        var nodes = new vis.DataSet({json.dumps(nodes)});
        var edges = new vis.DataSet({json.dumps(edges)});

        var container = document.getElementById('graph');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            groups: {{
                enterprise: {{ color: {{ background: '#6C5CE7', border: '#5B4CC4' }} }},
                city: {{ color: {{ background: '#00CEC9', border: '#00B5AD' }} }},
                client: {{ color: {{ background: '#4CAF50', border: '#388E3C' }} }},
            }},
            nodes: {{
                font: {{ size: 12 }},
                borderWidth: 2,
            }},
            edges: {{
                font: {{ size: 10, align: 'middle' }},
                arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }},
                smooth: {{ type: 'continuous' }},
            }},
            physics: {{
                stabilization: {{ iterations: 100 }},
                barnesHut: {{
                    gravitationalConstant: -2000,
                    springLength: 150,
                }},
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100,
            }},
        }};

        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>
"""
        graph_path.write_text(html, encoding="utf-8")
        logger.info(f"Generated relation graph: {graph_path}")
        return str(graph_path)

    async def generate_all(
        self,
        enterprises: list[dict[str, Any]],
        enrichments: list[EnrichmentResult] | None = None,
        map_file: str | None = None,
    ) -> dict[str, str]:
        """Generate all output formats.

        Args:
            enterprises: List of enterprise data
            enrichments: Optional list of enrichment results
            map_file: Optional existing map file path

        Returns:
            Dictionary mapping format to file path
        """
        outputs = {}

        if "csv" in self.config.formats:
            outputs["csv"] = self.generate_csv(enterprises, enrichments)

        if "jsonl" in self.config.formats:
            outputs["jsonl"] = self.generate_jsonl(enterprises, enrichments)

        graph_file = None
        if self.config.include_graph and "html" in self.config.formats:
            graph_file = self.generate_relation_graph(enterprises, enrichments)
            outputs["graph"] = graph_file

        if "md" in self.config.formats:
            outputs["md"] = self.generate_markdown_report(
                enterprises, enrichments, map_file, graph_file
            )

        return outputs


async def generate_all_outputs(
    enterprises: list[dict[str, Any]],
    query: str,
    output_dir: str,
    enrichments: list[EnrichmentResult] | None = None,
    map_file: str | None = None,
    formats: list[str] | None = None,
) -> dict[str, str]:
    """Convenience function to generate all outputs.

    Args:
        enterprises: List of enterprise data
        query: Original search query
        output_dir: Output directory
        enrichments: Optional enrichment results
        map_file: Optional existing map file
        formats: List of formats to generate

    Returns:
        Dictionary mapping format to file path
    """
    config = OutputConfig(
        output_dir=output_dir,
        query=query,
        formats=formats or ["csv", "jsonl", "md", "html"],
    )
    pipeline = OutputPipeline(config)
    return await pipeline.generate_all(enterprises, enrichments, map_file)
