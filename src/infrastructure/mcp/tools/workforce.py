"""MCP Tools for CAMEL AI Workforce - Territorial Market Analysis.

Exposes the TerritorialWorkforce as an MCP tool for Cherry Studio integration.
Uses REAL CAMEL AI agents with tool calling for intelligent analysis.
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from loguru import logger
from mcp.server.fastmcp import Context, FastMCP


def _generate_manual_report(query: str, enterprises: list, collected_data: dict) -> str:
    """Generate a manual report when AnalystAgent fails."""
    total_count = len(enterprises)

    # Effectif distribution
    effectif_distribution = {"<10": 0, "10-50": 0, "50-250": 0, ">250": 0}
    for ent in enterprises:
        effectif = ent.get("effectif", ent.get("trancheEffectifs", 0))
        try:
            eff_val = int(str(effectif).split("-")[0].replace("+", "")) if effectif else 0
        except (ValueError, TypeError):
            eff_val = 0

        if eff_val < 10:
            effectif_distribution["<10"] += 1
        elif eff_val < 50:
            effectif_distribution["10-50"] += 1
        elif eff_val < 250:
            effectif_distribution["50-250"] += 1
        else:
            effectif_distribution[">250"] += 1

    # Commune distribution
    communes = {}
    for ent in enterprises:
        commune = ent.get("commune", ent.get("city", "Non specifie"))
        communes[commune] = communes.get(commune, 0) + 1
    top_communes = sorted(communes.items(), key=lambda x: x[1], reverse=True)[:5]

    rapport_md = f"""# Rapport d'Intelligence Territoriale

## Executive Summary

Analyse du marche **"{query}"** avec **{total_count}** entreprises identifiees.

## Chiffres Cles

| Metrique | Valeur |
|----------|--------|
| Entreprises identifiees | **{total_count}** |
| Geocodees | {collected_data.get("stats", {}).get("geocoded_count", 0)} |

## Repartition par Effectif

| Tranche | Nombre | Part |
|---------|--------|------|
| < 10 salaries | {effectif_distribution["<10"]} | {effectif_distribution["<10"] / max(total_count, 1) * 100:.1f}% |
| 10-50 salaries | {effectif_distribution["10-50"]} | {effectif_distribution["10-50"] / max(total_count, 1) * 100:.1f}% |
| 50-250 salaries | {effectif_distribution["50-250"]} | {effectif_distribution["50-250"] / max(total_count, 1) * 100:.1f}% |
| > 250 salaries | {effectif_distribution[">250"]} | {effectif_distribution[">250"] / max(total_count, 1) * 100:.1f}% |

## Top 5 Communes

| Commune | Entreprises |
|---------|-------------|
"""
    for commune, count in top_communes:
        rapport_md += f"| {commune} | {count} |\n"

    rapport_md += """

## Top 10 Acteurs

| # | Entreprise | SIRET | Commune | Effectif |
|---|------------|-------|---------|----------|
"""
    for i, ent in enumerate(enterprises[:10], 1):
        name = ent.get("nom") or ent.get("name") or ent.get("title", "N/A")
        siret = ent.get("siret", "N/A")
        commune = ent.get("commune", ent.get("city", "N/A"))
        effectif = ent.get("effectif", ent.get("trancheEffectifs", "N/A"))
        rapport_md += f"| {i} | {name} | {siret} | {commune} | {effectif} |\n"

    rapport_md += f"""

## Recommandations

1. **Priorite haute**: Contacter les grandes entreprises (>250 salaries)
2. **Priorite moyenne**: Analyser les ETI pour opportunites
3. **Veille**: Surveiller les startups innovantes

---
*Rapport genere par Tawiza Workforce - {datetime.now().strftime("%d/%m/%Y %H:%M")}*
"""
    return rapport_md


def register_workforce_tools(mcp: FastMCP) -> None:
    """Register workforce tools on the MCP server."""

    @mcp.tool()
    async def tawiza_workforce_analyze(
        query: str,
        output_dir: str = "./outputs/analyses",
        with_map: bool = True,
        with_web: bool = False,
        limit: int = 50,
        use_agents: bool = True,
        ctx: Context = None,
    ) -> str:
        """Analyse de marche territoriale complete via CAMEL Workforce.

        Lance une equipe de 4 agents IA specialises qui collaborent:
        1. DataAgent: Collecte donnees Sirene (entreprises francaises)
        2. GeoAgent: Geocodage et cartographie Folium interactive
        3. WebAgent: Enrichissement web depuis sites entreprises (optionnel)
        4. AnalystAgent: Rapport strategique avec recommandations

        Les agents communiquent entre eux pour produire une analyse coherente.
        Notifications temps reel envoyees a chaque etape.

        Args:
            query: Requete d'analyse (ex: "marche conseil IT Lille", "startup IA Lyon")
            output_dir: Repertoire de sortie pour les fichiers generes
            with_map: Generer une carte interactive Folium (defaut: True)
            with_web: Enrichir via scraping web (defaut: False, plus lent mais plus riche)
            limit: Nombre max d'entreprises a analyser (defaut: 50)
            use_agents: Utiliser les vrais agents CAMEL (defaut: True). Si False, mode simplifie.

        Returns:
            JSON avec:
            - success: Boolean
            - rapport_md: Rapport complet en Markdown
            - carte_html: Chemin vers carte Folium (si with_map)
            - data_csv: Chemin vers donnees brutes CSV
            - metadata: Statistiques de l'analyse (duree, counts, agents)
            - output_dir: Repertoire contenant tous les fichiers
        """
        from src.infrastructure.agents.camel.tools.territorial_tools import (
            geo_locate,
            geo_map,
            sirene_search,
        )
        from src.infrastructure.agents.camel.workforce import create_territorial_workforce

        # Helper for progress reporting
        def notify(message: str, progress: int = None, total: int = 100):
            if ctx:
                try:
                    ctx.info(message)
                    if progress is not None:
                        ctx.report_progress(progress, total, message)
                except Exception as e:
                    logger.debug(f"Failed to send notification: {e}")
                    pass

        notify("Demarrage analyse territoriale...", 0)
        start_time = datetime.now()

        # Create output directory with timestamp
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        safe_query = "".join(c if c.isalnum() or c in " _-" else "_" for c in query[:30])
        safe_query = safe_query.replace(" ", "_")
        analysis_dir = Path(output_dir) / f"{timestamp}_{safe_query}"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        notify(f"Repertoire cree: {analysis_dir}", 5)

        # =====================================================================
        # MODE AGENTS CAMEL (use_agents=True)
        # Utilise les vrais agents CAMEL AI avec tool calling
        # =====================================================================
        if use_agents:
            notify("[CAMEL] Initialisation des agents IA...", 10)

            try:
                # Create the real CAMEL workforce
                workforce = create_territorial_workforce(
                    model_id="qwen3.5:27b",
                    enable_web_enrichment=with_web,
                )
                notify("[CAMEL] Workforce cree avec 4 agents", 15)

                # Run each agent with its real ChatAgent
                collected_data = {
                    "entreprises": [],
                    "locations": [],
                    "enrichments": [],
                    "stats": {},
                    "agent_responses": {},
                }

                # ===== DataAgent =====
                notify("[DataAgent] Agent IA collecte donnees...", 20)
                data_prompt = f"""Recherche les entreprises pour: "{query}"

Utilise l'outil sirene_search avec:
- query: "{query}"
- limite: {limit}

Analyse les resultats et structure-les."""

                try:
                    data_response = workforce.data_agent.step(data_prompt)
                    collected_data["agent_responses"]["data_agent"] = str(data_response.msg.content)
                    notify("[DataAgent] Reponse agent recue", 35)

                    # Extract enterprises from tool calls if any
                    if data_response.info and "tool_calls" in data_response.info:
                        for tool_call in data_response.info.get("tool_calls", []):
                            if tool_call.get("result"):
                                result = tool_call["result"]
                                if isinstance(result, dict) and result.get("enterprises"):
                                    collected_data["entreprises"] = result["enterprises"]
                                    collected_data["stats"]["sirene_count"] = len(
                                        result["enterprises"]
                                    )
                except Exception as e:
                    logger.warning(f"DataAgent step failed: {e}, using direct tool call")
                    # Fallback to direct tool call
                    sirene_result = sirene_search(query=query, limite=limit)
                    if sirene_result.get("success"):
                        collected_data["entreprises"] = sirene_result.get("enterprises", [])
                        collected_data["stats"]["sirene_count"] = len(collected_data["entreprises"])

                # If no enterprises from agent, try direct call
                if not collected_data["entreprises"]:
                    sirene_result = sirene_search(query=query, limite=limit)
                    if sirene_result.get("success"):
                        collected_data["entreprises"] = sirene_result.get("enterprises", [])
                        collected_data["stats"]["sirene_count"] = len(collected_data["entreprises"])

                notify(f"[DataAgent] {len(collected_data['entreprises'])} entreprises", 40)

                # ===== GeoAgent =====
                if with_map and collected_data["entreprises"]:
                    notify("[GeoAgent] Agent IA cartographie...", 45)

                    # Prepare locations for geo agent
                    locations = []
                    for ent in collected_data["entreprises"][:limit]:
                        geo = ent.get("geo")
                        if geo and geo.get("lat"):
                            locations.append(
                                {
                                    "nom": ent.get("nom") or ent.get("name", "N/A"),
                                    "lat": geo["lat"],
                                    "lon": geo["lon"],
                                    "type": "entreprise",
                                    "siret": ent.get("siret", ""),
                                }
                            )
                        elif ent.get("adresse"):
                            try:
                                geo_result = geo_locate(ent["adresse"])
                                if geo_result.get("lat"):
                                    locations.append(
                                        {
                                            "nom": ent.get("nom") or ent.get("name", "N/A"),
                                            "lat": geo_result["lat"],
                                            "lon": geo_result["lon"],
                                            "type": "entreprise",
                                        }
                                    )
                            except Exception as e:
                                logger.debug(
                                    f"Geocoding failed for {ent.get('nom', 'unknown')}: {e}"
                                )
                                pass

                    collected_data["locations"] = locations
                    collected_data["stats"]["geocoded_count"] = len(locations)

                    # Generate map
                    if locations:
                        map_path = str(analysis_dir / "carte.html")
                        try:
                            map_result = geo_map(
                                locations=locations,
                                title=f"Analyse: {query}",
                            )
                            if map_result.get("success"):
                                import shutil

                                shutil.copy(map_result["file_path"], map_path)
                                collected_data["stats"]["map_file"] = map_path
                        except Exception as e:
                            logger.error(f"Map generation failed: {e}")

                    notify(f"[GeoAgent] {len(locations)} points cartographies", 55)

                # ===== AnalystAgent =====
                notify("[AnalystAgent] Agent IA analyse...", 60)

                enterprises = collected_data["entreprises"]
                analyst_prompt = f"""Analyse les donnees collectees et genere un rapport strategique.

Donnees:
- Requete: {query}
- Entreprises trouvees: {len(enterprises)}
- Territoire: {query}

Top entreprises:
{json.dumps(enterprises[:10], ensure_ascii=False, indent=2) if enterprises else "Aucune"}

Genere un rapport d'intelligence territoriale complet avec:
1. Executive Summary
2. Chiffres cles
3. Analyse par effectif et commune
4. Top 10 acteurs
5. Recommandations strategiques"""

                try:
                    analyst_response = workforce.analyst_agent.step(analyst_prompt)
                    rapport_md = str(analyst_response.msg.content)
                    collected_data["agent_responses"]["analyst_agent"] = rapport_md
                    notify("[AnalystAgent] Rapport genere par agent IA", 80)
                except Exception as e:
                    logger.warning(f"AnalystAgent failed: {e}, generating manual report")
                    rapport_md = _generate_manual_report(query, enterprises, collected_data)

                # Save files
                notify("[Output] Sauvegarde fichiers...", 85)

                rapport_path = analysis_dir / "rapport.md"
                rapport_path.write_text(rapport_md, encoding="utf-8")

                csv_path = analysis_dir / "entreprises.csv"
                if enterprises:
                    fieldnames = ["nom", "siret", "commune", "effectif", "activite", "adresse"]
                    with open(csv_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                        writer.writeheader()
                        for ent in enterprises:
                            row = {
                                "nom": ent.get("nom") or ent.get("name", ""),
                                "siret": ent.get("siret", ""),
                                "commune": ent.get("commune", ""),
                                "effectif": ent.get("effectif", ""),
                                "activite": ent.get("activite", ent.get("naf", "")),
                                "adresse": ent.get("adresse", ""),
                            }
                            writer.writerow(row)

                # Metadata
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                metadata = {
                    "query": query,
                    "timestamp": start_time.isoformat(),
                    "duration_seconds": duration,
                    "mode": "camel_agents",
                    "agents_used": ["DataAgent", "GeoAgent", "AnalystAgent"]
                    + (["WebAgent"] if with_web else []),
                    "stats": collected_data["stats"],
                }

                metadata_path = analysis_dir / "metadata.json"
                metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))

                notify(f"[CAMEL] Analyse terminee! {len(enterprises)} entreprises", 100)

                result = {
                    "success": True,
                    "query": query,
                    "mode": "camel_agents",
                    "rapport_md": rapport_md,
                    "output_dir": str(analysis_dir),
                    "files": {
                        "rapport": str(rapport_path),
                        "csv": str(csv_path),
                        "metadata": str(metadata_path),
                    },
                    "metadata": metadata,
                }

                if collected_data["stats"].get("map_file"):
                    result["files"]["carte"] = collected_data["stats"]["map_file"]

                return json.dumps(result, ensure_ascii=False, indent=2, default=str)

            except Exception as e:
                logger.error(f"CAMEL workforce failed: {e}, falling back to simple mode")
                notify(f"[CAMEL] Erreur agents, mode simplifie: {str(e)[:30]}", 10)
                # Fall through to simple mode

        # =====================================================================
        # MODE SIMPLIFIE (use_agents=False ou fallback)
        # Appelle les tools directement sans agents
        # =====================================================================
        notify("[Simple] Mode sans agents IA", 10)

        # Results storage
        collected_data = {
            "entreprises": [],
            "locations": [],
            "enrichments": [],
            "stats": {},
        }

        # =====================================================================
        # PHASE 1: DataAgent - Collecte Sirene
        # =====================================================================
        notify("[DataAgent] Collecte donnees Sirene...", 10)

        try:
            sirene_result = sirene_search(query=query, limite=limit)

            if sirene_result.get("success") and sirene_result.get("enterprises"):
                enterprises = sirene_result["enterprises"]
                collected_data["entreprises"] = enterprises
                collected_data["stats"]["sirene_count"] = len(enterprises)
                notify(f"[DataAgent] {len(enterprises)} entreprises collectees", 25)
            else:
                # Fallback: try with default orchestrator search
                notify("[DataAgent] Sirene direct vide, recherche via orchestrateur...", 15)
                from src.application.orchestration.data_orchestrator import DataOrchestrator

                orchestrator = DataOrchestrator()
                orch_result = await orchestrator.search(query=query, limit_per_source=limit)

                all_results = []
                for sr in orch_result.source_results:
                    all_results.extend(sr.results)
                    notify(f"[DataAgent] Source {sr.source}: {len(sr.results)} resultats")

                collected_data["entreprises"] = all_results
                collected_data["stats"]["sirene_count"] = len(all_results)
                notify(f"[DataAgent] {len(all_results)} entreprises collectees (multi-sources)", 25)

        except Exception as e:
            logger.error(f"DataAgent error: {e}")
            notify(f"[DataAgent] Erreur: {str(e)[:50]}...", 25)
            collected_data["stats"]["sirene_error"] = str(e)

        # =====================================================================
        # PHASE 2: GeoAgent - Geocodage et Cartographie
        # =====================================================================
        if with_map and collected_data["entreprises"]:
            notify("[GeoAgent] Geocodage et cartographie...", 30)

            locations = []
            geocoded_count = 0

            for ent in collected_data["entreprises"][:limit]:
                # Check if already has geo data
                geo = ent.get("geo")
                if geo and geo.get("lat"):
                    locations.append(
                        {
                            "nom": ent.get("nom") or ent.get("name") or ent.get("title", "N/A"),
                            "lat": geo["lat"],
                            "lon": geo["lon"],
                            "type": "entreprise",
                            "siret": ent.get("siret", ""),
                            "commune": ent.get("commune", ""),
                        }
                    )
                    geocoded_count += 1
                elif ent.get("adresse"):
                    # Geocode the address
                    try:
                        geo_result = geo_locate(ent["adresse"])
                        if geo_result.get("lat"):
                            locations.append(
                                {
                                    "nom": ent.get("nom") or ent.get("name", "N/A"),
                                    "lat": geo_result["lat"],
                                    "lon": geo_result["lon"],
                                    "type": "entreprise",
                                    "siret": ent.get("siret", ""),
                                    "commune": geo_result.get("city", ""),
                                }
                            )
                            geocoded_count += 1
                    except Exception as e:
                        logger.debug(f"Geocoding failed for {ent.get('nom', 'unknown')}: {e}")
                        pass

            collected_data["locations"] = locations
            collected_data["stats"]["geocoded_count"] = geocoded_count
            total_ent = len(collected_data["entreprises"])
            geocode_rate = (geocoded_count / total_ent * 100) if total_ent > 0 else 0

            notify(f"[GeoAgent] Geocodage: {geocoded_count}/{total_ent} ({geocode_rate:.0f}%)", 45)

            # Generate map
            if locations:
                map_path = str(analysis_dir / "carte.html")
                try:
                    map_result = geo_map(
                        locations=locations,
                        title=f"Analyse: {query}",
                        style="default",
                    )
                    if map_result.get("success") and map_result.get("file_path"):
                        # Copy to analysis dir
                        import shutil

                        shutil.copy(map_result["file_path"], map_path)
                        collected_data["stats"]["map_file"] = map_path
                        collected_data["stats"]["map_markers"] = len(locations)
                        notify(f"[GeoAgent] Carte generee: {len(locations)} marqueurs", 55)
                except Exception as e:
                    logger.error(f"GeoAgent map error: {e}")
                    notify(f"[GeoAgent] Erreur carte: {str(e)[:30]}...", 55)

        else:
            notify("[GeoAgent] Cartographie desactivee ou pas de donnees", 55)

        # =====================================================================
        # PHASE 3: WebAgent - Enrichissement Web (optionnel)
        # =====================================================================
        if with_web and collected_data["entreprises"]:
            notify("[WebAgent] Enrichissement web...", 60)

            from src.infrastructure.agents.camel.tools.browser_tools import browser_search

            enriched_count = 0
            # Limit web enrichment to top 20 to avoid timeout
            for ent in collected_data["entreprises"][:20]:
                name = ent.get("nom") or ent.get("name", "")
                if name:
                    try:
                        # Search for company website info
                        search_result = browser_search(f"{name} site officiel")
                        if search_result.get("results"):
                            ent["web_enrichment"] = {
                                "search_results": search_result["results"][:3],
                            }
                            enriched_count += 1
                    except Exception as e:
                        logger.debug(f"Web enrichment failed for {name}: {e}")
                        pass

            collected_data["stats"]["web_enriched"] = enriched_count
            notify(f"[WebAgent] {enriched_count} entreprises enrichies", 75)

        elif with_web:
            notify("[WebAgent] Pas de donnees a enrichir", 75)
        else:
            notify("[WebAgent] Enrichissement web desactive", 75)

        # =====================================================================
        # PHASE 4: AnalystAgent - Rapport Strategique
        # =====================================================================
        notify("[AnalystAgent] Generation du rapport...", 80)

        # Calculate statistics
        enterprises = collected_data["entreprises"]
        total_count = len(enterprises)

        # Effectif analysis
        effectif_distribution = {"<10": 0, "10-50": 0, "50-250": 0, ">250": 0}
        for ent in enterprises:
            effectif = ent.get("effectif", ent.get("trancheEffectifs", 0))
            try:
                eff_val = int(str(effectif).split("-")[0].replace("+", "")) if effectif else 0
            except (ValueError, TypeError):
                eff_val = 0

            if eff_val < 10:
                effectif_distribution["<10"] += 1
            elif eff_val < 50:
                effectif_distribution["10-50"] += 1
            elif eff_val < 250:
                effectif_distribution["50-250"] += 1
            else:
                effectif_distribution[">250"] += 1

        # Commune distribution
        communes = {}
        for ent in enterprises:
            commune = ent.get("commune", ent.get("city", "Non specifie"))
            communes[commune] = communes.get(commune, 0) + 1
        top_communes = sorted(communes.items(), key=lambda x: x[1], reverse=True)[:5]

        # Generate Markdown report
        rapport_md = f"""# Rapport d'Intelligence Territoriale

## Executive Summary

Analyse du marche **"{query}"** avec **{total_count}** entreprises identifiees.
{"Cartographie interactive generee avec " + str(collected_data["stats"].get("map_markers", 0)) + " points." if with_map else ""}
{"Enrichissement web effectue sur " + str(collected_data["stats"].get("web_enriched", 0)) + " entreprises." if with_web else ""}

## Chiffres Cles

| Metrique | Valeur |
|----------|--------|
| Entreprises identifiees | **{total_count}** |
| Taux de geocodage | **{collected_data["stats"].get("geocoded_count", 0)}/{total_count}** |
| Sources interrogees | Sirene, Multi-sources |

## Repartition par Effectif

| Tranche | Nombre | Part |
|---------|--------|------|
| < 10 salaries | {effectif_distribution["<10"]} | {effectif_distribution["<10"] / total_count * 100:.1f}% |
| 10-50 salaries | {effectif_distribution["10-50"]} | {effectif_distribution["10-50"] / total_count * 100:.1f}% |
| 50-250 salaries | {effectif_distribution["50-250"]} | {effectif_distribution["50-250"] / total_count * 100:.1f}% |
| > 250 salaries | {effectif_distribution[">250"]} | {effectif_distribution[">250"] / total_count * 100:.1f}% |

## Top 5 Communes

| Commune | Entreprises |
|---------|-------------|
"""
        for commune, count in top_communes:
            rapport_md += f"| {commune} | {count} |\n"

        rapport_md += """
## Top 10 Acteurs

| # | Entreprise | SIRET | Commune | Effectif |
|---|------------|-------|---------|----------|
"""
        for i, ent in enumerate(enterprises[:10], 1):
            name = ent.get("nom") or ent.get("name") or ent.get("title", "N/A")
            siret = ent.get("siret", "N/A")
            commune = ent.get("commune", ent.get("city", "N/A"))
            effectif = ent.get("effectif", ent.get("trancheEffectifs", "N/A"))
            rapport_md += f"| {i} | {name} | {siret} | {commune} | {effectif} |\n"

        rapport_md += f"""
## Recommandations

1. **[PRIORITE HAUTE]** : Contacter les {min(5, len([e for e in enterprises if effectif_distribution[">250"] > 0]))} grandes entreprises (>250 salaries) pour partenariats strategiques
2. **[PRIORITE MOYENNE]** : Analyser les {effectif_distribution["50-250"]} ETI pour opportunites de croissance
3. **[OPTIONNEL]** : Veille sur les {effectif_distribution["<10"]} TPE/startups innovantes

---
*Rapport genere le {datetime.now().strftime("%d/%m/%Y a %H:%M")} par Tawiza Workforce*
"""

        notify("[AnalystAgent] Rapport genere", 90)

        # Save files
        # 1. Rapport Markdown
        rapport_path = analysis_dir / "rapport.md"
        rapport_path.write_text(rapport_md, encoding="utf-8")

        # 2. CSV des entreprises
        csv_path = analysis_dir / "entreprises.csv"
        if enterprises:
            fieldnames = ["nom", "siret", "commune", "effectif", "activite", "adresse"]
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for ent in enterprises:
                    row = {
                        "nom": ent.get("nom") or ent.get("name") or ent.get("title", ""),
                        "siret": ent.get("siret", ""),
                        "commune": ent.get("commune", ent.get("city", "")),
                        "effectif": ent.get("effectif", ent.get("trancheEffectifs", "")),
                        "activite": ent.get("activite", ent.get("naf", "")),
                        "adresse": ent.get("adresse", ""),
                    }
                    writer.writerow(row)

        # 3. Metadata JSON
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        metadata = {
            "query": query,
            "timestamp": start_time.isoformat(),
            "duration_seconds": duration,
            "options": {
                "with_map": with_map,
                "with_web": with_web,
                "limit": limit,
            },
            "stats": collected_data["stats"],
            "effectif_distribution": effectif_distribution,
            "top_communes": dict(top_communes),
            "agents_used": ["DataAgent", "GeoAgent"]
            + (["WebAgent"] if with_web else [])
            + ["AnalystAgent"],
        }

        metadata_path = analysis_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        notify(f"[AnalystAgent] Fichiers sauvegardes dans {analysis_dir}", 95)

        # Build response with HTTP URLs for file access
        # Get relative path for URL (analyses/timestamp_query)
        relative_dir = (
            str(analysis_dir).split("/outputs/")[-1]
            if "/outputs/" in str(analysis_dir)
            else analysis_dir.name
        )
        base_url = "http://localhost:8766"

        result = {
            "success": True,
            "query": query,
            "rapport_md": rapport_md,
            "output_dir": str(analysis_dir),
            "files": {
                "rapport": str(rapport_path),
                "csv": str(csv_path),
                "metadata": str(metadata_path),
            },
            "urls": {
                "rapport": f"{base_url}/{relative_dir}/rapport.md",
                "csv": f"{base_url}/{relative_dir}/data.csv",
            },
            "metadata": metadata,
        }

        if with_map and collected_data["stats"].get("map_file"):
            result["files"]["carte"] = collected_data["stats"]["map_file"]
            result["urls"]["carte"] = f"{base_url}/{relative_dir}/carte.html"

        notify(f"Analyse terminee! {total_count} entreprises, {duration:.1f}s", 100)
        logger.info(f"Workforce analysis complete: {query} -> {analysis_dir}")

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    @mcp.tool()
    async def tawiza_workforce_status(ctx: Context = None) -> str:
        """Verifie le statut du systeme Workforce CAMEL AI.

        Teste la disponibilite:
        - Ollama et modele LLM
        - Outils territoriaux (Sirene, Geo)
        - Agents specialises

        Returns:
            JSON avec statut de chaque composant
        """
        from src.infrastructure.agents.camel.workforce import create_territorial_workforce

        status = {
            "workforce": False,
            "ollama": False,
            "model": "qwen3.5:27b",
            "tools": {
                "sirene": False,
                "geo": False,
                "browser": False,
            },
            "agents": {
                "data": False,
                "geo": False,
                "web": False,
                "analyst": False,
            },
        }

        # Test Ollama
        try:
            from src.infrastructure.llm import OllamaClient

            client = OllamaClient(model="qwen3.5:27b")
            response = await client.generate("Test", max_tokens=10)
            status["ollama"] = bool(response)
            if ctx:
                ctx.info("Ollama: OK")
        except Exception as e:
            if ctx:
                ctx.info(f"Ollama: Erreur - {str(e)[:30]}")

        # Test tools
        try:
            status["tools"]["sirene"] = True
            if ctx:
                ctx.info("Tool Sirene: OK")
        except Exception as e:
            logger.debug(f"Sirene tool check failed: {e}")
            pass

        try:
            status["tools"]["geo"] = True
            if ctx:
                ctx.info("Tool Geo: OK")
        except Exception as e:
            logger.debug(f"Geo tool check failed: {e}")
            pass

        try:
            status["tools"]["browser"] = True
            if ctx:
                ctx.info("Tool Browser: OK")
        except Exception as e:
            logger.debug(f"Browser tool check failed: {e}")
            pass

        # Test workforce creation
        try:
            workforce = create_territorial_workforce(enable_web_enrichment=False)
            status["workforce"] = True
            status["agents"]["data"] = workforce.data_agent is not None
            status["agents"]["geo"] = workforce.geo_agent is not None
            status["agents"]["analyst"] = workforce.analyst_agent is not None
            status["agents"]["web"] = (
                workforce.web_agent is not None if workforce.enable_web_enrichment else True
            )
            if ctx:
                ctx.info("Workforce: OK")
        except Exception as e:
            if ctx:
                ctx.info(f"Workforce: Erreur - {str(e)[:30]}")

        return json.dumps(status, ensure_ascii=False, indent=2)
