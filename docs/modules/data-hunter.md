# Data Hunter

Module de collecte proactive de données pour l'agent TAJINE. Le Data Hunter orchestre l'interrogation intelligente de multiples sources de données avec des stratégies adaptatives.

## Architecture

Le Data Hunter existe en deux versions complémentaires :
- **`DataHunter`** : Version standard avec 4 stratégies de collecte
- **`ResilientDataHunter`** : Version renforcée avec circuit breaker, retry, cache et fallback

```
┌─────────────────────────────────────────────────┐
│               ResilientDataHunter               │
│                                                 │
│  ┌───────────┐  ┌───────────┐  ┌────────────┐  │
│  │ Hypothesis│  │  Bandit   │  │   Graph    │  │
│  │ Generator │  │ (LinUCB)  │  │  Expander  │  │
│  └─────┬─────┘  └─────┬─────┘  └─────┬──────┘  │
│        │              │              │          │
│  ┌─────▼──────────────▼──────────────▼──────┐   │
│  │        DataSourceManager (15+ APIs)      │   │
│  └─────────────────────┬────────────────────┘   │
│                        │                        │
│  ┌─────────────────────▼────────────────────┐   │
│  │  ResilientFetcher (retry + circuit break) │  │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

## Les 4 stratégies de collecte

### 1. Hypothesis-driven (`hypothesis.py`)
Génère des hypothèses à tester à partir de la requête utilisateur, puis sélectionne les sources les plus pertinentes pour les vérifier.

### 2. Bandit / LinUCB (`bandit.py`)
Sélection contextuelle des sources via un algorithme Multi-Armed Bandit (LinUCB). Le bandit apprend quelles sources sont les plus performantes selon le contexte territorial et sectoriel.

### 3. Graph Expansion (`graph_expander.py`)
Identifie les lacunes dans le Knowledge Graph (`KnowledgeGap`) et lance des collectes ciblées pour les combler. Explore les relations entre entités.

### 4. Discovery (`discovery_engine.py`)
Exploration automatique de patterns dans les données collectées. Détecte des corrélations et anomalies non anticipées.

## Version résiliente

Le `ResilientDataHunter` ajoute des mécanismes de robustesse :

| Mécanisme | Description | Fichier |
|-----------|-------------|---------|
| **Circuit Breaker** | Coupe les appels vers une source défaillante après N échecs | `circuit_breaker.py` |
| **Retry** | Réessaie avec backoff exponentiel | `resilient.py` → `ResilientFetcher` |
| **Cache** | Évite les appels redondants (mémoire + SQLite) | `resilient.py` → `DataCache` |
| **Fallback** | Bascule vers des sources alternatives en cas d'échec | `resilient.py` → `FallbackSourceChain` |
| **Augmentation** | Génère des données synthétiques quand les sources sont rares | `resilient.py` → `RareDataAugmenter` |
| **Persistent Bandit** | Sauvegarde l'apprentissage du bandit entre sessions | `resilient.py` → `PersistentBanditMixin` |
| **Semantic Search** | Recherche vectorielle complémentaire (pgvector/Qdrant) | Via `SemanticSearchService` |
| **Web Crawling** | Renfort par crawling web quand les APIs sont insuffisantes | Via `AdaptiveCrawler` |

## Fichiers clés

```
src/infrastructure/agents/tajine/hunter/
├── data_hunter.py        # DataHunter principal (4 stratégies)
├── resilient_hunter.py   # Version résiliente (circuit breaker, etc.)
├── resilient.py          # Composants de résilience (cache, fallback, retry)
├── hypothesis.py         # Générateur d'hypothèses
├── bandit.py             # SourceBandit (sélection contextuelle)
├── graph_expander.py     # Expansion du Knowledge Graph
├── discovery_engine.py   # Moteur de découverte automatique
├── reward.py             # Calcul de récompense pour le bandit
└── crawler.py            # Pont vers l'AdaptiveCrawler
```

## Configuration

Le Data Hunter utilise les mêmes variables que les sources de données (voir `configuration.md`). La configuration spécifique du bandit se fait via :

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| `exploration_param` | Paramètre d'exploration UCB (plus haut = plus exploratoire) | `2.0` |
| `cache_ttl` | Durée de vie du cache en secondes | `3600` |
| `max_concurrent` | Requêtes parallèles maximum | `10` |

## Télémétrie

Le module expose des métriques via OpenTelemetry :
- `record_bandit_pull` : Sélection de source par le bandit
- `track_cache` : Hit/miss du cache
- `track_fallback` : Utilisations du fallback
- `set_circuit_breaker` : État du circuit breaker
- `trace_hunt` : Trace complète d'une opération de collecte

## État actuel

- Les 4 stratégies de collecte sont implémentées
- La version résiliente est fonctionnelle avec circuit breaker et cache
- Le LinUCB contextuel est intégré mais nécessite plus de données d'entraînement
- Le Discovery Engine est optionnel (import avec fallback)
- Le parsing de documents (Docling pour PDF/DOCX) est optionnel

## Limitations connues

- Le bandit nécessite un historique suffisant pour converger (cold start)
- L'augmentation de données rares est basique (interpolation), pas de génération LLM
- Le cache SQLite peut croître sans limite si non purgé manuellement
- Le graph expander dépend d'un Knowledge Graph peuplé pour être efficace
