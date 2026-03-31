🇬🇧 English | [🇫🇷 Français](README.fr.md)

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

### Open source territorial intelligence

**Tawiza** (ⵜⴰⵡⵉⵣⴰ) - Amazigh word meaning *collective mutual aid*.

[![Status: Beta](https://img.shields.io/badge/Status-Beta-orange?style=flat-square)](#project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![CI](https://img.shields.io/github/actions/workflow/status/tawiza/tawiza/ci.yml?style=flat-square&label=CI)](https://github.com/tawiza/tawiza/actions)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](https://github.com/tawiza/tawiza/blob/main/CONTRIBUTING.md)
[![Good First Issues](https://img.shields.io/github/issues/tawiza/tawiza/good%20first%20issue?style=flat-square&label=good%20first%20issues&color=7057ff)](https://github.com/tawiza/tawiza/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)

</div>

> This project is developed by a solo dev alongside an internship.
> Some features work, others are under construction.
> This README describes the actual state, not the final vision.

---

## In a nutshell

Tawiza collects data from French government APIs and organizes it to analyze territories. The backend queries about twenty sources (SIRENE, BODACC, DVF, INSEE, France Travail...), and an AI agent (TAJINE) can synthesize the results.

**Stack**: Python/FastAPI + Next.js + PostgreSQL + Redis. LLM via Ollama (local) or cloud (Groq, OpenRouter).

---

## Project status

| Module | Status | Note |
|--------|:------:|------|
| Web dashboard (7 pages) | WIP | Functional interface, not fully stable |
| REST API | WIP | TAJINE endpoints, conversations, export, sources |
| Data Sources (~19 adapters) | WIP | SIRENE, BODACC, DVF, INSEE, France Travail, etc. Code present, not all tested |
| TAJINE Agent (PPDSL cycle) | WIP | 5 levels defined, results depend on the LLM |
| Data Hunter (collection) | WIP | Bandit and discovery strategies to test |
| Adaptive Crawler | WIP | MAB scheduling, HTTPX + Playwright workers |
| CLI / TUI | WIP | Not 100% functional |
| Knowledge Graph (Neo4j) | Present | Requires Neo4j infrastructure |
| Fine-tuning (LoRA/DPO) | Present | Requires GPU and MLflow |
| Watcher (monitoring) | Present | BOAMP, BODACC, GDELT pollers |

**Legend**: *WIP* = code present, stabilization in progress. *Present* = real code, requires specific configuration/infrastructure.

---

## Data Sources

19 coded adapters. Sources without auth can be used directly, others require free API keys.

<details>
<summary>Source list</summary>

| Source | Description | Auth |
|--------|------------|:----:|
| SIRENE | French businesses registry (11M+) | No |
| BODACC | Legal announcements (company filings) | No |
| BOAMP | Public procurement notices | No |
| INSEE Local | Regional statistics | Yes (free) |
| France Travail | Job listings (French public employment service) | Yes (OAuth2) |
| DVF | Real estate transactions | No |
| BAN | Address geocoding | No |
| RNA | Associations registry | No |
| Subventions | Territorial subsidies | No |
| OFGL | Local government finances | No |
| MELODI | Customs data | Yes |
| GDELT | Global events | No |
| DBNomics | Macroeconomic data | No |
| Google News | News | No |
| CommonCrawl | Web archive | No |
| PyTrends | Google Trends | No |
| RSS Enhanced | Real-time news | No |
| Wikipedia | Pageviews | No |
| Geo API | Municipalities, departments | No |

</details>

---

## TAJINE Agent

The TAJINE agent follows the PPDSL cycle (Perceive-Plan-Delegate-Synthesize-Learn) with 5 levels:

| Level | Capability |
|-------|-----------|
| Discovery | Factual extraction |
| Causal | Causal analysis (DAG) |
| Scenario | Monte Carlo simulation |
| Strategy | Recommendations |
| Theoretical | General principles |

> The agent is being simplified. Results depend on the LLM model and are not guaranteed.

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

# Frontend (separate terminal)
cd frontend && npm install && cp .env.local.example .env.local
npm run dev
```

Backend: http://localhost:8000/docs | Frontend: http://localhost:3000

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

**Cloud (Groq/OpenRouter)** - in `.env`:
```bash
GROQ_API_KEY=gsk_...          # free, rate-limited
OPENROUTER_API_KEY=sk-or-...  # paid
```

**Claude API via OpenRouter** - for the best analysis results.

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
|-------|-------------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async), Alembic |
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui |
| Database | PostgreSQL 17 + pgvector |
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

No IP, email, chat content, or business data is collected. Source code: [`src/core/telemetry.py`](src/core/telemetry.py).

---

## Documentation

| Document | Description |
|----------|-------------|
| [Docker Quick Start](docs/docker-quickstart.md) | Quick start with Docker Compose |
| [Getting Started](docs/getting-started.md) | Detailed installation guide |
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
git checkout -b feat/my-feature
pytest tests/ -v
ruff check src/
```

See the [contribution guide](CONTRIBUTING.md). Issues labeled [`good first issue`](https://github.com/tawiza/tawiza/labels/good%20first%20issue) are a good starting point.

---

## License

[MIT](LICENSE)

---

<div align="center">

*Made with coffee and open data.*

</div>
