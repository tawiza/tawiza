# API REST

Backend FastAPI de Tawiza. Expose l'ensemble des capacités de la plateforme (agents, crawler, signaux territoriaux, alertes, modèles LLM, export) via une API HTTP versionnée, complétée par un canal WebSocket temps réel et des endpoints compatibles OpenAI.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI app (main.py)                       │
│                                                                │
│  ┌──────────────────────── Middleware (LIFO) ──────────────┐  │
│  │  RequestIDMiddleware  ·  ErrorHandlerMiddleware  ·       │  │
│  │  PrometheusMiddleware  ·  CORS  ·  slowapi RateLimit     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                 │
│  ┌───────────────────────────▼──────────────────────────────┐  │
│  │                   Routers (~40 inclus)                     │  │
│  │                                                            │  │
│  │  v1/        →  routers organisés par domaine               │  │
│  │  routers/   →  routers plats (ML, fine-tuning, browser…)   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                 │
│  ┌───────────────────────────▼──────────────────────────────┐  │
│  │   WebSocket /ws  →  WebSocketManager + handlers PPDSL      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                │
│  Lifespan : DB, AgentOrchestrator, schedulers (TAJINE,        │
│  Crawler, Collector, News), broadcast métriques WebSocket     │
└──────────────────────────────────────────────────────────────┘
```

L'application est assemblée dans `main.py` : configuration du `lifespan` (initialisation base de données, `AgentOrchestrator`, schedulers, WebSocket), ajout des middlewares, puis inclusion des routers via `app.include_router(...)`.

## Cycle de vie (lifespan)

Au démarrage, le gestionnaire `lifespan` initialise dans l'ordre :

1. Le logging structuré (`configure_logging`) et la télémétrie (`capture_startup`).
2. La base de données (`init_db`), avec dégradation silencieuse si indisponible.
3. L'`AgentOrchestrator` (sélection du modèle Ollama, agents).
4. Le `WebSocketManager` et ses handlers, plus le broadcast périodique de métriques (intervalle 5 s).
5. Les schedulers : TAJINE, Crawler, Collector (micro-signaux), News Intelligence (intervalle 6 h).

À l'arrêt, les schedulers et le broadcast de métriques sont stoppés, le pool de connexions et la base de données sont fermés.

## Middleware

| Middleware | Rôle |
|------------|------|
| `RequestIDMiddleware` | Génère ou propage un `X-Request-ID` (corrélation logs/traces) |
| `ErrorHandlerMiddleware` | Capture les exceptions et renvoie une réponse JSON normalisée |
| `PrometheusMiddleware` | Mesure la durée des requêtes (exposée sur `/metrics`) |
| `CORSMiddleware` | Origines configurables via `CORS_ORIGINS` |
| slowapi `Limiter` | Rate limiting par IP sur les endpoints décorés |

Le middleware `security.py` (`SecurityHeadersMiddleware`, `RateLimitMiddleware`, `RequestValidationMiddleware`) fournit des en-têtes de sécurité, un rate limiting par token bucket et une validation de taille/Content-Type. Il est disponible dans le module mais n'est pas câblé dans `main.py`.

Les handlers d'exception FastAPI (`register_exception_handlers`) normalisent les erreurs domaine (`TawizaError`), de validation (`RequestValidationError`) et HTTP en réponses `{success, error, request_id}`.

## Routers

Les routers sont organisés en deux espaces :

- `v1/` : routers groupés par domaine, chacun dans un sous-package avec `routes.py` (et parfois `schemas.py`).
- `routers/` : routers plats, principalement orientés ML, entraînement et outils.

### Routers `v1/` (par domaine)

| Domaine | Prefix | Description |
|---------|--------|-------------|
| `auth/` | `/api/v1/auth` | Authentification (login admin via `ADMIN_EMAIL`/`ADMIN_PASSWORD`) |
| `agents/` | `/api/v1/agents` | Endpoints des agents Tawiza |
| `tajine/` | `/api/v1/tajine` | Méta-agent TAJINE (cycle PPDSL) |
| `orchestration/` | `/orchestration` | Orchestration de pipelines |
| `conversations/` | `/api/v1/conversations` | Historique de conversations |
| `crawler/` | `/crawler` | Configuration du crawler |
| `crawler/commoncrawl_routes` | `/api/v1/crawler/commoncrawl` | CrawlIntel (Common Crawl) |
| `crawler_v2.py` | `/api/v1/crawler` | Gestion du crawler V2 |
| `alerts/` | `/alerts` | Alertes territoriales |
| `territorial/` | `/territorial` | Widgets du tableau de bord territorial |
| `sources/` | `/api/v1/sources` | Santé et monitoring des sources de données |
| `signals.py` | `/api/v1/signals` | Signaux et micro-signaux (base tawiza) |
| `microsignals.py` | `/api/v1/microsignals` | Gestion des micro-signaux |
| `investigation.py` | `/api/v1/investigation` | Investigation |
| `relations.py` | `/api/v1/investigation/relations` | Relations entre entités |
| `decisions/` | `/api/v1/decisions` | Décisions et parties prenantes |
| `watcher/` | `/api/v1/watcher` | Daemon Watcher et alertes |
| `schedules/` | `/schedules` | Analyses planifiées |
| `export/` | `/api/v1/export` | Export PDF/Markdown |
| `health/` | `/api/v1/health` | Health checks détaillés |
| `ollama/` | `/api/v1/ollama` | Gestion des modèles Ollama |
| `openai_compatible/` | `/v1` | Endpoints compatibles OpenAI (LobeChat) |
| `training.py` | `/api/v1/training` | Données d'entraînement |
| `errors/` | `/api/v1/errors` | Remontée d'erreurs frontend |

### Routers `routers/` (ML et outils)

| Router | Prefix | Description |
|--------|--------|-------------|
| `annotations.py` | `/api/v1/annotations` | Annotations |
| `browser.py` | `/api/v1/browser` | Automatisation navigateur |
| `fine_tuning.py` | `/api/v1/fine-tuning` | Fine-tuning |
| `health.py` | `/health` | Health checks |
| `ollama.py` | (variable) | Gestion Ollama |
| `code_execution.py` | `/api/v1/code-execution` | Exécution de code |
| `ecocartographe.py` | `/ecocartographe` | EcoCartographe |
| `active_learning.py` | `/active-learning` | Active learning |
| `uaa.py` | `/uaa` | Unified Adaptive Agent |
| `vectors.py` | `/vectors` | Recherche vectorielle |
| `retraining.py` | `/retraining` | Réentraînement |
| `progress.py` | (variable) | Suivi de progression des tâches |
| `models.py`, `model_storage.py`, `prompts.py`, `datasets.py`, `predictions_v2.py`, `feedback_v2.py`, `training.py` | (variable) | Cycle de vie ML : modèles, prompts, datasets, prédictions, feedback |

Tous les routers `v1/` ne sont pas inclus dans `main.py` (certains, comme `routers/ecocartographe.py` ou `routers/active_learning.py`, ne sont pas câblés par défaut).

## WebSocket (`websocket/`)

Le canal `/ws` assure la communication temps réel avec la TUI et le frontend.

- `server.py` : `WebSocketManager` gère les connexions par session, le routage de messages, le broadcast (ciblé par session ou global) et la diffusion périodique de métriques système (CPU, RAM, GPU via `rocm-smi`, disque).
- `handlers.py` : enregistre les handlers métier  -  `TaskHandler` (création/contrôle de tâches via `AgentOrchestrator`), `ChatHandler` (chat streaming), `AgentStatusHandler`, `TAJINEHandler` (pont des événements PPDSL vers la TUI), `BrowserHandler` (streaming de captures d'écran).
- `models.py` : modèles Pydantic des messages (énum `MessageType`, messages Task/TAJINE/Chat/Browser/System) et fonction `parse_message`.

Le mapping `TAJINEHandler.EVENT_MAP` relaie les phases du cycle PPDSL (`perceive`, `plan`, `delegate`, `synthesize`, `learn`) vers les messages WebSocket correspondants.

## Endpoints racine

Définis directement dans `main.py` :

| Endpoint | Description |
|----------|-------------|
| `GET /` | Métadonnées de l'API |
| `GET /health` | Health check simple |
| `GET /metrics` | Métriques Prometheus |
| `GET /api/v1/system/status` | CPU/RAM/disque via `psutil` |
| `GET/POST /api/v1/evaluations` | Évaluations (placeholder) |
| `WS /ws` | Canal WebSocket temps réel |
| `GET /ws/status` | État du serveur WebSocket |

La documentation interactive est exposée sur `/docs` (Swagger) et `/redoc`.

## Fichiers clés

```
src/interfaces/api/
├── main.py                      # App FastAPI : lifespan, middlewares, inclusion routers
├── middleware/
│   ├── request_id.py            # Corrélation X-Request-ID
│   ├── error_handler.py         # Réponses d'erreur normalisées
│   └── security.py              # En-têtes sécurité, rate limit, validation
├── websocket/
│   ├── server.py                # WebSocketManager + broadcast métriques
│   ├── handlers.py              # Handlers Task/Chat/TAJINE/Browser
│   └── models.py                # Modèles de messages Pydantic
├── v1/                          # Routers par domaine (routes.py + schemas.py)
│   ├── auth/  agents/  tajine/  orchestration/  conversations/
│   ├── crawler/  alerts/  territorial/  sources/  decisions/
│   ├── watcher/  schedules/  export/  health/  ollama/
│   ├── openai_compatible/  errors/
│   ├── signals.py  microsignals.py  investigation.py
│   ├── relations.py  crawler_v2.py  training.py
│   └── relations_schemas.py
└── routers/                     # Routers plats (ML, outils)
    ├── annotations.py  browser.py  fine_tuning.py  code_execution.py
    ├── ecocartographe.py  active_learning.py  uaa.py  vectors.py
    ├── retraining.py  progress.py  health.py  ollama.py
    ├── models.py  model_storage.py  prompts.py  datasets.py
    └── predictions_v2.py  feedback_v2.py  training.py
```

## Configuration

| Variable | Description | Défaut |
|----------|-------------|--------|
| `CORS_ORIGINS` | Origines autorisées (séparées par virgule) | localhost:3000/8000 |
| `APP_ENV` | Environnement (`development`/`production`) | `development` |
| `LOG_LEVEL` | Niveau de log | `INFO` |
| `ENVIRONMENT` | Environnement Sentry | `development` |
| `SENTRY_DSN` | DSN Sentry (tracking d'erreurs, optionnel) |  -  |
| `ADMIN_EMAIL` | Email du compte admin (auth) |  -  |
| `ADMIN_PASSWORD` | Mot de passe admin (auth) |  -  |
| `ADMIN_NAME` | Nom affiché de l'admin | `Administrateur` |
| `SECRET_KEY` | Clé de signature JWT (obligatoire en production) | clé temporaire en dev |
| `OLLAMA_BASE_URL` | URL Ollama (endpoints compatibles OpenAI) | `http://localhost:11434` |

Le rate limiting global est appliqué par `slowapi` (`get_remote_address`) sur les endpoints racine (60/minute). L'intégration Sentry est optionnelle : activée uniquement si `sentry-sdk` est installé et `SENTRY_DSN` défini.

## État actuel

- L'API FastAPI versionnée et le canal WebSocket sont fonctionnels et servent la TUI et le frontend.
- Les middlewares de corrélation, gestion d'erreurs et métriques Prometheus sont câblés dans `main.py`.
- Les schedulers (TAJINE, Crawler, Collector, News) démarrent au boot avec dégradation silencieuse si une dépendance est indisponible.
- Le broadcast de métriques WebSocket s'appuie sur `rocm-smi` pour le GPU (renvoie 0 si absent).
- Les endpoints d'évaluations (`/api/v1/evaluations`) sont des placeholders.

## Limitations connues

- Tous les routers présents dans `v1/` et `routers/` ne sont pas inclus dans `main.py` : certains existent dans le code sans être câblés.
- `SecurityHeadersMiddleware`/`RateLimitMiddleware`/`RequestValidationMiddleware` sont implémentés mais pas ajoutés à l'application principale.
- Le préfixe `/api/v1/crawler` est partagé entre `crawler_v2.py` et les routes CrawlIntel (`commoncrawl_routes`), ce qui demande une attention au regroupement des routes.
- L'initialisation de la base de données et des schedulers échoue silencieusement (warning) si les dépendances ne sont pas disponibles, ce qui peut masquer un démarrage partiel.
