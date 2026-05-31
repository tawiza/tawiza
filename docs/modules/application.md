# Couche Application

Couche applicative de Tawiza (architecture hexagonale). Elle orchestre la logique métier entre le domaine et l'infrastructure : services, cas d'usage, ports (interfaces), DTOs, jobs planifiés, orchestration multi-sources, génération de rapports et gestion conversationnelle. Aucun accès direct aux dépendances externes - tout passe par des ports implémentés dans `src/infrastructure/`.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         src/application/                           │
│                                                                    │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────────┐     │
│  │   use_cases/   │  │    ports/    │  │       dtos/         │     │
│  │  Orchestration │─▶│  Interfaces  │  │  Requêtes/Réponses  │     │
│  │  ML (train,    │  │  (ABC/       │  │  (Pydantic/         │     │
│  │  deploy, ...)  │  │  Protocol)   │  │  dataclass)         │     │
│  └────────────────┘  └──────┬───────┘  └─────────────────────┘     │
│                             │ implémentés par infrastructure        │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │                        services/                              │  │
│  │                                                               │  │
│  │  ┌─────────────────────┐  ┌──────────────────────────────┐   │  │
│  │  │  Graphe relationnel │  │  Intelligence territoriale   │   │  │
│  │  │  extractors (L1)    │  │  department_scorer           │   │  │
│  │  │  inferrers   (L2)   │  │  ecosystem_score             │   │  │
│  │  │  predictors  (L3)   │  │  focal_point_detector        │   │  │
│  │  │  relation_service   │  │  correlation_engine          │   │  │
│  │  │  network_analytics  │  │  territorial_stats / reports │   │  │
│  │  └─────────────────────┘  └──────────────────────────────┘   │  │
│  │                                                               │  │
│  │  ┌─────────────────────┐  ┌──────────────────────────────┐   │  │
│  │  │  Pipeline news      │  │  Agents & LLM                │   │  │
│  │  │  news_sync          │  │  agent_orchestrator          │   │  │
│  │  │  news_cross_enricher│  │  autonomous_agent_service    │   │  │
│  │  │  news_scheduler     │  │  assistant_service           │   │  │
│  │  │  llm_summarizer     │  │  embedding_service           │   │  │
│  │  └─────────────────────┘  └──────────────────────────────┘   │  │
│  │                                                               │  │
│  │  ┌──────────────────────────────────────────────────────┐    │  │
│  │  │  Planification (APScheduler)                          │    │  │
│  │  │  crawler_scheduler · tajine_scheduler                 │    │  │
│  │  └──────────────────────────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  │
│  │ orchestration│  │  reporting/  │  │  jobs/   │  │conversation│  │
│  │ multi-source │  │  HTML report │  │ collecte │  │ assistant  │  │
│  └──────────────┘  └──────────────┘  └──────────┘  └────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Sous-modules

### `services/` - Logique métier

Le sous-module le plus volumineux. Les services suivent le principe de responsabilité unique et l'injection de dépendances.

#### Graphe relationnel (3 niveaux de confiance)

Le cœur de l'analyse territoriale est un graphe d'acteurs et de relations construit en trois niveaux d'abstraction croissante :

| Niveau | Fichier | `relation_type` | Confiance | Description |
|--------|---------|-----------------|-----------|-------------|
| **L1** | `relation_extractors.py` | `extracted` | élevée | Extraction factuelle depuis SIRENE, BODACC, BOAMP, RNA, subventions, EPCI, incubateurs, pôles |
| **L2** | `relation_inferrers.py` | `inferred` | `[0.40, 0.79]` | Inférence statistique (corrélations) sur les acteurs déjà persistés |
| **L3** | `relation_predictors.py` | `hypothetical` | `[0.05, 0.39]` | Prédiction de scénarios futurs et de liens probabilistes |

- `relation_service.py` : orchestrateur (`RelationService`) exposant `discover()`, `get_graph()` (payload D3.js), `get_coverage()` et `get_gaps()`. Utilise les registres `EXTRACTORS`, `INFERRERS`, `PREDICTORS`.
- `cascade_model.py` : régression logistique légère prédisant la probabilité de cascade (remplace l'heuristique `propagation_factor * confidence * 0.5`), avec repli heuristique si scikit-learn est indisponible.
- `network_analytics_service.py` : métriques de graphe via NetworkX (centralité, détection de communautés, résilience, trous structurels, approximation de Shapley, scoring de risque par acteur).

Les acteurs et relations utilisent des UUID déterministes (`uuid5` avec `NAMESPACE_DNS`) pour des UPSERT stables d'une exécution à l'autre.

#### Intelligence territoriale

- `department_scorer.py` : indice de santé départemental (0-100), adapté du Country Instability Index de World Monitor. Formule : `baseline * 0.4 + event_score * 0.6 + boosts`, plancher à 15.
- `ecosystem_score_service.py` : score de maturité d'écosystème à 6 dimensions pondérées (tissu économique 25 %, structures support 20 %, maillage institutionnel 15 %, formation & recherche 15 %, emploi & compétences 15 %, foncier & infrastructure 10 %).
- `focal_point_detector.py` : détecte les entités (ORG, LOC, PER) apparaissant dans plusieurs sources de presse indépendantes (convergence ≥ 2 sources, fenêtre 48 h).
- `correlation_engine.py` : corrélations cachées entre indicateurs - corrélations décalées (lag), causalité de Granger, information mutuelle, corrélation partielle.
- `territorial_stats.py` : statistiques territoriales réelles (SIRENE, BODACC, INSEE) - aucune donnée mock.
- `territorial_reports.py` : génération de rapports automatiques (flash quotidien, hebdo régional, mensuel national).

#### Pipeline news

- `news_sync_service.py` : synchronisation des flux RSS vers la base (fetch → dédoublonnage → persistance → résumé → sentiment → détection de pics → alerte).
- `news_cross_enricher.py` : crée des relations `mentioned_in_news` reliant un acteur connu à son territoire lorsqu'un focal point correspond.
- `news_scheduler.py` : pipeline périodique (sync + enrichissement + détection de focal points + santé départementale + alertes Telegram).
- `llm_summarizer.py` : résumé et sentiment d'article avec chaîne de repli Ollama → Groq → OpenRouter, chaque fournisseur protégé par un circuit breaker.
- `alert_service.py` : détection et notification des changements significatifs (création/fermeture d'entreprise, opportunité de marché, indicateur économique, etc.).

#### Agents, LLM & assistant

- `agent_orchestrator.py` : routage des requêtes vers les agents ou LLMs appropriés, avec émission d'événements pour l'intégration WebSocket TUI (`started`, `thinking`, `tool_call`, `streaming`, …).
- `autonomous_agent_service.py` : coordination de l'automatisation web autonome (planification LLM → validation → exécution pas-à-pas → reprise sur erreur).
- `assistant_service.py` : interface conversationnelle principale, orchestrant `conversation/` avec RAG optionnel.
- `embedding_service.py` : chunking, génération d'embeddings et stockage vectoriel (PGVector), Ollama direct ou via LitServe.

#### Planification & système

- `crawler_scheduler.py` : intègre `AdaptiveCrawler` avec APScheduler pour le crawling automatique des sources officielles françaises (SIRENE, BODACC, …).
- `tajine_scheduler.py` : analyses TAJINE planifiées via APScheduler avec job store PostgreSQL.
- `system_initialization_service.py` : orchestration de l'initialisation système (vérification, création de répertoires).
- `service_factory.py` : fonctions factory façade sur le conteneur DI.
- `interfaces.py` : `Protocol` des services système (vérification, initialisation, health check, GPU, répertoires).
- `_db_pool.py` : pool de connexions asyncpg partagé par les services du graphe relationnel.

### `use_cases/` - Cas d'usage ML

Cas d'usage orchestrant le cycle de vie des modèles ML, dépendant uniquement des ports et des repositories du domaine.

| Fichier | Cas d'usage |
|---------|-------------|
| `train_model.py` | Entraînement d'un nouveau modèle (LoRA) |
| `deploy_model.py` | Déploiement avec stratégie (canary, blue-green) et rollback |
| `predict.py` | Prédiction avec routage de trafic et journalisation |
| `submit_feedback.py` | Soumission de feedback utilisateur sur les prédictions |
| `active_learning.py` | Détection de drift, échantillonnage et déclenchement de réentraînement |
| `automatic_retraining.py` | Réentraînement automatique selon des conditions (dégradation, intervalle) |

### `ports/` - Interfaces (hexagonal)

Contrats (ABC / Protocol) implémentés par la couche infrastructure :

- `ml_ports.py` : `IModelTrainer`, `IModelDeployer`, `IModelInference`, `IMLExperimentTracker`, `IWorkflowOrchestrator`
- `storage_ports.py` : `IModelStorageService` (stockage S3-compatible / MinIO)
- `active_learning_ports.py` : `ISamplingStrategy`, `IDriftDetector`, `IRetrainingTrigger`
- `annotation_ports.py` : `IAnnotationService` (ex. Label Studio)
- `agent_ports.py` : contrats des agents d'automatisation web (`AgentType`, `TaskStatus`)

### `dtos/` - Data Transfer Objects

- `ml_dtos.py` : DTOs ML (`TrainModelRequest`, `DeployModelRequest`, `PredictionRequest`, …) en `dataclass`
- `active_learning_dtos.py` : DTOs Active Learning (Pydantic, ex. `SelectSamplesRequest`)
- `code_execution_dtos.py` : DTOs d'exécution de code (`ExecutionBackend`, `CodeLanguage`)

### `orchestration/` - Requêtes multi-sources

- `data_orchestrator.py` : `DataOrchestrator` lance des requêtes parallèles sur plusieurs sources de données, agrège les résultats et applique le matching d'entités (`EntityMatcher`).

### `reporting/` - Rapports

- `orchestrated_report.py` : `OrchestratedReportGenerator` génère des rapports HTML riches (résumé exécutif avec score de confiance, ventilation par source, timeline de validation multi-agents, recommandations, visualisations).

### `jobs/` - Tâches de collecte

- `territorial_collector.py` : job de collecte quotidienne parcourant les 101 départements français et stockant les métriques historiques.

### `conversation/` - Gestion conversationnelle

- `context_manager.py` : `ContextManager` / `ConversationContext` - état, historique et contexte de conversation.
- `dialog_manager.py` : `DialogManager` / `DialogState` - flux de dialogue (idle, greeting, helping, clarifying, …).
- `response_generator.py` : `ResponseGenerator` - réponses contextuelles via LLM (Ollama / LitServe).

## Fichiers clés

```
src/application/
├── services/
│   ├── relation_service.py            # Orchestrateur du graphe relationnel
│   ├── relation_extractors.py         # L1 - extraction factuelle
│   ├── relation_inferrers.py          # L2 - inférence statistique
│   ├── relation_predictors.py         # L3 - prédiction
│   ├── cascade_model.py               # Régression logistique cascade
│   ├── network_analytics_service.py   # Métriques NetworkX
│   ├── department_scorer.py           # Indice de santé départemental
│   ├── ecosystem_score_service.py     # Score de maturité 6 dimensions
│   ├── focal_point_detector.py        # Convergence multi-sources
│   ├── correlation_engine.py          # Corrélations cachées
│   ├── territorial_stats.py           # Stats réelles SIRENE/BODACC/INSEE
│   ├── territorial_reports.py         # Rapports automatiques
│   ├── news_sync_service.py           # Sync RSS → DB
│   ├── news_cross_enricher.py         # Enrichissement graphe via news
│   ├── news_scheduler.py              # Pipeline news périodique
│   ├── llm_summarizer.py              # Résumé + sentiment (fallback chain)
│   ├── alert_service.py               # Alertes sur changements
│   ├── agent_orchestrator.py          # Routage agents/LLM (WebSocket TUI)
│   ├── autonomous_agent_service.py    # Automatisation web autonome
│   ├── assistant_service.py           # Assistant conversationnel
│   ├── embedding_service.py           # Embeddings + stockage vectoriel
│   ├── crawler_scheduler.py           # Planification du crawler
│   ├── tajine_scheduler.py            # Planification des analyses TAJINE
│   ├── system_initialization_service.py
│   ├── service_factory.py             # Factory / façade DI
│   ├── interfaces.py                  # Protocols services système
│   └── _db_pool.py                    # Pool asyncpg partagé
├── use_cases/                         # Cas d'usage ML (train, deploy, predict, …)
├── ports/                             # Interfaces (ml, storage, active_learning, …)
├── dtos/                              # DTOs (ml, active_learning, code_execution)
├── orchestration/data_orchestrator.py # Requêtes multi-sources parallèles
├── reporting/orchestrated_report.py    # Rapports HTML
├── jobs/territorial_collector.py       # Collecte quotidienne 101 départements
└── conversation/                       # Contexte, dialogue, génération de réponse
```

## Configuration

Variables d'environnement utilisées par la couche application :

| Variable | Description | Défaut |
|----------|-------------|--------|
| `COLLECTOR_DATABASE_URL` | DSN PostgreSQL du pool asyncpg partagé (`_db_pool.py`) | `postgresql+asyncpg://localhost:5432/tawiza` |
| `OLLAMA_BASE_URL` | URL du serveur Ollama (LLM local) | `http://localhost:11434` |
| `OLLAMA_MODEL` | Modèle Ollama par défaut | - |
| `GROQ_API_KEY` | Clé API Groq (2ᵉ maillon du fallback LLM) | - |
| `OPENROUTER_API_KEY` | Clé API OpenRouter (3ᵉ maillon du fallback LLM) | - |
| `TELEGRAM_BOT_TOKEN` | Token du bot Telegram pour les alertes | - |
| `TELEGRAM_CHAT_ID` | Identifiant du chat Telegram destinataire | - |

## État actuel

- Le graphe relationnel à 3 niveaux (extractors / inferrers / predictors) est fonctionnel avec UPSERT déterministe.
- Le pipeline news (sync → enrichissement → focal points → alertes) tourne via `news_scheduler`.
- Les scores territoriaux (santé départementale, maturité d'écosystème) sont opérationnels sur données réelles.
- La chaîne de repli LLM (Ollama → Groq → OpenRouter) est protégée par circuit breakers.
- Les cas d'usage ML s'appuient sur les ports : l'implémentation infrastructure conditionne leur activation effective.
- `cascade_model` retombe sur l'heuristique si scikit-learn ou les données d'entraînement manquent.

## Limitations connues

- Le pool asyncpg (`_db_pool`) est un singleton global partagé - pas d'isolation par tenant.
- Le modèle de cascade nécessite des données d'entraînement suffisantes, sinon repli heuristique.
- Les schedulers APScheduler perdent leur état au redémarrage si le job store PostgreSQL n'est pas configuré.
- L'enrichissement news → graphe dépend de la qualité du NER pour le matching d'acteurs.
- Plusieurs services (corrélation, prédiction L3) nécessitent un historique de données suffisant pour produire des résultats fiables.
