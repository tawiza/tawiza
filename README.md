```
 ████████╗ █████╗ ██╗    ██╗██╗███████╗ █████╗
 ╚══██╔══╝██╔══██╗██║    ██║██║╚══███╔╝██╔══██╗
    ██║   ███████║██║ █╗ ██║██║  ███╔╝ ███████║
    ██║   ██╔══██║██║███╗██║██║ ███╔╝  ██╔══██║
    ██║   ██║  ██║╚███╔███╔╝██║███████╗██║  ██║
    ╚═╝   ╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝╚══════╝╚═╝  ╚═╝
```

# Tawiza — Intelligence territoriale propulsée par l'IA

[![Status: Beta](https://img.shields.io/badge/Status-Beta-orange.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Website](https://img.shields.io/badge/Website-tawiza.fr-indigo.svg)](https://hamidedefr.github.io/tawiza-landing/)

> **⚠️ Beta** — Ce projet est en développement actif. L'API, le schéma de données et les fonctionnalités peuvent changer. On est preneurs de retours et de contributions !

> Parce que scraper l'INSEE à la main, c'est so 2020.

**Tawiza** est une plateforme open source d'intelligence économique et territoriale française. Elle analyse les entreprises, les territoires et les dynamiques économiques en s'appuyant sur 15+ APIs gouvernementales et des agents IA cognitifs.

> **Tawiza** (ⵜⴰⵡⵉⵣⴰ) — mot amazigh signifiant *entraide collective*. Parce que l'intelligence économique, c'est mieux à plusieurs.

---

## Pourquoi Tawiza ?

- **Les données publiques françaises sont un trésor**... dispersé sur 15 APIs différentes, avec 15 formats différents, et 15 façons de paginer. On a fait le sale boulot pour vous.
- **L'IA sans données réelles, c'est de la fiction**. Tawiza ne triche pas : zéro mock, zéro données synthétiques. Tout vient d'APIs gouvernementales en production.
- **Analyser un territoire, ça ne devrait pas prendre 3 semaines**. Un agent IA cognitif (TAJINE) décompose votre question, collecte les données, et synthétise — pendant que vous prenez un café.
- **Self-hostable, forkable, hackable**. Votre intelligence économique vous appartient.

---

## Fonctionnalités

### Agent TAJINE — Le cerveau

L'agent TAJINE suit le cycle **PPDSL** (Perceive-Plan-Delegate-Synthesize-Learn) avec 5 niveaux cognitifs :

| Niveau | Capacité | Exemple |
|--------|----------|---------|
| **Discovery** | Extraction factuelle | "Combien d'entreprises tech à Toulouse ?" |
| **Causal** | Analyse causale | "Pourquoi le secteur BTP recule en Occitanie ?" |
| **Scenario** | Simulation What-If | "Et si on doublait les subventions innovation ?" |
| **Strategy** | Recommandations | "Où investir pour maximiser l'emploi ?" |
| **Theoretical** | Principes généraux | "Quels facteurs structurels expliquent l'attractivité ?" |

### Sources de données — 15+ APIs intégrées

| Source | Type | Auth requise |
|--------|------|:------------:|
| **SIRENE** | Entreprises françaises (11M+) | Non |
| **BODACC** | Annonces légales | Non |
| **BOAMP** | Marchés publics | Non |
| **INSEE Local** | Statistiques régionales | Oui (gratuit) |
| **France Travail** | Offres d'emploi | Oui (OAuth2) |
| **DVF** | Transactions immobilières | Non |
| **BAN** | Géocodage adresses | Non |
| **RNA** | Associations | Non |
| **Subventions** | Aides territoriales | Non |
| **GDELT** | Événements mondiaux | Non |
| **DBNomics** | Données économiques | Non |
| **CommonCrawl** | Archive web | Non |
| **PyTrends** | Tendances Google | Non |
| **RSS Enhanced** | News temps réel | Non |
| **Wikipedia** | Pageviews | Non |

### Dashboard — 15+ pages

- **Chat IA** — Posez vos questions en langage naturel (WebSocket temps réel)
- **Cockpit territorial** — Radar 6 axes, heatmaps, flux Sankey
- **Analytics** — Timeseries BODACC, répartition sectorielle, prédictions
- **Investigation** — Cartographie des relations inter-entreprises (graphe)
- **Décisions** — Matrice d'impact, stakeholders RACI
- **Signaux** — Détection d'anomalies (ML)
- **Web Intelligence** — Crawling adaptatif de sources configurables
- **Départements** — Classement et détail par département
- **Comparaison** — Benchmarking entre territoires
- **Fine-tuning** — Pipeline d'amélioration continue (LLM-as-Judge)

### Analyse territoriale

- **6 axes** : Infrastructure, Capital humain, Innovation, Export, Investissement, Durabilité
- **Simulation Monte Carlo** + modélisation agent-based
- **Scoring multi-facteurs** avec analyse d'attractivité territoriale

---

## Quick Start

### Prérequis

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
python -m venv .venv && source .venv/bin/activate
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

### Modèles Ollama

Tawiza utilise [Ollama](https://ollama.ai) pour le LLM en local. Aucune donnée n'est envoyée vers le cloud.

```bash
# Installer Ollama
curl -fsSL https://ollama.ai/install.sh | sh
```

| Modèle | Rôle | VRAM | Commande |
|--------|------|------|----------|
| `qwen2.5:7b` | Chat par défaut, contextualisation | ~5 Go | `ollama pull qwen2.5:7b` |
| `nomic-embed-text` | Embeddings (pgvector, RAG) | ~300 Mo | `ollama pull nomic-embed-text` |
| `qwen3.5:27b` | Agent TAJINE, analyses complexes | ~17 Go | `ollama pull qwen3.5:27b` |
| `qwen3:8b` | Résumés, synthèses | ~5 Go | `ollama pull qwen3:8b` |

**Minimum pour démarrer** : `qwen2.5:7b` + `nomic-embed-text` (~5 Go VRAM).

**Recommandé** : ajouter `qwen3.5:27b` pour des analyses TAJINE de qualité (~17 Go VRAM, GPU 24 Go+).

> Les modèles sont configurables via les variables d'environnement `OLLAMA__DEFAULT_MODEL` et `OLLAMA__EMBEDDING_MODEL` dans `.env`.

---

## Architecture

```
                    ┌──────────────────────────────────┐
                    │       Frontend (Next.js 14)       │
                    │   Dashboard · Chat · Analytics     │
                    └───────────────┬──────────────────┘
                                    │ REST + WebSocket
                    ┌───────────────▼──────────────────┐
                    │        API Layer (FastAPI)         │
                    │   Routes · Middleware · Auth       │
                    └───────────────┬──────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
 ┌─────────▼─────────┐  ┌──────────▼──────────┐  ┌──────────▼──────────┐
 │   Application     │  │   Agent TAJINE      │  │   Data Sources      │
 │   Services        │  │   (Cycle PPDSL)     │  │   (15+ APIs)        │
 └─────────┬─────────┘  └──────────┬──────────┘  └──────────┬──────────┘
           │                        │                        │
 ┌─────────▼────────────────────────▼────────────────────────▼──────────┐
 │                        Infrastructure                                │
 │   PostgreSQL · Redis · Ollama · pgvector                            │
 └─────────────────────────────────────────────────────────────────────┘
```

L'architecture suit le pattern **hexagonal** (ports & adapters). Voir [docs/architecture.md](docs/architecture.md) pour les détails.

---

## Tech Stack

| Couche | Technologies |
|--------|-------------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy (async), Alembic |
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| **Visualisation** | Recharts, D3.js, Plotly |
| **Base de données** | PostgreSQL 17 + pgvector |
| **Cache** | Redis (multi-niveaux) |
| **LLM** | Ollama (local) avec HybridLLMRouter |
| **ML** | scikit-learn, Oumi (fine-tuning) |
| **Web Scraping** | Crawl4AI, Playwright |
| **Monitoring** | Prometheus, Grafana, Langfuse |
| **Tests** | pytest, pytest-asyncio |

---

## Configuration

Toute la configuration passe par des variables d'environnement. Voir [docs/configuration.md](docs/configuration.md) pour la référence complète.

Variables essentielles :

```bash
DATABASE_URL=postgresql+asyncpg://tawiza:changeme@localhost:5433/tawiza
REDIS_URL=redis://localhost:6380/0
OLLAMA_BASE_URL=http://localhost:11434    # Optionnel
SECRET_KEY=CHANGEZ_MOI_EN_PRODUCTION     # Obligatoire
```

> Les ports sont volontairement non-standard (5433, 6380, 3003) pour éviter les conflits. C'est un choix, pas un bug.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Installation détaillée |
| [Architecture](docs/architecture.md) | Structure du projet |
| [Configuration](docs/configuration.md) | Variables d'environnement |
| [Data Sources](docs/data-sources.md) | Catalogue des 15+ APIs |
| [API Reference](docs/api-reference.md) | Endpoints REST & WebSocket |
| [Self-Hosting](docs/self-hosting.md) | Guide de déploiement |
| [Contributing](CONTRIBUTING.md) | Guide de contribution |
| [Security](SECURITY.md) | Politique de sécurité |

---

## Contribuer

Les contributions sont les bienvenues ! Que ce soit un bug fix, une nouvelle source de données, ou une amélioration du dashboard.

```bash
# Fork, clone, branch
git checkout -b feat/ma-feature

# Coder, tester
pytest tests/ -v
ruff check src/

# PR !
```

Consultez le [guide de contribution](CONTRIBUTING.md) pour les détails. Les issues [`good first issue`](https://github.com/hamidedefr/tawiza/labels/good%20first%20issue) sont un bon point de départ.

---

## Roadmap

- [ ] Internationalisation (i18n) du frontend
- [ ] API GraphQL en complément du REST
- [ ] Plugin system pour les sources de données communautaires
- [ ] Mode offline avec cache local des APIs
- [ ] Application mobile (React Native)
- [ ] Intégration Jupyter Notebook pour l'analyse exploratoire

---

## Communauté

- [GitHub Discussions](https://github.com/hamidedefr/tawiza/discussions) — Questions, idées, retours
- [Issues](https://github.com/hamidedefr/tawiza/issues) — Bugs et feature requests

---

## License

[MIT](LICENSE) — Faites-en ce que vous voulez, mais gardez la mention.

---

<p align="center">
  <i>Fait avec du café, des données ouvertes, et une pointe d'obstination.</i>
  <br>
  <sub>L'intelligence territoriale pour tous — pas juste pour ceux qui ont le budget.</sub>
</p>
