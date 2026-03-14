<div align="center">

```
           """
           >>=========================================================<<
           ||                                                         ||
           ||                                                         ||
           ||  T)tttttt   A)aa   W)      ww I)iiii Z)zzzzzz   A)aa    ||
           ||     T)     A)  aa  W)      ww   I)         Z)  A)  aa   ||
           ||     T)    A)    aa W)  ww  ww   I)       Z)   A)    aa  ||
           ||     T)    A)aaaaaa W)  ww  ww   I)      Z)    A)aaaaaa  ||
           ||     T)    A)    aa W)  ww  ww   I)    Z)      A)    aa  ||
           ||     T)    A)    aa  W)ww www  I)iiii Z)zzzzzz A)    aa  ||
           ||                                                         ||
           ||                                                         ||
           >>=========================================================<<
           """
```

### Intelligence territoriale propulsée par l'IA

**Tawiza** (ⵜⴰⵡⵉⵣⴰ) — mot amazigh signifiant *entraide collective*.<br>
Parce que l'intelligence économique, c'est mieux à plusieurs.

<br>

[![CI](https://img.shields.io/badge/CI-passing-brightgreen?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/tawiza/tawiza/actions/workflows/ci.yml)
[![Status: Beta](https://img.shields.io/badge/Status-Beta-orange?style=for-the-badge)](#-etat-du-projet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Website](https://img.shields.io/badge/tawiza.fr-d97706?style=for-the-badge&logo=safari&logoColor=white)](https://tawiza.fr)

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)

<br>

<p>
  <img width="48%" alt="Dashboard Analytics" src="https://github.com/user-attachments/assets/ecc9079c-8c61-4d95-b32b-a59487238832" style="border-radius: 12px;" />
  <img width="48%" alt="Agent TAJINE" src="https://github.com/user-attachments/assets/ee96d642-5777-4d8b-98b0-28271bfcfaa3" style="border-radius: 12px;" />
</p>
<p>
  <img width="48%" alt="Cockpit Territorial" src="https://github.com/user-attachments/assets/60558f98-adba-4de0-b6e2-2ffc39fec3f3" style="border-radius: 12px;" />
</p>

</div>

> **Beta active** — Ce projet est en développement actif. L'API, le schéma de données et les fonctionnalités peuvent changer. On est preneurs de retours et de contributions !

> *Parce que scraper l'INSEE a la main, c'est so 2020.*

---

<div align="center">

## En bref

**Tawiza** est une plateforme open source d'intelligence économique et territoriale française.<br>
Elle analyse les entreprises, les territoires et les dynamiques économiques en s'appuyant sur<br>
**18+ APIs gouvernementales**, des **agents IA cognitifs**, et un **système de collecte proactive** de données.

</div>

<br>

<table align="center">
<tr>
<td align="center" width="33%">
<br>
<img src="https://img.shields.io/badge/18+-APIs_intégrées-blue?style=for-the-badge" alt="18+ APIs" />
<br><br>
<b>Données réelles</b><br>
<sub>SIRENE, BODACC, BOAMP, DVF, INSEE, France Travail... Zero mock, zero données synthétiques.</sub>
<br><br>
</td>
<td align="center" width="33%">
<br>
<img src="https://img.shields.io/badge/Agent-TAJINE-purple?style=for-the-badge" alt="Agent TAJINE" />
<br><br>
<b>IA cognitive</b><br>
<sub>Cycle PPDSL à 5 niveaux, raisonnement causal, simulation Monte Carlo, débat multi-agents.</sub>
<br><br>
</td>
<td align="center" width="33%">
<br>
<img src="https://img.shields.io/badge/Self--hosted-100%25-green?style=for-the-badge" alt="Self-hosted" />
<br><br>
<b>Souveraineté</b><br>
<sub>Self-hostable, forkable, hackable. Votre intelligence économique vous appartient.</sub>
<br><br>
</td>
</tr>
</table>

<br>

<div align="center">

[**Démarrage rapide**](#-quick-start) · [**Documentation**](#-documentation) · [**Architecture**](#-architecture) · [**Contribuer**](#-contribuer)

</div>

---

## 💡 Pourquoi Tawiza ?

- **Les données publiques françaises sont un trésor**... dispersé sur 18 APIs différentes, avec 18 formats differents, et 18 façons de paginer. On a fait le sale boulot pour vous.
- **L'IA sans données réelles, c'est de la fiction**. Tawiza ne triche pas : zero mock, zero données synthétiques. Tout vient d'APIs gouvernementales en production.
- **Analyser un territoire, ça ne devrait pas prendre 3 semaines**. Un agent IA cognitif (TAJINE) décompose votre question, collecte les données, et synthétise — pendant que vous prenez un café.
- **Self-hostable, forkable, hackable**. Votre intelligence économique vous appartient.

---

## 📊 État du projet

> Tawiza est en **bêta active**. Certains modules sont stables, d'autres en cours de développement. Le tableau ci-dessous reflète l'état réel — pas de marketing, juste la vérité.

| Module | Etat | Note |
|--------|:----:|------|
| **Dashboard web** (22 pages) | ![Stable](https://img.shields.io/badge/-Stable-brightgreen?style=flat-square) | Interface chat fonctionnelle, cockpit territorial, analytics |
| **API REST** (40+ endpoints) | ![Stable](https://img.shields.io/badge/-Stable-brightgreen?style=flat-square) | Authentification JWT, middleware de sécurité, SSE streaming |
| **Sources de données** (18+ APIs) | ![Stable](https://img.shields.io/badge/-Stable-brightgreen?style=flat-square) | SIRENE, BODACC, BOAMP, DVF, INSEE, France Travail... |
| **Agent TAJINE** (cycle PPDSL) | ![En cours](https://img.shields.io/badge/-En_cours-orange?style=flat-square) | Simplification et calibrage en cours, résultats non garantis |
| **Data Hunter** (collecte proactive) | ![En cours](https://img.shields.io/badge/-En_cours-orange?style=flat-square) | Stratégies bandit et discovery à tester selon votre cas d'usage |
| **Signaux & Decisions** | ![En cours](https://img.shields.io/badge/-En_cours-orange?style=flat-square) | Détection d'anomalies et module décisions à valider |
| **Crawler adaptatif** | ![En cours](https://img.shields.io/badge/-En_cours-orange?style=flat-square) | Scheduling MAB et workers opérationnels, stabilisation en cours |
| **CLI / TUI** (Typer + Textual) | ![En cours](https://img.shields.io/badge/-En_cours-orange?style=flat-square) | Pas encore fonctionnel à 100%, en cours de finalisation |
| **Knowledge Graph** (Neo4j) | ![Present](https://img.shields.io/badge/-Présent-blue?style=flat-square) | Code réel, nécessite Neo4j en infra |
| **Workforce CAMEL** (12 agents) | ![Present](https://img.shields.io/badge/-Présent-blue?style=flat-square) | Fonctionne, mais dépend fortement de la qualité du LLM |
| **Fine-tuning & Active Learning** | ![Present](https://img.shields.io/badge/-Présent-blue?style=flat-square) | Pipeline LoRA/DPO, nécessite GPU et configuration MLflow |
| **Veille automatisée** (Watcher) | ![Present](https://img.shields.io/badge/-Présent-blue?style=flat-square) | Pollers BOAMP, BODACC, GDELT opérationnels |
| **Investigation bayésienne** | ![Present](https://img.shields.io/badge/-Présent-blue?style=flat-square) | Raisonnement probabiliste, extraction de signaux |
| **Serveur MCP** (13 outils) | ![Present](https://img.shields.io/badge/-Présent-blue?style=flat-square) | Intégration avec agents externes via Model Context Protocol |

<sub>

**Légende :** ![Stable](https://img.shields.io/badge/-Stable-brightgreen?style=flat-square) Production-ready · ![En cours](https://img.shields.io/badge/-En_cours-orange?style=flat-square) Fonctionnel, stabilisation en cours · ![Present](https://img.shields.io/badge/-Présent-blue?style=flat-square) Code réel, nécessite configuration/infra

</sub>

---

## 🧠 Agent TAJINE — Le cerveau

L'agent TAJINE suit le cycle **PPDSL** (Perceive-Plan-Delegate-Synthesize-Learn) avec 5 niveaux cognitifs :

| Niveau | Capacité | Exemple |
|--------|----------|---------|
| **Discovery** | Extraction factuelle | *"Combien d'entreprises tech à Toulouse ?"* |
| **Causal** | Analyse causale (DAG) | *"Pourquoi le secteur BTP recule en Occitanie ?"* |
| **Scenario** | Simulation Monte Carlo | *"Et si on doublait les subventions innovation ?"* |
| **Strategy** | Recommandations stratégiques | *"Où investir pour maximiser l'emploi ?"* |
| **Theoretical** | Principes généraux | *"Quels facteurs structurels expliquent l'attractivité ?"* |

Chaque niveau s'appuie sur des modules spécialisés : raisonnement causal (DAG), simulation Monte Carlo, modélisation agent-based (ménages/entreprises), et débat multi-agents pour les questions complexes.

> **Note :** L'agent est en cours de simplification et de calibrage. Les résultats dépendent fortement du modèle LLM utilisé et ne sont pas garantis à ce stade.

---

## 🎯 Fonctionnalites

### 🔍 Data Hunter — La collecte proactive

Le **Data Hunter** est le moteur de collecte intelligent de Tawiza. Au lieu d'interroger toutes les sources à l'aveugle, il utilise 4 stratégies combinées :

| Stratégie | Méthode | Quand |
|-----------|---------|-------|
| **Hypothesis-driven** | Le LLM génère des hypothèses à valider | Questions complexes |
| **Bandit-optimized** | UCB1/LinUCB sélectionnent les meilleures sources | Mode normal |
| **Graph-expanding** | Neo4j détecte les trous dans le graphe de connaissances | Enrichissement |
| **Discovery** | ScrapeGraphAI découvre de nouveaux patterns d'extraction | Exploration |

Le Data Hunter dispose aussi d'une version **résiliente** avec circuit breaker, retry exponentiel, cache multi-niveaux, et fallback automatique entre sources.

> **Note :** Module en cours de tests. Les strategies fonctionnent mais les résultats varient selon la configuration et les sources ciblées.

<details>
<summary><b>📡 Sources de données — 18+ APIs intégrées</b></summary>
<br>

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
| **OFGL** | Finances locales collectivités | Non |
| **MELODI** | Données douanières | Non |
| **GDELT** | Événements mondiaux | Non |
| **DBNomics** | Donnees macroéconomiques | Non |
| **Google News** | Actualités | Non |
| **CommonCrawl** | Archive web | Non |
| **PyTrends** | Tendances Google | Non |
| **RSS Enhanced** | News temps réel | Non |
| **Wikipedia** | Pageviews (intérêt public) | Non |

</details>

### 📺 Dashboard — 22 pages

- **Chat IA** — Questions en langage naturel (WebSocket temps réel, historique de conversations)
- **Cockpit territorial** — Radar 6 axes, heatmaps, flux Sankey
- **Analytics** — Timeseries BODACC, répartition sectorielle, prédictions
- **Investigation** — Cartographie des relations inter-entreprises (graphe interactif), analyse de réseau, score écosystème
- **Decisions** — Matrice d'impact, stakeholders RACI, graphe de relations *(en cours de validation)*
- **Signaux** — Détection d'anomalies et micro-signaux (ML) *(en cours de validation)*
- **News Intelligence** — Analyse et enrichissement croisé des actualités
- **Web Intelligence** — Crawling adaptatif de sources configurables (Crawl Intel)
- **Départements** — Classement, détail par département, scoring EPCI
- **Comparaison** — Benchmarking entre territoires
- **Fine-tuning** — Pipeline d'amélioration continue (LoRA, LLM-as-Judge)
- **Predictions** — Modèles ML avec feature importance et outliers
- **Sources** — Gestion et statut des sources de données
- **Alertes** — Systeme de veille automatisee

<details>
<summary><b>🗺️ Analyse territoriale</b></summary>
<br>

- **6 axes** : Infrastructure, Capital humain, Innovation, Export, Investissement, Durabilité
- **Simulation Monte Carlo** + modélisation agent-based (ménages, entreprises)
- **Scoring multi-facteurs** avec analyse d'attractivité territoriale
- **Écocartographe** — Cartographie automatique des écosystèmes territoriaux
- **Détection de points focaux** et analyse de réseau

</details>

<details>
<summary><b>🕸️ Knowledge Graph (Neo4j)</b></summary>
<br>

Tawiza construit un **graphe de connaissances** territorial avec Neo4j :

- Relations entreprises-dirigeants-territoires-secteurs
- Détection de gaps (relations manquantes, données obsolètes, entités incomplètes)
- Algorithmes de centralité, détection de communautés, similarité
- Synchronisation batch avec file d'attente

</details>

<details>
<summary><b>🤖 Système multi-agents (CAMEL)</b></summary>
<br>

Pour les analyses complexes, Tawiza orchestre une **workforce** de 12 agents spécialisés :

Analyst, Business Plan, Comparison, Data, Finance, Geo, Orchestrator, Prospection, Simulation, Veille, Web, et un coordinateur général.

</details>

<details>
<summary><b>🕵️ Browser Automation & Crawling</b></summary>
<br>

Deux backends de navigation stealth pour le scraping avancé :

- **Camoufox** — Firefox modifié avec fingerprint C++ (anti-détection)
- **Nodriver** — Chrome CDP stealth

Plus un **crawler adaptatif** *(en cours de stabilisation)* avec :
- Scheduling intelligent (Multi-Armed Bandit)
- Pool de proxies et rotation de headers
- Workers HTTPX (rapide) + Playwright (JS rendering)
- Rate limiting par domaine

</details>

<details>
<summary><b>👁️ Veille automatisée (Watcher)</b></summary>
<br>

Système de surveillance continue avec pollers spécialisés :
- **BOAMP** — Nouveaux marchés publics
- **BODACC** — Annonces légales (faillites, creations)
- **GDELT** — Événements mondiaux impactant les territoires
- Notifications et alertes configurables

</details>

<details>
<summary><b>🔎 Investigation & Risk Analysis</b></summary>
<br>

- **Raisonnement bayésien** pour l'investigation d'entités
- **Extraction de signaux** et détection d'anomalies
- **Scoring de risque multi-facteurs** avec explications
- **Analyse de crédibilité** des sources
- **Cascade model** pour la propagation d'impacts

</details>

<details>
<summary><b>🧪 Active Learning & Fine-tuning</b></summary>
<br>

Pipeline d'amélioration continue du LLM :
- **Drift detection** — Détecte quand le modèle se dégrade
- **Feedback loop** — Les retours utilisateurs alimentent le retraining
- **LoRA/QLoRA** — Fine-tuning efficace avec PEFT
- **DPO/GRPO** — Alignement via TRL
- **LLM-as-Judge** — Évaluation automatique de la qualité
- **MLflow** — Tracking des expériences

</details>

<details>
<summary><b>⌨️ CLI & TUI — En cours de développement</b></summary>
<br>

Tawiza embarque une **CLI** (Typer) et une **TUI** (Textual) pour l'usage en terminal. Ces interfaces sont en cours de finalisation et ne sont pas encore fonctionnelles à 100%.

Ce qui est implémenté :
- Carte de France interactive avec classement des départements
- Charts en terminal (sparklines, gauges, barres) via Plotext
- Écran TAJINE — Dialogue avec l'agent en terminal
- Dashboard temps réel — Métriques, statut des services, logs
- GPU Monitor — Suivi VRAM/utilisation en temps réel
- Autocomplétion dynamique contextuelle

```bash
# La CLI/TUI est en cours — utilisation à vos risques
tawiza   # CLI v2 avec TUI Textual
```

</details>

<details>
<summary><b>🔌 Serveur MCP</b></summary>
<br>

Tawiza expose un serveur **MCP** (Model Context Protocol) avec 13 outils :
benchmark, browser, business plan, comparison, dashboard, analyse granulaire, vue macro, prospection, simulation, veille, recherche web, coordination workforce, et plus.

</details>

---

## 🚀 Quick Start

### Prérequis

| Outil | Version |
|-------|---------|
| Python | 3.11+ |
| Node.js | 20+ |
| Docker & Docker Compose | Dernière version stable |

### En 5 commandes

```bash
# Cloner
git clone https://github.com/tawiza/tawiza.git && cd tawiza

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

> **Backend :** http://localhost:8000/docs &nbsp;|&nbsp; **Frontend :** http://localhost:3000

### Avec Docker Compose (tout-en-un)

```bash
git clone https://github.com/tawiza/tawiza.git && cd tawiza
cp .env.example .env
docker compose up -d
```

<details>
<summary><b>🤖 Configuration des modèles LLM</b></summary>
<br>

Tawiza supporte **trois modes** pour le LLM — choisissez celui qui vous convient :

#### Option 1 : Ollama (local, gratuit)

Idéal pour la vie privée et le contrôle total. Fonctionne avec **NVIDIA (CUDA)** et **AMD (ROCm)**.

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

**Minimum** : `qwen2.5:7b` + `nomic-embed-text` (~5 Go VRAM).<br>
**Recommandé** : ajouter `qwen3.5:27b` pour des analyses TAJINE de qualité (~17 Go VRAM, GPU 24 Go+).

> **GPU AMD (ROCm)** : Ollama supporte nativement ROCm. Assurez-vous d'installer la version avec le backend ROCm (`ollama-linux-amd64-rocm`). Testé avec RX 7900 XTX.
>
> **GPU NVIDIA (CUDA)** : Ollama détecte automatiquement CUDA. Aucune configuration supplémentaire nécessaire.
>
> **CPU uniquement** : Fonctionne aussi, mais plus lent. Privilégiez les petits modèles (7b).

#### Option 2 : LLM cloud (Groq, OpenRouter)

Si vous n'avez pas de GPU ou préférez le cloud. Tawiza utilise un **fallback chain** : Ollama -> Groq -> OpenRouter.

```bash
# Dans .env
GROQ_API_KEY=gsk_...          # Gratuit (rate-limited)
OPENROUTER_API_KEY=sk-or-...  # Payant, large choix de modèles
```

#### Option 3 : API Claude (recommandé pour la qualité)

Pour les meilleurs résultats d'analyse, utilisez [Claude](https://docs.anthropic.com/en/docs/about-claude/models) via l'API Anthropic ou un proxy OpenAI-compatible.

```bash
# Dans .env — via OpenRouter (compatible OpenAI)
OPENROUTER_API_KEY=sk-or-...
# Le modèle Claude sera automatiquement disponible via OpenRouter
```

> Les modèles sont configurables via les variables d'environnement `OLLAMA__DEFAULT_MODEL` et `OLLAMA__EMBEDDING_MODEL` dans `.env`.

</details>

---

## 🏗️ Architecture

<p align="center">
  <img width="750" alt="Tawiza Architecture Diagram" src="https://github.com/user-attachments/assets/a0a8d145-ed6a-4803-9fb4-fd10271d5e42" style="border-radius: 12px;" />
</p>

Le diagramme illustre les **6 couches** de la plateforme et comment elles interagissent :

| Couche | Description |
|--------|-------------|
| **1. Interfaces** | 5 points d'entrée : dashboard web (Next.js 14), TUI terminal (Textual, en cours), CLI (Typer, en cours), WebSocket temps réel, et serveur MCP pour les agents externes. |
| **2. API Layer** | 40+ endpoints REST avec authentification JWT, middleware de sécurité (rate limiting, CORS, request ID), streaming SSE, et tracing distribué OpenTelemetry. |
| **3. Application** | Services métier : intelligence territoriale (scoring 6 axes), news intelligence, moteur de relations inter-entreprises, scoring de risque, score d'écosystème territorial. |
| **4. Agents Cognitifs** | Agent **TAJINE** (cycle PPDSL, 5 niveaux, RAG), **Data Hunter** (4 stratégies), **CAMEL Workforce** (12 agents), **Crawler Adaptatif** (MAB), **Watcher** (BOAMP, BODACC, GDELT). |
| **5. Sources & ML** | 18+ sources gouvernementales + infra ML : fine-tuning LoRA/QLoRA, active learning, knowledge graph Neo4j, recherche sémantique (Qdrant + pgvector), tracking MLflow. |
| **6. Storage & LLM** | PostgreSQL + pgvector, Redis, Neo4j, Qdrant. LLM : Ollama (GPU NVIDIA/AMD), fallback Groq et OpenRouter. |

L'architecture suit le pattern **hexagonal** (ports & adapters) :

```
src/
├── domain/          # Entités, value objects, events (zéro dépendance externe)
├── application/     # Services, use cases, DTOs, ports
├── infrastructure/  # Adapters (DB, APIs, LLM, agents, crawlers)
└── interfaces/      # API REST, WebSocket, middleware
```

> Voir [docs/architecture.md](docs/architecture.md) pour les détails.

---

<details>
<summary><h2>🔧 Tech Stack</h2></summary>
<br>

| Couche | Technologies |
|--------|-------------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy (async), Alembic |
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| **TUI** | Textual, Plotext, Rich *(en cours)* |
| **Visualisation** | Recharts, D3.js, Plotly, Leaflet (carte interactive) |
| **Base de données** | PostgreSQL 17 + pgvector |
| **Knowledge Graph** | Neo4j |
| **Recherche sémantique** | Qdrant, pgvector |
| **Cache** | Redis (multi-niveaux) |
| **LLM** | Ollama (local), Groq, OpenRouter, Claude API |
| **ML** | scikit-learn, PEFT (LoRA), TRL (DPO/GRPO), MLflow |
| **Web Scraping** | Crawl4AI, Playwright, Camoufox, ScrapeGraphAI |
| **Monitoring** | Prometheus, Grafana, Langfuse, OpenTelemetry |
| **Tests** | pytest, pytest-asyncio |

</details>

---

<details>
<summary><h2>⚙️ Configuration</h2></summary>
<br>

Toute la configuration passe par des variables d'environnement. Voir [docs/configuration.md](docs/configuration.md) pour la référence complète.

Variables essentielles :

```bash
DATABASE_URL=postgresql+asyncpg://tawiza:VOTRE_MOT_DE_PASSE@localhost:5433/tawiza
REDIS_URL=redis://localhost:6380/0
OLLAMA_BASE_URL=http://localhost:11434    # Optionnel
SECRET_KEY=CHANGEZ_MOI_EN_PRODUCTION     # Obligatoire
```

> Les ports sont volontairement non-standard (5433, 6380, 3003) pour éviter les conflits. C'est un choix, pas un bug.

</details>

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Installation détaillée |
| [Architecture](docs/architecture.md) | Structure du projet |
| [Configuration](docs/configuration.md) | Variables d'environnement |
| [Data Sources](docs/data-sources.md) | Catalogue des 18+ APIs |
| [API Reference](docs/api-reference.md) | Endpoints REST & WebSocket |
| [Self-Hosting](docs/self-hosting.md) | Guide de déploiement |
| [Télémétrie](docs/telemetry.md) | Données collectées et opt-out |
| [Contributing](CONTRIBUTING.md) | Guide de contribution |
| [Security](SECURITY.md) | Politique de sécurité |

<details>
<summary><b>Documentation des modules</b></summary>
<br>

| Module | Description | État |
|--------|-------------|:----:|
| [Agent TAJINE](docs/modules/tajine.md) | Cycle PPDSL, 5 niveaux cognitifs, configuration | En cours |
| [Data Hunter](docs/modules/data-hunter.md) | 4 stratégies de collecte, version résiliente | En cours |
| [Signaux & Anomalies](docs/modules/signaux.md) | Détection ML, pipeline de traitement | En cours |
| [Décisions](docs/modules/decisions.md) | Matrice d'impact, RACI, graphe de relations | En cours |
| [Crawler](docs/modules/crawler.md) | Scheduling MAB, backends stealth | En cours |
| [CLI & TUI](docs/modules/cli-tui.md) | Typer CLI, Textual TUI, écrans et widgets | En cours |
| [Knowledge Graph](docs/modules/knowledge-graph.md) | Neo4j, nœuds, relations, algorithmes | Présent |
| [Investigation](docs/modules/investigation.md) | Bayésien, scoring de risque, signaux | Présent |

</details>

---

## 🤝 Contribuer

Les contributions sont les bienvenues ! Que ce soit un bug fix, une nouvelle source de données, ou une amélioration du dashboard.

```bash
# Fork, clone, branch
git checkout -b feat/ma-feature

# Coder, tester
pytest tests/ -v
ruff check src/

# PR !
```

Consultez le [guide de contribution](CONTRIBUTING.md) pour les détails. Les issues [`good first issue`](https://github.com/tawiza/tawiza/labels/good%20first%20issue) sont un bon point de départ.

---

## 🗺️ Roadmap

### En cours

- [ ] Stabilisation de l'agent TAJINE (simplification, calibrage)
- [ ] Finalisation CLI & TUI (fusion v2/v3, couverture complète)
- [ ] Validation des modules Signaux et Décisions
- [ ] Stabilisation du crawler adaptatif
- [ ] Tests end-to-end du Data Hunter

### Prévu

- [ ] Internationalisation (i18n) du frontend
- [ ] Plugin system pour les sources de données communautaires
- [ ] Mode offline avec cache local des APIs
- [ ] Intégration Jupyter Notebook pour l'analyse exploratoire

### À terme

Certaines fonctionnalités actuellement separees seront fusionnees au fil du temps pour simplifier l'architecture (ex : les différentes versions du CLI, les modules redondants de collecte).

---

## 💬 Communauté

- [GitHub Discussions](https://github.com/tawiza/tawiza/discussions) — Questions, idées, retours
- [Issues](https://github.com/tawiza/tawiza/issues) — Bugs et feature requests

---

## 📄 License

[MIT](LICENSE) — Faites-en ce que vous voulez, mais gardez la mention.

---

<div align="center">

<br>

*Fait avec du café, des données ouvertes, et une pointe d'obstination.*

<sub>L'intelligence territoriale pour tous — pas juste pour ceux qui ont le budget.</sub>

<br>

</div>
