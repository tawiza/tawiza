# Core

Module de fondation transverse de Tawiza. Regroupe la configuration, les constantes, la hiérarchie d'exceptions, le logging, les utilitaires de sécurité, la gestion d'état système et la télémétrie. Tous les autres modules s'appuient sur `src/core/` pour leurs réglages, leur journalisation et leurs erreurs typées.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         src/core/                             │
│                                                               │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   │
│  │  config.py   │   │ constants.py │   │  exceptions.py   │   │
│  │ Settings     │   │ Valeurs      │   │ Hiérarchie       │   │
│  │ pydantic     │   │ figées       │   │ TawizaException  │   │
│  └──────────────┘   └──────────────┘   └──────────────────┘   │
│                                                               │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   │
│  │ logging_     │   │ security.py  │   │ system_state.py  │   │
│  │ config.py    │   │ Secrets ·    │   │ Singleton thread-│   │
│  │ loguru       │   │ sanitization │   │ safe + snapshots │   │
│  └──────────────┘   └──────────────┘   └──────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                    telemetry.py                       │    │
│  │      Télémétrie anonyme opt-out (PostHog)             │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Composants

### Configuration (`config.py`)

Gestion centralisée des réglages via **pydantic-settings**. La classe `Settings` agrège des sous-réglages, chacun chargé depuis l'environnement (préfixe dédié) et le fichier `.env` :

| Sous-réglage | Préfixe env | Contenu |
|--------------|-------------|---------|
| `DatabaseSettings` | `DATABASE_` | URL PostgreSQL (asyncpg), pool, overflow, echo SQL |
| `OllamaSettings` | `OLLAMA_` | URL API, modèle, modèle d'embedding, température, timeout |
| `VectorDBSettings` | `VECTORDB_` | activation, dimension d'embedding, taille/overlap de chunk |
| `RedisSettings` | `REDIS_` | URL de connexion Redis |
| `APISettings` | `API_` | host, port, préfixe, origines CORS |

Un singleton `settings` est instancié à l'import. Le modèle par défaut Ollama est `qwen2.5:7b`, l'embedding `nomic-embed-text`.

### Constantes (`constants.py`)

Centralise les nombres magiques, versions et valeurs par défaut sous forme de `Final` typés, pour éviter la duplication. Regroupements principaux :

- **Version** : `APP_VERSION` (`2.0.3`), `APP_NAME` (`Tawiza-V2`), `MIN_PYTHON_VERSION` (`3.10`)
- **Timeouts** : commandes (`SHORT`/`MEDIUM`/`LONG`/`EXTENDED`/`MAX`), réseau HTTP, retries
- **Répertoires** : `DIRS_TO_CREATE`, `LOG_DIR`, `DATA_DIR`, `MODELS_DIR`, etc.
- **Seuils ressources** : CPU/mémoire/disque (warning + critical)
- **Scores de santé** : excellent/good/medium + pénalités
- **Ports par défaut** : API (8000), Prometheus (9090), Grafana (3000), MLflow (5000), Ollama (11434), etc.
- **Base de données / Redis / Ollama** : tailles de pool et TTL de cache
- **Entraînement** : batch size, learning rate, époques, rang/alpha LoRA
- **Vector DB** : dimension, taille de chunk, seuil de distance
- **GPU** : `ROCM_PATH_DEFAULT` (`/opt/rocm`), `GPU_PLATFORM_AMD`
- **Icônes et indicateurs** : pictogrammes de statut

### Exceptions (`exceptions.py`)

Hiérarchie d'exceptions typées qui remplace les `except` nus et porte un contexte structuré. Toutes héritent de `TawizaException`, qui transporte un `message` et un dictionnaire `details`.

```
TawizaException
├── TawizaConfigurationError
│   ├── ConfigurationNotFoundError
│   ├── ConfigurationCorruptedError
│   └── InvalidConfigurationError
├── TawizaResourceError
│   └── ResourceExhaustedError
│       ├── MemoryExhaustedError
│       └── DiskSpaceExhaustedError
├── TawizaValidationError
├── SystemNotInitializedError / SystemAlreadyInitializedError / SystemInitializationError
├── SystemRequirementError
│   ├── PythonVersionError
│   ├── DockerNotAvailableError
│   └── GPUNotAvailableError
│       └── ROCmNotInstalledError
├── AgentError (AgentNotAvailable · AgentExecution · AgentTimeout)
├── TaskError (NotFound · NotCompleted · NotCancellable · AlreadyRunning)
├── SecurityError (InsecureConfiguration · PathTraversal · CommandInjection)
├── DebugError (DebuggerNotStarted · DebuggerAlreadyRunning)
├── ExternalServiceError (ServiceUnavailable · ServiceTimeout · OllamaService · MLflowService)
└── ModelError (ModelNotFound · ModelLoad)
```

Deux helpers : `require_system_initialized()` et `require_debugger_started()` lèvent l'exception adéquate si la précondition n'est pas remplie.

### Logging (`logging_config.py`)

Configuration unifiée de la journalisation via **loguru**. Tous les modules importent `logger` depuis ce fichier plutôt que la lib standard.

- **Corrélation de requête** : `ContextVar` `request_id` et `user_id`, avec getters/setters dédiés
- **`InterceptHandler`** : redirige le logging stdlib vers loguru pour capturer les libs tierces
- **`format_record()`** : format coloré `TIME | LEVEL | MODULE:LINE [req=… user=…] - MESSAGE`
- **`configure_logging()`** : niveau, sortie JSON optionnelle, fichier avec rotation (`10 MB`) et rétention (`1 week`) + compression `gz`
- Les loggers bruyants (uvicorn, fastapi, httpx, sqlalchemy.engine, playwright) sont mis à `WARNING`

Le logging est configuré au niveau `INFO` dès l'import, reconfigurable via `configure_logging()`.

### Sécurité (`security.py`)

Utilitaires pour prévenir les vulnérabilités courantes.

| Fonction / Classe | Rôle |
|-------------------|------|
| `SecretManager` | Récupère/génère/valide la clé secrète. Exige `SECRET_KEY` en production, génère une clé temporaire en développement |
| `sanitize_path()` | Empêche le path traversal, restreint à un répertoire de base |
| `validate_filename()` | Valide un nom de fichier (caractères sûrs, pas de fichier caché, longueur max) |
| `sanitize_command_arg()` | Détecte les caractères dangereux et la substitution de commande |
| `validate_subprocess_command()` | Interdit l'exécution shell (`sh`, `bash`, …) dans un subprocess |
| `validate_port()` | Vérifie qu'un port est entre 1 et 65535 |
| `validate_timeout()` | Valide une durée (non négative, alerte au-delà d'une heure) |
| `sanitize_log_message()` | Empêche l'injection de logs (suppression des sauts de ligne) |
| `get_security_headers()` | Renvoie les en-têtes HTTP de sécurité recommandés (CSP, HSTS, X-Frame-Options, …) |

### État système (`system_state.py`)

Singleton thread-safe qui remplace les variables globales mutables par un accès contrôlé.

- **`InitializationConfig`** : dataclass figée (GPU, monitoring, tâches concurrentes, auto-scale, retries)
- **`SystemState`** : snapshot immuable (composants, config, métadonnées, compteurs de tâches). Propriétés `is_initialized`, `has_gpu`, `has_monitoring` ; méthode `with_updates()` pour produire un nouvel état sans muter l'ancien
- **`SystemStateManager`** : singleton à double-checked locking (`Lock` pour la création, `RLock` réentrant pour l'accès). Conserve un historique des 10 derniers états. Méthodes `update_state()`, `clear_state()`, `is_initialized()`, `get_state_or_raise()`, `increment_tasks()`, `get_history()`, `get_metrics()`

Fonctions de commodité au niveau module : `get_system_state_manager()`, `get_current_state()`, `is_system_initialized()`, `require_initialized()`.

### Télémétrie (`telemetry.py`)

Télémétrie anonyme **opt-out** envoyée vers PostHog (clé en écriture seule, dashboard de l'équipe Tawiza).

- Désactivable via `TELEMETRY_ENABLED=false`
- Identifiant anonyme stable par installation (`~/.tawiza/.telemetry_id`, hash SHA-256, aucune PII)
- Client PostHog lazy-init, échec silencieux  -  la télémétrie ne doit jamais casser l'application
- Événements : `capture()`, `capture_feature()`, `capture_agent()`, `capture_datasource()`, `capture_startup()`, plus `shutdown()` pour vider les événements en attente
- Chaque événement enrichi de propriétés de base : version, version Python, OS, architecture

## Fichiers clés

```
src/core/
├── config.py            # Settings pydantic (DB, Ollama, VectorDB, Redis, API)
├── constants.py         # Constantes Final (versions, timeouts, ports, seuils)
├── exceptions.py        # Hiérarchie TawizaException + helpers
├── logging_config.py    # Logging loguru + corrélation request/user
├── security.py          # Secrets, sanitization, validation, headers
├── system_state.py      # Singleton thread-safe + snapshots immuables
└── telemetry.py         # Télémétrie anonyme PostHog (opt-out)
```

## Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `DATABASE_URL` | URL PostgreSQL (asyncpg) | `postgresql+asyncpg://tawiza:changeme@localhost:5432/tawiza` |
| `OLLAMA_BASE_URL` | URL API Ollama | `http://localhost:11434` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379/0` |
| `VECTORDB_ENABLED` | Activer la base vectorielle | `true` |
| `API_PORT` | Port de l'API | `8000` |
| `SECRET_KEY` | Clé secrète (obligatoire en production, min. 32 caractères) |  -  |
| `APP_ENV` | Environnement (`development` / `production`) | `development` |
| `TELEMETRY_ENABLED` | Activer la télémétrie anonyme | `true` |

Les sous-réglages pydantic acceptent aussi la notation à double underscore (ex. `OLLAMA__BASE_URL`).

## État actuel

- La configuration pydantic, les constantes, la hiérarchie d'exceptions et le logging loguru sont stables et utilisés transversalement
- Les utilitaires de sécurité (sanitization, validation, headers) sont en place
- Le `SystemStateManager` thread-safe remplace les anciens globaux mutables
- La télémétrie anonyme est opt-out et conçue pour échouer silencieusement

## Limitations connues

- La clé secrète générée en développement est éphémère (régénérée à chaque démarrage si `SECRET_KEY` n'est pas défini)
- L'historique d'état est limité aux 10 derniers snapshots et n'est pas persisté
- `validate_subprocess_command()` interdit le shell mais ne valide pas l'existence ni les droits du binaire appelé
- La télémétrie embarque une clé PostHog publique en écriture seule directement dans le code
