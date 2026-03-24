"""MCP Tools for Multi-Territory Comparison.

Enables parallel market analysis across multiple territories with
LLM-powered comparative analysis and visualizations.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger
from mcp.server.fastmcp import Context, FastMCP


@dataclass
class TerritoryAnalysis:
    """Results from analyzing a single territory."""

    territory: str
    query: str
    enterprises_count: int
    top_sectors: dict = field(default_factory=dict)
    effectif_distribution: dict = field(default_factory=dict)
    top_communes: list = field(default_factory=list)
    top_enterprises: list = field(default_factory=list)
    geocoded_count: int = 0
    avg_effectif: float = 0
    creation_recent: int = 0  # Created in last 2 years
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "territory": self.territory,
            "query": self.query,
            "enterprises_count": self.enterprises_count,
            "top_sectors": self.top_sectors,
            "effectif_distribution": self.effectif_distribution,
            "top_communes": self.top_communes,
            "top_enterprises": self.top_enterprises,
            "geocoded_count": self.geocoded_count,
            "avg_effectif": self.avg_effectif,
            "creation_recent": self.creation_recent,
            "error": self.error,
        }


@dataclass
class ComparisonResult:
    """Results from comparing multiple territories."""

    query_base: str
    territories: list[str]
    analyses: list[TerritoryAnalysis]
    comparison_md: str
    winner: str | None = None
    recommendations: list[str] = field(default_factory=list)
    charts_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "query_base": self.query_base,
            "territories": self.territories,
            "analyses": [a.to_dict() for a in self.analyses],
            "comparison_md": self.comparison_md,
            "winner": self.winner,
            "recommendations": self.recommendations,
            "charts_data": self.charts_data,
        }


COMPARATOR_PROMPT = """Tu es un analyste expert en intelligence territoriale. Compare ces {n} marchés territoriaux et détermine lequel est le plus attractif.

**Requête de base**: {query}

**Données par territoire**:
{territories_data}

**Analyse et réponds en JSON**:
{{
    "winner": "<territoire le plus attractif>",
    "winner_reason": "<justification en 2 phrases>",
    "ranking": ["<1er>", "<2e>", "<3e>", ...],
    "strengths": {{
        "<territoire1>": ["force1", "force2"],
        "<territoire2>": ["force1", "force2"]
    }},
    "weaknesses": {{
        "<territoire1>": ["faiblesse1"],
        "<territoire2>": ["faiblesse1"]
    }},
    "recommendations": [
        "<recommandation1>",
        "<recommandation2>",
        "<recommandation3>"
    ],
    "analysis_summary": "<resume de la comparaison en 3 phrases>"
}}

Criteres de comparaison:
1. Nombre d'entreprises (densite du marche)
2. Taille moyenne (maturite)
3. Dynamisme (creations recentes)
4. Concentration geographique
5. Diversite sectorielle
"""


def register_comparison_tools(mcp: FastMCP) -> None:
    """Register comparison tools on the MCP server."""

    @mcp.tool()
    async def tawiza_compare_markets(
        query: str,
        territories: list[str],
        limit_per_territory: int = 30,
        ctx: Context = None,
    ) -> str:
        """Compare un marche sur plusieurs territoires en parallele.

        Lance des analyses simultanées sur N territoires et produit
        un rapport comparatif avec recommandations.

        Args:
            query: Requête de base sans territoire (ex: "startup IA", "conseil IT")
            territories: Liste des territoires à comparer (ex: ["Lille", "Lyon", "Nantes"])
            limit_per_territory: Nombre max d'entreprises par territoire

        Returns:
            JSON avec:
            - comparison_md: Rapport comparatif Markdown
            - analyses: Données par territoire
            - winner: Territoire recommandé
            - charts_data: Données pour graphiques
        """
        from src.application.orchestration.data_orchestrator import DataOrchestrator
        from src.infrastructure.agents.camel.tools.territorial_tools import sirene_search

        def notify(msg: str, progress: int = None):
            if ctx:
                try:
                    ctx.info(msg)
                    if progress is not None:
                        ctx.report_progress(progress, 100, msg)
                except Exception as e:
                    logger.debug(f"Failed to send notification: {e}")
                    pass

        if len(territories) < 2:
            return json.dumps(
                {
                    "success": False,
                    "error": "Au moins 2 territoires requis pour comparaison",
                },
                ensure_ascii=False,
            )

        if len(territories) > 5:
            territories = territories[:5]
            notify("Limite a 5 territoires maximum")

        notify(f"Comparaison: {query} sur {len(territories)} territoires", 0)
        start_time = datetime.now()

        # Analyze territories in parallel
        async def analyze_territory(territory: str) -> TerritoryAnalysis:
            """Analyze a single territory."""
            full_query = f"{query} {territory}"
            notify(f"[{territory}] Analyse en cours...")

            try:
                # Try direct Sirene search first
                result = sirene_search(query=full_query, limite=limit_per_territory)

                enterprises = []
                if result.get("success") and result.get("enterprises"):
                    enterprises = result["enterprises"]
                else:
                    # Fallback to orchestrator
                    orchestrator = DataOrchestrator()
                    orch_result = await orchestrator.search(
                        query=full_query,
                        limit_per_source=limit_per_territory,
                        sources=["sirene"],
                    )
                    for sr in orch_result.source_results:
                        enterprises.extend(sr.results)

                if not enterprises:
                    return TerritoryAnalysis(
                        territory=territory,
                        query=full_query,
                        enterprises_count=0,
                        error="Aucune entreprise trouvee",
                    )

                # Calculate statistics
                effectif_dist = {"<10": 0, "10-50": 0, "50-250": 0, ">250": 0}
                sectors = {}
                communes = {}
                total_effectif = 0
                creation_recent = 0
                current_year = datetime.now().year

                for ent in enterprises:
                    # Effectif distribution
                    effectif = ent.get("effectif", ent.get("trancheEffectifs", 0))
                    try:
                        eff_val = (
                            int(str(effectif).split("-")[0].replace("+", "")) if effectif else 0
                        )
                    except (ValueError, TypeError):
                        eff_val = 0

                    total_effectif += eff_val
                    if eff_val < 10:
                        effectif_dist["<10"] += 1
                    elif eff_val < 50:
                        effectif_dist["10-50"] += 1
                    elif eff_val < 250:
                        effectif_dist["50-250"] += 1
                    else:
                        effectif_dist[">250"] += 1

                    # Sectors
                    sector = ent.get("activite", ent.get("naf", "Inconnu"))
                    if sector:
                        sectors[sector] = sectors.get(sector, 0) + 1

                    # Communes
                    commune = ent.get("commune", ent.get("city", "Inconnu"))
                    if commune:
                        communes[commune] = communes.get(commune, 0) + 1

                    # Recent creations
                    creation = ent.get("dateCreation", "")
                    if creation:
                        try:
                            year = int(str(creation)[:4])
                            if current_year - year <= 2:
                                creation_recent += 1
                        except (ValueError, TypeError):
                            pass

                # Top items
                top_sectors = dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:5])
                top_communes = sorted(communes.items(), key=lambda x: x[1], reverse=True)[:5]
                top_enterprises = [
                    {
                        "nom": e.get("nom") or e.get("name", "N/A"),
                        "siret": e.get("siret", ""),
                        "effectif": e.get("effectif", "N/A"),
                    }
                    for e in enterprises[:5]
                ]

                avg_effectif = total_effectif / len(enterprises) if enterprises else 0

                notify(f"[{territory}] {len(enterprises)} entreprises")

                return TerritoryAnalysis(
                    territory=territory,
                    query=full_query,
                    enterprises_count=len(enterprises),
                    top_sectors=top_sectors,
                    effectif_distribution=effectif_dist,
                    top_communes=top_communes,
                    top_enterprises=top_enterprises,
                    avg_effectif=round(avg_effectif, 1),
                    creation_recent=creation_recent,
                )

            except Exception as e:
                logger.error(f"Error analyzing {territory}: {e}")
                return TerritoryAnalysis(
                    territory=territory,
                    query=full_query,
                    enterprises_count=0,
                    error=str(e),
                )

        # Run parallel analyses
        notify(f"Lancement de {len(territories)} analyses paralleles...", 10)

        tasks = [analyze_territory(t) for t in territories]
        analyses = await asyncio.gather(*tasks)

        notify("Analyses terminees, comparaison LLM...", 60)

        # Filter successful analyses
        valid_analyses = [a for a in analyses if not a.error]

        if len(valid_analyses) < 2:
            return json.dumps(
                {
                    "success": False,
                    "error": "Pas assez de territoires avec resultats",
                    "analyses": [a.to_dict() for a in analyses],
                },
                ensure_ascii=False,
                indent=2,
            )

        # LLM Comparison
        territories_data = ""
        for a in valid_analyses:
            territories_data += f"""
**{a.territory}**:
- Entreprises: {a.enterprises_count}
- Effectif moyen: {a.avg_effectif}
- Creations recentes (2 ans): {a.creation_recent}
- Distribution: <10={a.effectif_distribution.get("<10", 0)}, 10-50={a.effectif_distribution.get("10-50", 0)}, 50-250={a.effectif_distribution.get("50-250", 0)}, >250={a.effectif_distribution.get(">250", 0)}
- Top secteurs: {", ".join(list(a.top_sectors.keys())[:3])}
"""

        try:
            from src.infrastructure.llm import OllamaClient

            client = OllamaClient(model="qwen3.5:27b")

            prompt = COMPARATOR_PROMPT.format(
                n=len(valid_analyses),
                query=query,
                territories_data=territories_data,
            )

            response = await client.generate(prompt=prompt, max_tokens=800)

            # Parse JSON from response
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            comparison_data = json.loads(json_str.strip())
            winner = comparison_data.get("winner")
            recommendations = comparison_data.get("recommendations", [])
            analysis_summary = comparison_data.get("analysis_summary", "")

            notify(f"[LLM] Recommandation: {winner}", 80)

        except Exception as e:
            logger.warning(f"LLM comparison failed: {e}")
            # Fallback: pick winner by enterprise count
            winner = max(valid_analyses, key=lambda x: x.enterprises_count).territory
            recommendations = [
                f"Explorer {winner} en priorité (plus grand marché)",
                "Approfondir l'analyse des secteurs clés",
                "Valider avec des contacts terrain",
            ]
            analysis_summary = f"Comparaison basée sur les données quantitatives. {winner} présente le marché le plus dense."
            comparison_data = {}

        # Generate comparison markdown
        notify("Génération du rapport comparatif...", 85)

        comparison_md = f"""# Comparaison Multi-Territoires

## Requête: {query}

*Analyse comparative de {len(territories)} territoires*
*Générée le {datetime.now().strftime("%d/%m/%Y à %H:%M")}*

## Resume Executif

{analysis_summary}

**Territoire recommande**: **{winner}**

## Tableau Comparatif

| Territoire | Entreprises | Effectif Moy. | Creations 2 ans | Score |
|------------|-------------|---------------|-----------------|-------|
"""
        max_count = max(a.enterprises_count for a in valid_analyses) or 1
        for a in sorted(valid_analyses, key=lambda x: x.enterprises_count, reverse=True):
            score = int((a.enterprises_count / max_count) * 100)
            comparison_md += f"| **{a.territory}** | {a.enterprises_count} | {a.avg_effectif} | {a.creation_recent} | {score}/100 |\n"

        comparison_md += "\n## Detail par Territoire\n"

        for a in valid_analyses:
            comparison_md += f"""
### {a.territory}

**Chiffres cles:**
- Entreprises trouvees: **{a.enterprises_count}**
- Effectif moyen: **{a.avg_effectif}**
- Creations recentes: **{a.creation_recent}**

**Distribution par taille:**
| Taille | Nombre |
|--------|--------|
| TPE (<10) | {a.effectif_distribution.get("<10", 0)} |
| PME (10-50) | {a.effectif_distribution.get("10-50", 0)} |
| ETI (50-250) | {a.effectif_distribution.get("50-250", 0)} |
| GE (>250) | {a.effectif_distribution.get(">250", 0)} |

**Top 5 entreprises:**
"""
            for i, ent in enumerate(a.top_enterprises[:5], 1):
                comparison_md += f"{i}. {ent['nom']} (effectif: {ent['effectif']})\n"

        comparison_md += """
## Recommandations

"""
        for i, rec in enumerate(recommendations[:5], 1):
            comparison_md += f"{i}. {rec}\n"

        comparison_md += """
---
*Comparaison generee par Tawiza Multi-Territoires*
"""

        # Build charts data for visualization
        charts_data = {
            "enterprises_by_territory": {a.territory: a.enterprises_count for a in valid_analyses},
            "avg_effectif_by_territory": {a.territory: a.avg_effectif for a in valid_analyses},
            "creation_recent_by_territory": {
                a.territory: a.creation_recent for a in valid_analyses
            },
            "size_distribution": {a.territory: a.effectif_distribution for a in valid_analyses},
        }

        # Build result
        duration = (datetime.now() - start_time).total_seconds()
        notify(f"Comparaison terminee ({duration:.1f}s)", 100)

        result = ComparisonResult(
            query_base=query,
            territories=territories,
            analyses=valid_analyses,
            comparison_md=comparison_md,
            winner=winner,
            recommendations=recommendations,
            charts_data=charts_data,
        )

        return json.dumps(
            {
                "success": True,
                **result.to_dict(),
                "duration_seconds": duration,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    @mcp.tool()
    async def tawiza_territory_benchmark(
        territory: str,
        sectors: list[str] | None = None,
        ctx: Context = None,
    ) -> str:
        """Benchmark complet d'un territoire sur plusieurs secteurs.

        Analyse un territoire en profondeur sur plusieurs secteurs
        d'activite pour identifier les opportunites.

        Args:
            territory: Territoire a analyser (ex: "Lille", "Lyon")
            sectors: Secteurs a analyser (defaut: tech, conseil, industrie, sante, commerce)

        Returns:
            Benchmark du territoire avec forces/faiblesses par secteur
        """
        from src.infrastructure.agents.camel.tools.territorial_tools import sirene_search

        def notify(msg: str, progress: int = None):
            if ctx:
                try:
                    ctx.info(msg)
                    if progress is not None:
                        ctx.report_progress(progress, 100, msg)
                except Exception as e:
                    logger.debug(f"Failed to send notification: {e}")
                    pass

        default_sectors = ["startup tech", "conseil IT", "industrie", "sante", "commerce"]
        sectors = sectors or default_sectors

        notify(f"Benchmark {territory} sur {len(sectors)} secteurs", 0)

        results = {}
        for i, sector in enumerate(sectors):
            progress = int((i / len(sectors)) * 80)
            notify(f"[{territory}] Secteur: {sector}", progress)

            try:
                result = sirene_search(query=f"{sector} {territory}", limite=30)
                count = len(result.get("enterprises", [])) if result.get("success") else 0
                results[sector] = {
                    "count": count,
                    "top_3": [e.get("nom", "N/A") for e in result.get("enterprises", [])[:3]]
                    if result.get("enterprises")
                    else [],
                }
            except Exception as e:
                results[sector] = {"count": 0, "error": str(e)}

        # Generate benchmark markdown
        total = sum(r["count"] for r in results.values())
        best_sector = max(results.items(), key=lambda x: x[1].get("count", 0))

        benchmark_md = f"""# Benchmark Territorial: {territory}

## Resume
- **Entreprises totales**: {total}
- **Secteur dominant**: {best_sector[0]} ({best_sector[1].get("count", 0)} entreprises)

## Par Secteur

| Secteur | Entreprises | Top 3 |
|---------|-------------|-------|
"""
        for sector, data in sorted(
            results.items(), key=lambda x: x[1].get("count", 0), reverse=True
        ):
            top3 = ", ".join(data.get("top_3", [])[:3]) or "N/A"
            benchmark_md += f"| {sector} | {data.get('count', 0)} | {top3[:50]}... |\n"

        benchmark_md += f"""
## Opportunites
- Secteur fort: **{best_sector[0]}** - marche etabli, concurrence
- Secteurs emergents: identifier les gaps dans les secteurs a faible densite

---
*Benchmark généré par Tawiza*
"""

        notify(f"Benchmark termine: {total} entreprises", 100)

        return json.dumps(
            {
                "success": True,
                "territory": territory,
                "sectors_analyzed": len(sectors),
                "total_enterprises": total,
                "best_sector": best_sector[0],
                "results": results,
                "benchmark_md": benchmark_md,
            },
            ensure_ascii=False,
            indent=2,
        )
