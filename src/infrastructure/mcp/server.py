"""Main MCP Server for Tawiza.

Exposes territorial market analysis tools via Model Context Protocol.
Designed for integration with Cherry Studio and other MCP clients.

Usage:
    # Local (stdio) - for local MCP clients
    python -m src.infrastructure.mcp

    # Network (SSE) - for remote Cherry Studio access
    python -m src.infrastructure.mcp --sse --port 8080 --host 0.0.0.0

Transport: stdio (default) or SSE (HTTP Server-Sent Events)
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from mcp.server.fastmcp import FastMCP


# Parse arguments early to configure server
def _parse_args():
    parser = argparse.ArgumentParser(description="Tawiza MCP Server")
    parser.add_argument("--sse", action="store_true", help="Use SSE transport (HTTP) instead of stdio")
    parser.add_argument("--port", type=int, default=8080, help="Port for SSE server (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE server (default: 0.0.0.0)")
    return parser.parse_args()

_args = _parse_args()

# Create the MCP server instance with host/port for SSE
mcp = FastMCP(
    name="Tawiza",
    instructions="Analyse de marchés territoriaux français - Multi-sources + Débat multi-agents LLM",
    host=_args.host,
    port=_args.port,
)


# Import and register tools
from src.infrastructure.mcp.resources.dashboard import register_dashboard_resources
from src.infrastructure.mcp.tools.benchmark import register_benchmark_tools
from src.infrastructure.mcp.tools.browser import register_browser_tools
from src.infrastructure.mcp.tools.business_plan import register_business_plan_tools
from src.infrastructure.mcp.tools.comparison import register_comparison_tools
from src.infrastructure.mcp.tools.dashboard import register_dashboard_tools
from src.infrastructure.mcp.tools.granular import register_granular_tools
from src.infrastructure.mcp.tools.high_level import register_high_level_tools
from src.infrastructure.mcp.tools.prospection import register_prospection_tools
from src.infrastructure.mcp.tools.simulation import register_simulation_tools
from src.infrastructure.mcp.tools.veille import register_veille_tools
from src.infrastructure.mcp.tools.web_search import register_web_search_tools
from src.infrastructure.mcp.tools.workforce import register_workforce_tools

register_high_level_tools(mcp)
register_granular_tools(mcp)
register_browser_tools(mcp)
register_dashboard_tools(mcp)
register_web_search_tools(mcp)
register_workforce_tools(mcp)
register_veille_tools(mcp)
register_comparison_tools(mcp)
register_prospection_tools(mcp)
register_simulation_tools(mcp)
register_business_plan_tools(mcp)
register_benchmark_tools(mcp)
register_dashboard_resources(mcp)


# Resources - static information about the server
@mcp.resource("tawiza://sources")
def get_sources() -> str:
    """Liste des sources de données disponibles."""
    return """# Sources de données Tawiza

## Sources principales (France)
- **SIRENE** - Base INSEE des entreprises françaises (SIRET, NAF, effectifs)
- **BODACC** - Annonces légales (créations, modifications, radiations)
- **BOAMP** - Marchés publics français
- **BAN** - Base Adresse Nationale (géocodage)

## Sources complémentaires
- **GDELT** - Actualités mondiales en temps réel
- **Google News RSS** - Actualités Google
- **Data.gouv Subventions** - Subventions publiques

## Capacités
- Recherche multi-sources parallèle
- Géocodage automatique des adresses
- Débat multi-agents pour validation (6 agents LLM)
- Génération de cartes interactives
"""


@mcp.resource("tawiza://agents")
def get_agents() -> str:
    """Description des agents de débat."""
    return """# Agents de Débat Tawiza

## Pipeline de validation (6 agents)

### 1. Chercheur
Analyse les données collectées et identifie les informations clés.

### 2. SourceRanker
Évalue la fiabilité et la pertinence de chaque source.

### 3. Critique
Questionne les données, identifie les incohérences et les lacunes.

### 4. FactChecker
Vérifie les faits en croisant les sources.

### 5. Vérificateur
Synthétise les analyses et produit un score de confiance.

### 6. Synthèse
Rédige le rapport final avec conclusions et recommandations.

## Modes de débat
- **STANDARD** - 3 agents (rapide)
- **EXTENDED** - 6 agents (approfondi)
"""


@mcp.resource("tawiza://workforce")
def get_workforce() -> str:
    """Description du Workforce CAMEL AI."""
    return """# Workforce CAMEL AI - Analyse de Marche Territoriale

## Vue d'ensemble
Le Workforce coordonne 4 agents IA specialises qui collaborent pour
produire une analyse de marche complete.

## Les 4 Agents

### 1. DataAgent
Expert en collecte de donnees d'entreprises francaises.
- Interroge l'API Sirene (INSEE)
- Filtre par secteur, territoire, effectif
- Nettoie et structure les donnees

### 2. GeoAgent
Expert en cartographie territoriale.
- Geocode les adresses (BAN)
- Genere des cartes Folium interactives
- Identifie les zones de concentration

### 3. WebAgent (optionnel)
Expert en veille web et enrichissement.
- Visite les sites web des entreprises
- Extrait descriptions, services, actualites
- Enrichit les donnees Sirene

### 4. AnalystAgent
Stratege qui transforme les donnees en insights.
- Synthetise toutes les donnees
- Produit un rapport structuré
- Formule des recommandations actionnables

## Outil MCP: tawiza_workforce_analyze

```
tawiza_workforce_analyze(
    query: str,           # "marche conseil IT Lille"
    output_dir: str,      # "./outputs/analyses"
    with_map: bool=True,  # Carte interactive
    with_web: bool=False, # Enrichissement web
    limit: int=50         # Max entreprises
)
```

## Fichiers generes
- `rapport.md` - Rapport strategique Markdown
- `carte.html` - Carte Folium interactive
- `entreprises.csv` - Donnees brutes
- `metadata.json` - Stats de l'analyse
"""


@mcp.resource("tawiza://alerts")
def get_alerts_resource() -> str:
    """Alertes de veille en temps reel."""
    from src.infrastructure.dashboard import DashboardDB

    db = DashboardDB()
    alerts = db.get_unread_alerts(limit=20)
    alerts_count = db.get_alerts_count()
    poll_status = db.get_poll_status()

    return f"""# Alertes de Veille Tawiza

## Resume
- **Alertes non lues**: {alerts_count.get('total_unread', 0)}
- **Total alertes**: {alerts_count.get('total', 0)}

## Par Source
- BODACC: {alerts_count.get('by_source', {}).get('bodacc', 0)}
- BOAMP: {alerts_count.get('by_source', {}).get('boamp', 0)}
- GDELT: {alerts_count.get('by_source', {}).get('gdelt', 0)}

## Dernieres Alertes Non Lues
{"".join(f"- **{a['title'][:50]}...** ({a['source']})" + chr(10) for a in alerts[:10]) or "Aucune alerte non lue"}

## Status Polling
- BODACC: {poll_status.get('bodacc', {}).get('last_poll', 'jamais')}
- BOAMP: {poll_status.get('boamp', {}).get('last_poll', 'jamais')}
- GDELT: {poll_status.get('gdelt', {}).get('last_poll', 'jamais')}

## Outils Disponibles
- `tawiza_veille_scan` - Scan avec filtrage LLM
- `tawiza_veille_digest` - Digest periodique
- `tawiza_veille_configure` - Configuration watchlist
- `tawiza_veille_alert_detail` - Detail d'une alerte
"""


@mcp.resource("tawiza://veille")
def get_veille_resource() -> str:
    """Documentation de la veille automatisee."""
    return """# Veille Automatisee Tawiza

## Vue d'ensemble
Systeme de monitoring continu des marches territoriaux francais
avec filtrage intelligent LLM.

## Sources Surveillees

### BODACC (Bulletin Officiel des Annonces Civiles et Commerciales)
- Creations d'entreprises
- Radiations
- Modifications statutaires
- Ventes de fonds de commerce
- **Frequence**: toutes les 6 heures

### BOAMP (Bulletin Officiel des Annonces de Marches Publics)
- Appels d'offres
- Attributions de marches
- **Frequence**: toutes les 6 heures

### GDELT (Global Database of Events, Language, and Tone)
- Actualites economiques
- Mentions d'entreprises dans les medias
- **Frequence**: toutes les 2 heures

## Filtrage Intelligent LLM

Chaque alerte est scoree par un LLM (qwen3.5:27b) sur 5 niveaux:

| Priorite | Score | Description |
|----------|-------|-------------|
| CRITICAL | 80-100 | Action immediate requise |
| HIGH | 60-79 | Important, traiter rapidement |
| MEDIUM | 40-59 | Interessant, a surveiller |
| LOW | 20-39 | Information de fond |
| NOISE | 0-19 | Non pertinent |

## Outils MCP

### tawiza_veille_scan
Scan immediat avec filtrage LLM.
```
tawiza_veille_scan(
    keywords: ["startup", "IA"],
    sources: ["bodacc", "boamp"],
    min_priority: "medium",
    limit: 20
)
```

### tawiza_veille_digest
Digest periodique avec analyse.
```
tawiza_veille_digest(period: "today"|"week"|"month")
```

### tawiza_veille_configure
Gestion de la watchlist.
```
tawiza_veille_configure(
    action: "add"|"remove"|"list"|"status",
    keywords: ["mot1", "mot2"],
    sources: ["bodacc"]
)
```

## Watchlist
Configurez les mots-cles a surveiller pour recevoir
des alertes pertinentes automatiquement.
"""


def run_server():
    """Run the MCP server with stdio or SSE transport."""
    if _args.sse:
        # Start static file server for maps/outputs
        import http.server
        import os
        import socketserver
        import threading

        outputs_dir = Path(__file__).parent.parent.parent.parent / "outputs"
        outputs_dir.mkdir(exist_ok=True)

        file_port = _args.port + 1  # 8766 if MCP is on 8765

        def serve_files():
            os.chdir(outputs_dir)
            handler = http.server.SimpleHTTPRequestHandler
            with socketserver.TCPServer(("", file_port), handler) as httpd:
                httpd.serve_forever()

        file_thread = threading.Thread(target=serve_files, daemon=True)
        file_thread.start()

        print(f"🚀 Starting Tawiza MCP Server (SSE) on http://{_args.host}:{_args.port}")
        print(f"📡 Cherry Studio URL: http://<your-ip>:{_args.port}/sse")
        print(f"📁 Files Server: http://<your-ip>:{file_port}/")
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
