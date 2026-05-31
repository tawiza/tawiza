# Serveur MCP

Serveur **Model Context Protocol** de Tawiza. Expose les outils d'analyse de marchés territoriaux français à des clients MCP externes (Cherry Studio et autres). Construit sur `FastMCP` et organisé en outils, ressources et notifications de progression.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      FastMCP "Tawiza"                          │
│                                                                │
│   Transport: stdio (défaut)  ou  SSE (HTTP Server-Sent Events) │
│                                                                │
│  ┌────────────────────────┐   ┌──────────────────────────┐    │
│  │        Tools           │   │        Resources         │    │
│  │  (13 modules register) │   │  tawiza://sources        │    │
│  │                        │   │  tawiza://agents         │    │
│  │  high_level · granular │   │  tawiza://workforce      │    │
│  │  browser · dashboard   │   │  tawiza://alerts         │    │
│  │  web_search · workforce│   │  tawiza://veille         │    │
│  │  veille · comparison   │   │  tawiza://dashboard/*     │    │
│  │  prospection           │   └──────────────────────────┘    │
│  │  simulation            │                                    │
│  │  business_plan         │   ┌──────────────────────────┐    │
│  │  benchmark             │   │      Notifications       │    │
│  └────────────────────────┘   │   ProgressNotifier       │    │
│                                │   (step/source/agent/    │    │
│                                │    browser/geocode)      │    │
│                                └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Transports

Le serveur se lance via `python -m src.infrastructure.mcp` :

| Transport | Commande | Usage |
|-----------|----------|-------|
| **stdio** (défaut) | `python -m src.infrastructure.mcp` | Clients MCP locaux |
| **SSE** (HTTP) | `python -m src.infrastructure.mcp --sse --port 8080 --host 0.0.0.0` | Accès réseau distant (Cherry Studio) |

En mode SSE, un serveur de fichiers statiques est démarré en parallèle sur `port + 1` pour exposer le répertoire `outputs/` (cartes HTML, rapports). L'endpoint SSE est `http://<host>:<port>/sse`.

## Outils MCP

Les outils sont enregistrés par 13 fonctions `register_*_tools(mcp)` appelées dans `server.py`.

### `high_level.py`  -  Outils de haut niveau
Outils orchestrant le pipeline complet :
- `tawiza_analyze` : Analyse complète d'un marché territorial
- `tawiza_search` : Recherche multi-sources dans les bases françaises
- `tawiza_validate` : Validation par débat multi-agents LLM
- `tawiza_map` : Génération de carte interactive
- `tawiza_chat` : Assistant conversationnel

### `granular.py`  -  Outils granulaires
Accès direct à chaque source/capacité :
- `sirene_search`, `bodacc_search`, `boamp_search` : Recherche par base
- `geo_locate`, `geo_batch_locate`, `geo_generate_map` : Géocodage (BAN) et cartographie Folium
- `debate_run` : Lancement d'un débat multi-agents
- `gdelt_search` : Recherche d'actualités GDELT
- `subventions_search` : Subventions publiques (data.gouv.fr)

### `browser.py`  -  Pilotage navigateur (PiP)
Streaming Picture-in-Picture et automatisation :
- `browser_start_stream`, `browser_stop_stream`, `browser_screenshot`
- `browser_navigate`, `browser_click`, `browser_extract`, `browser_scrape_page`

### `dashboard.py`  -  Dashboard et watchlist
Gestion des alertes et de la surveillance :
- `dashboard_mark_read`, `dashboard_get_alert`, `dashboard_get_alerts`
- `watchlist_add`, `watchlist_remove`, `watchlist_list`
- `watcher_force_poll`, `tawiza_dashboard_status`

### `web_search.py`  -  Recherche web DuckDuckGo
Recherche gratuite sans clé API :
- `web_search`, `web_search_news`, `web_search_images`, `web_search_maps`

### `workforce.py`  -  Workforce CAMEL AI
Analyse de marché via 4 agents CAMEL coordonnés :
- `tawiza_workforce_analyze` : Analyse complète (rapport + carte + CSV + metadata)
- `tawiza_workforce_status` : Statut du système Workforce

### `veille.py`  -  Veille automatisée
Monitoring continu avec filtrage LLM :
- `tawiza_veille_scan`, `tawiza_veille_digest`
- `tawiza_veille_configure`, `tawiza_veille_alert_detail`

### `comparison.py`  -  Comparaison multi-territoires
- `tawiza_compare_markets` : Comparaison d'un marché sur plusieurs territoires en parallèle
- `tawiza_territory_benchmark` : Benchmark d'un territoire sur plusieurs secteurs

### `prospection.py`  -  Prospection automatisée
Génération et enrichissement de leads :
- `tawiza_prospect`, `tawiza_prospect_export`
- `tawiza_generate_message`, `tawiza_lead_score`, `tawiza_financial_health`

### `simulation.py`  -  Simulation de scénarios économiques
- `tawiza_simulate` : Simulation d'impact d'un scénario sur un territoire
- `tawiza_scenarios_list`, `tawiza_impact_analysis`

### `business_plan.py`  -  Génération de business plans
- `tawiza_generate_bp`, `tawiza_bp_templates`
- `tawiza_bp_section`, `tawiza_bp_from_analysis`

### `benchmark.py`  -  Benchmark des outils
- `tawiza_benchmark_run`, `tawiza_benchmark_list`
- `tawiza_benchmark_tool`, `tawiza_benchmark_compare`

## Ressources MCP

Les ressources exposent des informations sur le serveur (statiques et dynamiques).

### Ressources statiques (`server.py`)

| URI | Description |
|-----|-------------|
| `tawiza://sources` | Liste des sources de données (SIRENE, BODACC, BOAMP, BAN, GDELT, subventions) |
| `tawiza://agents` | Description du pipeline de débat (6 agents : Chercheur, SourceRanker, Critique, FactChecker, Vérificateur, Synthèse) |
| `tawiza://workforce` | Description du Workforce CAMEL AI (4 agents) |
| `tawiza://alerts` | Alertes de veille en temps réel (lecture `DashboardDB`) |
| `tawiza://veille` | Documentation de la veille automatisée |

### Ressources dynamiques (`resources/dashboard.py`)

Enregistrées via `register_dashboard_resources(mcp)`, elles interrogent `DashboardDB` et renvoient du JSON :

| URI | Description |
|-----|-------------|
| `tawiza://dashboard/status` | État système (sources, watcher, base, statut Ollama) |
| `tawiza://dashboard/alerts` | Alertes non lues par source |
| `tawiza://dashboard/history` | Historique des analyses récentes |
| `tawiza://dashboard/stats` | Statistiques d'utilisation sur 7 jours |

## Notifications de progression

Le module `notifications/progress.py` fournit le `ProgressNotifier`, qui relaie les mises à jour de progression vers le client MCP pendant les opérations longues. Il enveloppe `ctx.report_progress` et accepte des callbacks additionnels.

Types d'événements (`ProgressType`) :

| Type | Usage |
|------|-------|
| `STEP` | Progression d'une étape principale |
| `SOURCE` | Requête vers une source de données |
| `AGENT` | Activité d'un agent de débat |
| `BROWSER` | Navigation navigateur |
| `GEOCODE` | Opération de géocodage |

Le `StepContext` (context manager `async`) permet de suivre une étape avec compteur (`update()`, `increment()`).

## Fichiers clés

```
src/infrastructure/mcp/
├── server.py                   # Serveur FastMCP : args, transports, ressources statiques
├── __main__.py                 # Point d'entrée (python -m src.infrastructure.mcp)
├── __init__.py                 # Exporte mcp, run_server
├── tools/
│   ├── high_level.py           # tawiza_analyze, search, validate, map, chat
│   ├── granular.py             # SIRENE/BODACC/BOAMP, geo, debate, GDELT, subventions
│   ├── browser.py              # Pilotage navigateur PiP
│   ├── dashboard.py            # Alertes et watchlist
│   ├── web_search.py           # Recherche DuckDuckGo
│   ├── workforce.py            # Workforce CAMEL AI
│   ├── veille.py               # Veille automatisée
│   ├── comparison.py           # Comparaison multi-territoires
│   ├── prospection.py          # Prospection et leads
│   ├── simulation.py           # Simulation de scénarios
│   ├── business_plan.py        # Génération de business plans
│   └── benchmark.py            # Benchmark des outils
├── resources/
│   └── dashboard.py            # Ressources dynamiques tawiza://dashboard/*
├── notifications/
│   └── progress.py             # ProgressNotifier, StepContext
└── chat/                       # Package assistant chat (placeholder)
```

## Configuration

| Argument | Description | Défaut |
|----------|-------------|--------|
| `--sse` | Active le transport SSE (HTTP) au lieu de stdio | `false` (stdio) |
| `--port` | Port du serveur SSE | `8080` |
| `--host` | Hôte du serveur SSE | `0.0.0.0` |

En mode SSE, le serveur de fichiers statiques (répertoire `outputs/`) écoute sur `port + 1`.

Les ressources du dashboard vérifient le statut Ollama via `http://localhost:11434/api/tags`.

## État actuel

- Le serveur expose 13 modules d'outils et un ensemble de ressources statiques + dynamiques
- Les transports stdio et SSE sont opérationnels, avec serveur de fichiers statiques en SSE
- Les ressources du dashboard sont alimentées par `DashboardDB` et `WatcherDaemon`
- Le système de notifications de progression est intégré aux outils longs
- Le package `chat/` est un placeholder (uniquement `__init__.py`)
