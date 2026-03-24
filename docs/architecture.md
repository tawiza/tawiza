# Architecture de Tawiza

## Vue d'ensemble

Tawiza suit une architecture hexagonale (ports & adapters) avec séparation claire des responsabilités.

```
                    ┌─────────────────────────────────────┐
                    │           Frontend (Next.js)         │
                    │    Dashboard · Chat · Analytics       │
                    └──────────────┬──────────────────────┘
                                   │ REST + WebSocket
                    ┌──────────────▼──────────────────────┐
                    │          API Layer (FastAPI)          │
                    │     Routes · Middleware · Auth        │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
    │   Application    │ │  Agent TAJINE   │ │   Data Sources  │
    │   Services       │ │  (Cognitif)     │ │   (15+ APIs)    │
    └─────────┬────────┘ └────────┬────────┘ └────────┬────────┘
              │                    │                    │
    ┌─────────▼────────────────────▼────────────────────▼────────┐
    │                    Infrastructure                           │
    │  PostgreSQL · Redis · Ollama · pgvector                    │
    └────────────────────────────────────────────────────────────┘
```

## Couches

### Domain (`src/domain/`)

Entités métier pures sans dépendances externes :
- `Company` — Entreprise (SIREN, NAF, forme juridique)
- `Territory` — Territoire (département, région, EPCI)
- `Signal` — Signal économique (BODACC, marché public)
- `Analysis` — Résultat d'analyse territoriale

### Application (`src/application/`)

Use cases et logique métier :
- `TerritorialAnalysisService` — Orchestration des analyses
- `CompanySearchService` — Recherche et enrichissement entreprises
- `SignalDetectionService` — Détection d'anomalies et tendances

### Infrastructure (`src/infrastructure/`)

Implémentations concrètes :

#### Agents (`agents/tajine/`)

Le coeur intelligent de Tawiza. L'agent TAJINE suit le cycle PPDSL :

```
Perceive → Plan → Delegate → Synthesize → Learn
    │         │        │           │          │
    │         │        │           │          └─ Fine-tuning auto
    │         │        │           └─ Fusion des résultats
    │         │        └─ DataHunter, BrowserAgent, etc.
    │         └─ StrategicPlanner (sous-tâches)
    └─ Classification intent + contexte territorial
```

5 niveaux cognitifs :
1. **Discovery** — Extraction factuelle (qui, quoi, où)
2. **Causal** — Analyse causale (pourquoi, comment)
3. **Scenario** — Simulation what-if (et si...?)
4. **Strategy** — Recommandations optimales
5. **Theoretical** — Principes généraux et théories

#### Sources de données (`datasources/adapters/`)

Système d'adaptateurs avec :
- Cache multi-niveaux (Redis)
- Rate limiting par source
- Fallback et retry automatiques
- Health checks

#### Persistence (`persistence/`)

- SQLAlchemy async + Alembic migrations
- pgvector pour les embeddings
- Repositories pattern

### Interfaces (`src/interfaces/`)

#### API REST (`api/v1/`)

- FastAPI avec OpenAPI auto-générée
- WebSocket pour le chat temps réel
- Server-Sent Events pour le streaming
- Middleware : RequestID, ErrorHandler, Prometheus

### Frontend (`frontend/`)

- Next.js 14 App Router
- SWR pour le data fetching (revalidation automatique)
- Recharts + D3.js + Plotly pour la visualisation
- shadcn/ui + Tailwind CSS + Glassmorphism

## Flux de données typique

```
1. Utilisateur pose une question dans le chat
2. WebSocket → API → Agent TAJINE
3. TAJINE: Perceive (classifier l'intent)
4. TAJINE: Plan (décomposer en sous-tâches)
5. TAJINE: Delegate (DataHunter → SIRENE, BODACC, etc.)
6. TAJINE: Synthesize (fusionner, générer charts)
7. TAJINE: Learn (stocker pour fine-tuning)
8. Response → WebSocket → Dashboard (temps réel)
```

## Ports remarquables

| Service | Port | Note |
|---------|------|------|
| Backend API | 8000 | FastAPI |
| Frontend | 3000 | Next.js |
| PostgreSQL | 5433 | Pas 5432 (éviter conflits) |
| Redis | 6380 | Pas 6379 (éviter conflits) |
| Ollama | 11434 | LLM local |
| Grafana | 3003 | Monitoring |
