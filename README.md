<div align="center">

```
           """
           >>=========================================================<<
           ||                                                         ||
           ||  T)tttttt   A)aa   W)      ww I)iiii Z)zzzzzz   A)aa    ||
           ||     T)     A)  aa  W)      ww   I)         Z)  A)  aa   ||
           ||     T)    A)    aa W)  ww  ww   I)       Z)   A)    aa  ||
           ||     T)    A)aaaaaa W)  ww  ww   I)      Z)    A)aaaaaa  ||
           ||     T)    A)    aa W)  ww  ww   I)    Z)      A)    aa  ||
           ||     T)    A)    aa  W)ww www  I)iiii Z)zzzzzz A)    aa  ||
           ||                                                         ||
           >>=========================================================<<
           """
```

### Intelligence territoriale open source

**Tawiza** (ⵜⴰⵡⵉⵣⴰ) - mot amazigh signifiant *entraide collective*.

[![Status: Beta](https://img.shields.io/badge/Status-Beta-orange?style=flat-square)](#etat-du-projet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)

</div>

> Ce projet est développé par un dev solo en parallèle d'un stage.
> Certaines features marchent, d'autres sont en construction.
> Le README décrit l'état réel, pas la vision finale.

---

## En bref

Tawiza collecte des données depuis les APIs gouvernementales françaises et les organise pour analyser les territoires. Le backend interroge une vingtaine de sources (SIRENE, BODACC, DVF, INSEE, France Travail...), et un agent IA (TAJINE) peut synthétiser les résultats.

**Stack** : Python/FastAPI + Next.js + PostgreSQL + Redis. LLM via Ollama (local) ou cloud (Groq, OpenRouter).

---

## État du projet

| Module | État | Note |
|--------|:----:|------|
| Dashboard web (7 pages) | En cours | Interface fonctionnelle, pas tout stable |
| API REST | En cours | Endpoints TAJINE, conversations, export, sources |
| Sources de données (~19 adaptateurs) | En cours | SIRENE, BODACC, DVF, INSEE, France Travail, etc. Code présent, pas tout testé |
| Agent TAJINE (cycle PPDSL) | En cours | 5 niveaux définis, résultats dépendant du LLM |
| Data Hunter (collecte) | En cours | Stratégies bandit et discovery à tester |
| Crawler adaptatif | En cours | Scheduling MAB, workers HTTPX + Playwright |
| CLI / TUI | En cours | Pas fonctionnel à 100% |
| Knowledge Graph (Neo4j) | Présent | Nécessite Neo4j en infra |
| Fine-tuning (LoRA/DPO) | Présent | Nécessite GPU et MLflow |
| Veille (Watcher) | Présent | Pollers BOAMP, BODACC, GDELT |

**Légende** : *En cours* = code présent, stabilisation en cours. *Présent* = code réel, nécessite configuration/infra spécifique.

---

## Sources de données

19 adaptateurs codés. Les sources sans auth sont utilisables directement, les autres nécessitent des clés API gratuites.

<details>
<summary>Liste des sources</summary>

| Source | Description | Auth |
|--------|------------|:----:|
| SIRENE | Entreprises françaises (11M+) | Non |
| BODACC | Annonces légales | Non |
| BOAMP | Marchés publics | Non |
| INSEE Local | Statistiques régionales | Oui (gratuit) |
| France Travail | Offres d'emploi | Oui (OAuth2) |
| DVF | Transactions immobilières | Non |
| BAN | Géocodage adresses | Non |
| RNA | Associations | Non |
| Subventions | Aides territoriales | Non |
| OFGL | Finances locales | Non |
| MELODI | Données douanières | Oui |
| GDELT | Événements mondiaux | Non |
| DBNomics | Données macroéconomiques | Non |
| Google News | Actualités | Non |
| CommonCrawl | Archive web | Non |
| PyTrends | Tendances Google | Non |
| RSS Enhanced | News temps réel | Non |
| Wikipedia | Pageviews | Non |
| Geo API | Communes, départements | Non |

</details>

---

## Agent TAJINE

L'agent TAJINE suit le cycle PPDSL (Perceive-Plan-Delegate-Synthesize-Learn) avec 5 niveaux :

| Niveau | Capacité |
|--------|----------|
| Discovery | Extraction factuelle |
| Causal | Analyse causale (DAG) |
| Scenario | Simulation Monte Carlo |
| Strategy | Recommandations |
| Theoretical | Principes généraux |

> L'agent est en cours de simplification. Les résultats dépendent du modèle LLM et ne sont pas garantis.

---

## Quick Start

### Prérequis

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose

### Installation

```bash
git clone https://github.com/tawiza/tawiza.git && cd tawiza

# Services (PostgreSQL + Redis)
docker compose up -d postgres redis

# Backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env && alembic upgrade head
uvicorn src.interfaces.api.main:app --reload --port 8000

# Frontend (autre terminal)
cd frontend && npm install && cp .env.local.example .env.local
npm run dev
```

Backend : http://localhost:8000/docs | Frontend : http://localhost:3000

### Avec Docker Compose

```bash
git clone https://github.com/tawiza/tawiza.git && cd tawiza
cp .env.example .env
docker compose up -d
```

<details>
<summary>Configuration LLM</summary>

Trois options :

**Ollama (local, gratuit)** - fonctionne avec NVIDIA (CUDA) et AMD (ROCm) :
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

**Cloud (Groq/OpenRouter)** - dans `.env` :
```bash
GROQ_API_KEY=gsk_...          # gratuit, rate-limited
OPENROUTER_API_KEY=sk-or-...  # payant
```

**Claude API via OpenRouter** - pour les meilleurs résultats d'analyse.

Fallback chain : Ollama -> Groq -> OpenRouter.

</details>

---

## Architecture

```
src/
├── domain/          # Entités, value objects, events
├── application/     # Services, use cases, DTOs
├── infrastructure/  # Adapters (DB, APIs, LLM, agents, crawlers)
└── interfaces/      # API REST, WebSocket, middleware
```

Architecture hexagonale (ports & adapters).

<details>
<summary>Tech stack</summary>

| Couche | Technologies |
|--------|-------------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async), Alembic |
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui |
| BDD | PostgreSQL 17 + pgvector |
| Cache | Redis |
| LLM | Ollama (local), Groq, OpenRouter |
| Monitoring | Prometheus, Grafana |
| Tests | pytest, pytest-asyncio |

</details>

---

## Télémétrie

Tawiza collecte des données de télémétrie anonymes via PostHog (EU) pour améliorer la plateforme. Opt-out :

```bash
TELEMETRY_ENABLED=false  # dans .env
```

Aucune IP, email, contenu de chat ou donnée d'entreprise n'est collectée. Code source : [`src/core/telemetry.py`](src/core/telemetry.py).

---

## Documentation

| Document | Description |
|----------|-------------|
| [Docker Quick Start](docs/docker-quickstart.md) | Démarrage rapide avec Docker Compose |
| [Getting Started](docs/getting-started.md) | Installation détaillée |
| [Architecture](docs/architecture.md) | Structure du projet |
| [Configuration](docs/configuration.md) | Variables d'environnement |
| [Data Sources](docs/data-sources.md) | Catalogue des sources |
| [API Reference](docs/api-reference.md) | Endpoints REST |
| [Self-Hosting](docs/self-hosting.md) | Guide de déploiement |
| [Contributing](CONTRIBUTING.md) | Guide de contribution |

---

## Contribuer

Les contributions sont les bienvenues.

```bash
git checkout -b feat/ma-feature
pytest tests/ -v
ruff check src/
```

Voir le [guide de contribution](CONTRIBUTING.md). Les issues [`good first issue`](https://github.com/tawiza/tawiza/labels/good%20first%20issue) sont un bon point de départ.

---

## Licence

[MIT](LICENSE)

---

<div align="center">

*Fait avec du café et des données ouvertes.*

</div>
