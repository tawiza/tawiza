```
                       ████████╗ █████╗ ██╗    ██╗██╗███████╗ █████╗
                       ╚══██╔══╝██╔══██╗██║    ██║██║╚══███╔╝██╔══██╗
                          ██║   ███████║██║ █╗ ██║██║  ███╔╝ ███████║
                          ██║   ██╔══██║██║███╗██║██║ ███╔╝  ██╔══██║
                          ██║   ██║  ██║╚███╔███╔╝██║███████╗██║  ██║
                          ╚═╝   ╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝╚══════╝╚═╝  ╚═╝
```


# Tawiza — Intelligence territoriale propulsee par l'IA
<p align="center">
  <img width="48%" alt="Dashboard Analytics" src="https://github.com/user-attachments/assets/ecc9079c-8c61-4d95-b32b-a59487238832" style="border-radius: 12px;" />
  <img width="48%" alt="Agent TAJINE" src="https://github.com/user-attachments/assets/ee96d642-5777-4d8b-98b0-28271bfcfaa3" style="border-radius: 12px;" />
</p>
<p align="center">
  <img width="48%" alt="Cockpit Territorial" src="https://github.com/user-attachments/assets/60558f98-adba-4de0-b6e2-2ffc39fec3f3" style="border-radius: 12px;" />
</p>


[![CI](https://github.com/hamidedefr/tawiza/actions/workflows/ci.yml/badge.svg)](https://github.com/hamidedefr/tawiza/actions/workflows/ci.yml)
[![Status: Beta](https://img.shields.io/badge/Status-Beta-orange.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Website](https://img.shields.io/badge/Website-tawiza.fr-indigo.svg)](https://hamidedefr.github.io/tawiza-landing/)

> **Beta** — Ce projet est en developpement actif. L'API, le schema de donnees et les fonctionnalites peuvent changer. On est preneurs de retours et de contributions !

> Parce que scraper l'INSEE a la main, c'est so 2020.

**Tawiza** est une plateforme open source d'intelligence economique et territoriale francaise. Elle analyse les entreprises, les territoires et les dynamiques economiques en s'appuyant sur 18+ APIs gouvernementales, des agents IA cognitifs, et un systeme de collecte proactive de donnees.

> **Tawiza** (ⵜⴰⵡⵉⵣⴰ) — mot amazigh signifiant *entraide collective*. Parce que l'intelligence economique, c'est mieux a plusieurs.

---

## Pourquoi Tawiza ?

- **Les donnees publiques francaises sont un tresor**... disperse sur 18 APIs differentes, avec 18 formats differents, et 18 facons de paginer. On a fait le sale boulot pour vous.
- **L'IA sans donnees reelles, c'est de la fiction**. Tawiza ne triche pas : zero mock, zero donnees synthetiques. Tout vient d'APIs gouvernementales en production.
- **Analyser un territoire, ca ne devrait pas prendre 3 semaines**. Un agent IA cognitif (TAJINE) decompose votre question, collecte les donnees, et synthetise — pendant que vous prenez un cafe.
- **Self-hostable, forkable, hackable**. Votre intelligence economique vous appartient.

---

## Fonctionnalites

### Agent TAJINE — Le cerveau

L'agent TAJINE suit le cycle **PPDSL** (Perceive-Plan-Delegate-Synthesize-Learn) avec 5 niveaux cognitifs :

| Niveau | Capacite | Exemple |
|--------|----------|---------|
| **Discovery** | Extraction factuelle | "Combien d'entreprises tech a Toulouse ?" |
| **Causal** | Analyse causale (DAG) | "Pourquoi le secteur BTP recule en Occitanie ?" |
| **Scenario** | Simulation Monte Carlo | "Et si on doublait les subventions innovation ?" |
| **Strategy** | Recommandations strategiques | "Ou investir pour maximiser l'emploi ?" |
| **Theoretical** | Principes generaux | "Quels facteurs structurels expliquent l'attractivite ?" |

Chaque niveau s'appuie sur des modules specialises : raisonnement causal (DAG), simulation Monte Carlo, modelisation agent-based (menages/entreprises), et debate multi-agents pour les questions complexes.

### Data Hunter — La collecte proactive

Le **Data Hunter** est le moteur de collecte intelligent de Tawiza. Au lieu d'interroger betement toutes les sources, il utilise 4 strategies combinees :

| Strategie | Methode | Quand |
|-----------|---------|-------|
| **Hypothesis-driven** | Le LLM genere des hypotheses a valider | Questions complexes |
| **Bandit-optimized** | UCB1/LinUCB selectionnent les meilleures sources | Mode normal |
| **Graph-expanding** | Neo4j detecte les trous dans le graphe de connaissances | Enrichissement |
| **Discovery** | ScrapeGraphAI decouvre de nouveaux patterns d'extraction | Exploration |

Le Data Hunter dispose aussi d'une version **resiliente** avec circuit breaker, retry exponentiel, cache multi-niveaux, et fallback automatique entre sources.

### Sources de donnees — 18+ APIs integrees

| Source | Type | Auth requise |
|--------|------|:------------:|
| **SIRENE** | Entreprises francaises (11M+) | Non |
| **BODACC** | Annonces legales | Non |
| **BOAMP** | Marches publics | Non |
| **INSEE Local** | Statistiques regionales | Oui (gratuit) |
| **France Travail** | Offres d'emploi | Oui (OAuth2) |
| **DVF** | Transactions immobilieres | Non |
| **BAN** | Geocodage adresses | Non |
| **RNA** | Associations | Non |
| **Subventions** | Aides territoriales | Non |
| **OFGL** | Finances locales collectivites | Non |
| **MELODI** | Donnees douanieres | Non |
| **GDELT** | Evenements mondiaux | Non |
| **DBNomics** | Donnees macroeconomiques | Non |
| **Google News** | Actualites | Non |
| **CommonCrawl** | Archive web | Non |
| **PyTrends** | Tendances Google | Non |
| **RSS Enhanced** | News temps reel | Non |
| **Wikipedia** | Pageviews (interet public) | Non |

### Dashboard — 15+ pages

- **Chat IA** — Questions en langage naturel (WebSocket temps reel, historique de conversations)
- **Cockpit territorial** — Radar 6 axes, heatmaps, flux Sankey
- **Analytics** — Timeseries BODACC, repartition sectorielle, predictions
- **Investigation** — Cartographie des relations inter-entreprises (graphe interactif), analyse de reseau, score ecosysteme
- **Decisions** — Matrice d'impact, stakeholders RACI, graphe de relations
- **Signaux** — Detection d'anomalies et micro-signaux (ML)
- **News Intelligence** — Analyse et enrichissement croise des actualites
- **Web Intelligence** — Crawling adaptatif de sources configurables (Crawl Intel)
- **Departements** — Classement, detail par departement, scoring EPCI
- **Comparaison** — Benchmarking entre territoires
- **Fine-tuning** — Pipeline d'amelioration continue (LoRA, LLM-as-Judge)
- **Predictions** — Modeles ML avec feature importance et outliers
- **Sources** — Gestion et statut des sources de donnees
- **Alertes** — Systeme de veille automatisee

### TUI — Interface terminal avancee

En plus du dashboard web, Tawiza propose une **TUI** (Terminal User Interface) complete avec Textual :

- **Carte de France interactive** avec classement des departements
- **Charts en terminal** (sparklines, gauges, barres) via Plotext
- **Ecran TAJINE** — Dialogue avec l'agent directement en terminal
- **Dashboard temps reel** — Metriques, statut des services, logs
- **GPU Monitor** — Suivi VRAM/utilisation en temps reel
- **Session recorder** — Enregistrement et replay de sessions
- **Autocompletion dynamique** — Contextuelle selon l'etat du systeme

```bash
# Lancer la TUI
tawiza   # CLI v2 avec TUI Textual
```

### Analyse territoriale

- **6 axes** : Infrastructure, Capital humain, Innovation, Export, Investissement, Durabilite
- **Simulation Monte Carlo** + modelisation agent-based (menages, entreprises)
- **Scoring multi-facteurs** avec analyse d'attractivite territoriale
- **Ecocartographe** — Cartographie automatique des ecosystemes territoriaux
- **Detection de points focaux** et analyse de reseau

### Knowledge Graph (Neo4j)

Tawiza construit un **graphe de connaissances** territorial avec Neo4j :

- Relations entreprises-dirigeants-territoires-secteurs
- Detection de gaps (relations manquantes, donnees obsoletes, entites incompletes)
- Algorithmes de centralite, detection de communautes, similarite
- Synchronisation batch avec file d'attente

### Systeme multi-agents (CAMEL)

Pour les analyses complexes, Tawiza orchestre une **workforce** de 11 agents specialises :

Analyst, Business Plan, Comparison, Data, Finance, Geo, Prospection, Simulation, Veille, Web, et un Orchestrateur qui coordonne le tout.

### Browser Automation & Crawling

Trois backends de navigation stealth pour le scraping avance :

- **Camoufox** — Firefox modifie avec fingerprint C++ (anti-detection)
- **Nodriver** — Chrome CDP stealth
- **BrowserUse** — Agent browser LLM-driven

Plus un **crawler adaptatif** avec :
- Scheduling intelligent (Multi-Armed Bandit)
- Pool de proxies et rotation de headers
- Workers HTTPX (rapide) + Playwright (JS rendering)
- Rate limiting par domaine

### Veille automatisee (Watcher)

Systeme de surveillance continue avec pollers specialises :
- **BOAMP** — Nouveaux marches publics
- **BODACC** — Annonces legales (faillites, creations)
- **GDELT** — Evenements mondiaux impactant les territoires
- Notifications et alertes configurables

### Investigation & Risk Analysis

- **Raisonnement bayesien** pour l'investigation d'entites
- **Extraction de signaux** et detection d'anomalies
- **Scoring de risque multi-facteurs** avec explications
- **Analyse de credibilite** des sources
- **Cascade model** pour la propagation d'impacts

### Active Learning & Fine-tuning

Pipeline d'amelioration continue du LLM :
- **Drift detection** — Detecte quand le modele se degrade
- **Feedback loop** — Les retours utilisateurs alimentent le retraining
- **LoRA/QLoRA** — Fine-tuning efficace avec PEFT
- **DPO/GRPO** — Alignement via TRL
- **LLM-as-Judge** — Evaluation automatique de la qualite
- **MLflow** — Tracking des experiences

### Code Execution Sandbox

Pour l'analyse exploratoire, Tawiza integre des environnements d'execution isoles :
- **E2B** — Sandbox cloud
- **Open Interpreter** — Execution locale

### MCP Server

Tawiza expose un serveur **MCP** (Model Context Protocol) avec 12 outils :
benchmark, browser, business plan, comparison, dashboard, analyse granulaire, vue macro, prospection, simulation, veille, recherche web, et coordination workforce.

---

## Quick Start

### Prerequis

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose

### En 5 commandes

```bash
# Cloner
git clone https://github.com/hamidedefr/tawiza.git && cd tawiza

# Services (PostgreSQL + Redis)
docker compose up -d db redis

# Backend
python -m venv .venv && source .venv/activate
pip install -e ".[dev]"
cp .env.example .env && alembic upgrade head
uvicorn src.interfaces.api.main:app --reload --port 8000

# Frontend (dans un autre terminal)
cd frontend && npm install && cp .env.local.example .env.local
npm run dev
```

Backend : http://localhost:8000/docs | Frontend : http://localhost:3000

### Avec Docker Compose (tout-en-un)

```bash
git clone https://github.com/hamidedefr/tawiza.git && cd tawiza
cp .env.example .env
docker compose up -d
```

### Modeles LLM

Tawiza supporte **trois modes** pour le LLM — choisissez celui qui vous convient :

#### Option 1 : Ollama (local, gratuit)

Ideal pour la vie privee et le controle total. Fonctionne avec **NVIDIA (CUDA)** et **AMD (ROCm)**.

```bash
# Installer Ollama
curl -fsSL https://ollama.ai/install.sh | sh
```

| Modele | Role | VRAM | Commande |
|--------|------|------|----------|
| `qwen2.5:7b` | Chat par defaut, contextualisation | ~5 Go | `ollama pull qwen2.5:7b` |
| `nomic-embed-text` | Embeddings (pgvector, RAG) | ~300 Mo | `ollama pull nomic-embed-text` |
| `qwen3.5:27b` | Agent TAJINE, analyses complexes | ~17 Go | `ollama pull qwen3.5:27b` |
| `qwen3:8b` | Resumes, syntheses | ~5 Go | `ollama pull qwen3:8b` |

**Minimum** : `qwen2.5:7b` + `nomic-embed-text` (~5 Go VRAM).
**Recommande** : ajouter `qwen3.5:27b` pour des analyses TAJINE de qualite (~17 Go VRAM, GPU 24 Go+).

> **GPU AMD (ROCm)** : Ollama supporte nativement ROCm. Assurez-vous d'installer la version avec le backend ROCm (`ollama-linux-amd64-rocm`). Teste avec RX 7900 XTX.
>
> **GPU NVIDIA (CUDA)** : Ollama detecte automatiquement CUDA. Aucune configuration supplementaire necessaire.
>
> **CPU uniquement** : Fonctionne aussi, mais plus lent. Privilegiez les petits modeles (7b).

#### Option 2 : LLM cloud (Groq, OpenRouter)

Si vous n'avez pas de GPU ou preferez le cloud. Tawiza utilise un **fallback chain** : Ollama -> Groq -> OpenRouter.

```bash
# Dans .env
GROQ_API_KEY=gsk_...          # Gratuit (rate-limited)
OPENROUTER_API_KEY=sk-or-...  # Payant, large choix de modeles
```

#### Option 3 : API Claude (recommande pour la qualite)

Pour les meilleurs resultats d'analyse, utilisez [Claude](https://docs.anthropic.com/en/docs/about-claude/models) via l'API Anthropic ou un proxy OpenAI-compatible.

```bash
# Dans .env — via OpenRouter (compatible OpenAI)
OPENROUTER_API_KEY=sk-or-...
# Le modele Claude sera automatiquement disponible via OpenRouter
```

> Les modeles sont configurables via les variables d'environnement `OLLAMA__DEFAULT_MODEL` et `OLLAMA__EMBEDDING_MODEL` dans `.env`.

---

## Architecture

<!-- Architecture diagram (Excalidraw) -->
<p align="center">
  <img width="750" alt="Tawiza Architecture Diagram" src="https://github.com/user-attachments/assets/a0a8d145-ed6a-4803-9fb4-fd10271d5e42" style="border-radius: 12px;" />
</p>

> [Ouvrir le diagramme interactif sur Excalidraw](https://excalidraw.com/#json=ExdBrD05gBN8pVe48EI3D,0dlRnvFQ86n0uw451FsiWQ)

Le diagramme illustre les **6 couches** de la plateforme et comment elles interagissent :

1. **Interfaces** — 5 points d'entree : dashboard web (Next.js 14), TUI terminal (Textual), CLI (Typer), WebSocket temps reel, et serveur MCP pour les agents externes. Toutes communiquent avec l'API via REST ou WebSocket.

2. **API Layer (FastAPI)** — 40+ endpoints REST avec authentification JWT, middleware de securite (rate limiting, CORS, request ID), streaming SSE pour les reponses longues de TAJINE, et tracing distribue OpenTelemetry.

3. **Application** — Les services metier orchestrent les cas d'usage : intelligence territoriale (scoring 6 axes), news intelligence (enrichissement croise d'actualites), moteur de relations inter-entreprises, scoring de risque multi-facteurs, et score d'ecosysteme territorial.

4. **Agents Cognitifs** — Le coeur intelligent de Tawiza. L'agent **TAJINE** suit le cycle PPDSL (Perceive-Plan-Delegate-Synthesize-Learn) avec 5 niveaux cognitifs et RAG. Le **Data Hunter** collecte proactivement les donnees via 4 strategies (hypotheses LLM, bandits UCB1, expansion de graphe, discovery IA). La **CAMEL Workforce** orchestre 11 agents specialises. Le **Browser Stealth** automatise la navigation avec 3 backends anti-detection. Le **Crawler Adaptatif** planifie les crawls via Multi-Armed Bandit. Le **Watcher** surveille en continu BOAMP, BODACC et GDELT.

5. **Sources & ML** — A gauche, les 18+ sources de donnees gouvernementales et publiques (SIRENE, BODACC, BOAMP, INSEE, DVF, France Travail, GDELT...). A droite, l'infrastructure ML : fine-tuning LoRA/QLoRA, active learning avec drift detection, knowledge graph Neo4j, recherche semantique (Qdrant + pgvector), tracking MLflow, et sandbox d'execution de code (E2B).

6. **Storage & LLM** — La couche de persistance : PostgreSQL avec pgvector pour le stockage relationnel et vectoriel, Redis pour le cache multi-niveaux, Neo4j pour le graphe de connaissances, Qdrant pour la recherche semantique haute performance. Cote LLM : Ollama en local (GPU NVIDIA/AMD), avec fallback vers Groq (gratuit) et OpenRouter (cloud multi-modeles).

L'architecture suit le pattern **hexagonal** (ports & adapters) avec une separation claire :
- `src/domain/` — Entites, value objects, events (zero dependance externe)
- `src/application/` — Services, use cases, DTOs, ports
- `src/infrastructure/` — Adapters (DB, APIs, LLM, agents, crawlers)
- `src/interfaces/` — API REST, WebSocket, middleware

Voir [docs/architecture.md](docs/architecture.md) pour les details.

---

## Tech Stack

| Couche | Technologies |
|--------|-------------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy (async), Alembic |
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| **TUI** | Textual, Plotext, Rich |
| **Visualisation** | Recharts, D3.js, Plotly, Leaflet (carte interactive) |
| **Base de donnees** | PostgreSQL 17 + pgvector |
| **Knowledge Graph** | Neo4j |
| **Recherche semantique** | Qdrant, pgvector |
| **Cache** | Redis (multi-niveaux) |
| **LLM** | Ollama (local), Groq, OpenRouter, Claude API |
| **ML** | scikit-learn, PEFT (LoRA), TRL (DPO/GRPO), MLflow |
| **Web Scraping** | Crawl4AI, Playwright, Camoufox, ScrapeGraphAI |
| **Browser Automation** | BrowserUse, Nodriver, Camoufox |
| **Monitoring** | Prometheus, Grafana, Langfuse, OpenTelemetry |
| **Tests** | pytest, pytest-asyncio |

---

## Configuration

Toute la configuration passe par des variables d'environnement. Voir [docs/configuration.md](docs/configuration.md) pour la reference complete.

Variables essentielles :

```bash
DATABASE_URL=postgresql+asyncpg://tawiza:VOTRE_MOT_DE_PASSE@localhost:5433/tawiza
REDIS_URL=redis://localhost:6380/0
OLLAMA_BASE_URL=http://localhost:11434    # Optionnel
SECRET_KEY=CHANGEZ_MOI_EN_PRODUCTION     # Obligatoire
```

> Les ports sont volontairement non-standard (5433, 6380, 3003) pour eviter les conflits. C'est un choix, pas un bug.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Installation detaillee |
| [Architecture](docs/architecture.md) | Structure du projet |
| [Configuration](docs/configuration.md) | Variables d'environnement |
| [Data Sources](docs/data-sources.md) | Catalogue des 18+ APIs |
| [API Reference](docs/api-reference.md) | Endpoints REST & WebSocket |
| [Self-Hosting](docs/self-hosting.md) | Guide de deploiement |
| [Contributing](CONTRIBUTING.md) | Guide de contribution |
| [Security](SECURITY.md) | Politique de securite |

---

## Contribuer

Les contributions sont les bienvenues ! Que ce soit un bug fix, une nouvelle source de donnees, ou une amelioration du dashboard.

```bash
# Fork, clone, branch
git checkout -b feat/ma-feature

# Coder, tester
pytest tests/ -v
ruff check src/

# PR !
```

Consultez le [guide de contribution](CONTRIBUTING.md) pour les details. Les issues [`good first issue`](https://github.com/hamidedefr/tawiza/labels/good%20first%20issue) sont un bon point de depart.

---

## Roadmap

- [ ] Internationalisation (i18n) du frontend
- [ ] API GraphQL en complement du REST
- [ ] Plugin system pour les sources de donnees communautaires
- [ ] Mode offline avec cache local des APIs
- [ ] Application mobile (React Native)
- [ ] Integration Jupyter Notebook pour l'analyse exploratoire

---

## Communaute

- [GitHub Discussions](https://github.com/hamidedefr/tawiza/discussions) — Questions, idees, retours
- [Issues](https://github.com/hamidedefr/tawiza/issues) — Bugs et feature requests

---

## License

[MIT](LICENSE) — Faites-en ce que vous voulez, mais gardez la mention.

---

<p align="center">
  <i>Fait avec du cafe, des donnees ouvertes, et une pointe d'obstination.</i>
  <br>
  <sub>L'intelligence territoriale pour tous — pas juste pour ceux qui ont le budget.</sub>
</p>
