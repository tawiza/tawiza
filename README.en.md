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
### Open Source Territorial Intelligence

**Tawiza** (ⵜⴰⵡⵉⵣⴰ) - Amazigh word meaning *collective mutual aid*.

[![Status: Beta](https://img.shields.io/badge/Status-Beta-orange?style=flat-square)](#etat-du-projet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)

</div>

> This project is developed by a solo developer alongside an internship.
> Some features are working, others are still under construction.
> This README reflects the current state of the project, not the final vision.

---

## Overview

Tawiza collects data from French government APIs and organizes it to analyze territories. The backend queries around twenty sources (SIRENE, BODACC, DVF, INSEE, France Travail, etc.), and an AI agent (TAJINE) can synthesize the results.

**Stack** : Python/FastAPI + Next.js + PostgreSQL + Redis. LLM via Ollama (local) or cloud (Groq, OpenRouter).

---

## Project Status

| Module | Status | Notes |
|--------|:----:|------|
| Web dashboard (7 pages) | In progress | Functional interface, not fully stable |
| REST API | In progress | Endpoints TAJINE, conversations, export, sources |
| Data sources (~19 adapters) | In progress | SIRENE, BODACC, DVF, INSEE, France Travail, etc. Code exists, not fully tested |
| TAJINE Agent (PPDSL cycle) | In progress | 5 levels defined, results depend on the LLM |
| Data Hunter (collection) | In progress | Bandit and discovery strategies to be tested |
| Adaptive crawler | In progress | MAB scheduling, HTTPX + Playwright workers |
| CLI / TUI | In progress | Not 100% functional |
| Knowledge Graph (Neo4j) | Available | Requires Neo4j infrastructure |
| Fine-tuning (LoRA/DPO) | Available | Requires GPU and MLflow|
| Monitoring (Watcher) | Available | BOAMP, BODACC, GDELT pollers |

**Legend** : *In progress* = code is present, stabilization ongoing. *Available* = actual code exists, requires specific configuration/infrastructure.

---

## Data Sources

19 adapters implemented. Sources without authentication can be used directly, while others require free API keys.

<details>
<summary>List of sources</summary>

| Source | Description | Auth |
|--------|------------|:----:|
| SIRENE | French companies (11M+) | No |
| BODACC | Legal announcements | No |
| BOAMP | Public procurement | No |
| INSEE Local | Regional statistics | Yes (free) |
| France Travail | Job listings | Yes (OAuth2) |
| DVF | Real estate transactions | No |
| BAN | Address geocoding | No |
| RNA | Associations | No |
| Subventions | Territorial grants | No |
| OFGL | Local finances | No |
| MELODI | Customs data | Yes |
| GDELT | Global events | No |
| DBNomics | Macroeconomic data | No |
| Google News | News | No |
| CommonCrawl | Web archive | No |
| PyTrends | Google trends | No |
| RSS Enhanced | Real-time news | No |
| Wikipedia | Pageviews | No |
| Geo API | Municipalities, departments | No |

</details>

---

## TAJINE Agent

The TAJINE agent follows the PPDSL cycle (Perceive-Plan-Delegate-Synthesize-Learn) with 5 levels:

| Level | Capability |
|--------|----------|
| Discovery | Factual extraction |
| Causal | Causal analysis (DAG) |
| Scenario | Monte Carlo simulation |
| Strategy | Recommendations |
| Theoretical | General principles |

> The agent is currently being simplified. Results depend on the LLM model and are not guaranteed.

---

## Quick Start

### Prerequisites

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

# Frontend (another terminal)
cd frontend && npm install && cp .env.local.example .env.local
npm run dev
```

Backend : http://localhost:8000/docs | Frontend : http://localhost:3000

### With Docker Compose

```bash
git clone https://github.com/tawiza/tawiza.git && cd tawiza
cp .env.example .env
docker compose up -d
```

<details>
<summary>LLM Configuration</summary>

Three options:

**Ollama (local, free)** - works with NVIDIA (CUDA) and AMD (ROCm):
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

**Cloud (Groq/OpenRouter)** - in `.env` :
```bash
GROQ_API_KEY=gsk_...          # free, rate-limited
OPENROUTER_API_KEY=sk-or-...  # paid
```

**Claude API via OpenRouter** -  for best analysis results.

Fallback chain: Ollama -> Groq -> OpenRouter.

</details>

---

## Architecture

```
src/
├── domain/          # Entities, value objects, events
├── application/     # Services, use cases, DTOs
├── infrastructure/  # Adapters (DB, APIs, LLM, agents, crawlers)
└── interfaces/      # REST API, WebSocket, middleware
```

Hexagonal architecture (ports & adapters).

<details>
<summary>Tech stack</summary>

| Layer | Technologies |
|--------|-------------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async), Alembic |
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui |
| DB | PostgreSQL 17 + pgvector |
| Cache | Redis |
| LLM | Ollama (local), Groq, OpenRouter |
| Monitoring | Prometheus, Grafana |
| Tests | pytest, pytest-asyncio |

</details>

---

## Telemetry

Tawiza collects anonymous telemetry data via PostHog (EU) to improve the platform. Opt-out:

```bash
TELEMETRY_ENABLED=false  # in .env
```

No IP address, email, chat content, or company data is collected. Source code: [`src/core/telemetry.py`](src/core/telemetry.py).

---

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Detailed installation |
| [Architecture](docs/architecture.md) | Project structure |
| [Configuration](docs/configuration.md) | Environment variables |
| [Data Sources](docs/data-sources.md) | Source catalog |
| [API Reference](docs/api-reference.md) | REST endpoints |
| [Self-Hosting](docs/self-hosting.md) | Deployment guide |
| [Contributing](CONTRIBUTING.md) | Contribution guide |

---

## Contributing

Contributions are welcome.

```bash
git checkout -b feat/ma-feature
pytest tests/ -v
ruff check src/
```

See the [contributing guide](CONTRIBUTING.md).[`good first issue`](https://github.com/tawiza/tawiza/labels/good%20first%20issue) issues are a good starting point.

---

## License

[MIT](LICENSE)

---

<div align="center">

*Made with coffee and open data.*

</div>
