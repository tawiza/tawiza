# Scripts standalone

Scripts exécutables en ligne de commande qui composent le pipeline batch de Tawiza : collecte des sources publiques, détection d'anomalies, embeddings sémantiques, scoring territorial, surveillance continue et génération de données d'entraînement. Ils s'appuient sur la table `signals` unifiée et alimentent les tables exposées par l'API.

## Architecture du pipeline

```
┌──────────────────┐
│  collect_all_v2  │  Collecte multi-sources → table `signals`
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ detect_anomalies │     │   embed_signals  │     │ scoring_composite│
│      _v2         │     │  (pgvector)      │     │   (lib + CLI)    │
│ anomaly_detection│     │ signal_embeddings│     │territorial_snap. │
└──────────────────┘     └──────────────────┘     └──────────────────┘
         ▲
         │
┌──────────────────┐     ┌──────────────────┐
│    scheduler     │     │     watcher      │
│  (APScheduler)   │     │ (daemon Z-score) │
│ orchestre tout   │     │  watcher_alerts  │
└──────────────────┘     └──────────────────┘

┌──────────────────────┐
│ generate_training_data│  Hors pipeline → JSONL pour fine-tuning TAJINE
└──────────────────────┘
```

`scheduler.py` est le chef d'orchestre : il déclenche `collect_all_v2` et la détection selon des plages horaires. Les autres scripts peuvent aussi être lancés manuellement.

## Scripts de collecte

### `collect_all_v2.py`  -  Collecteur unifié

Collecte huit sources publiques et insère tout dans la table `signals` :
BODACC (liquidations, créations, modifications), France Travail (offres d'emploi), SIRENE (créations via data.gouv.fr), INSEE (chômage BDM, population geo.api), OFGL (finances locales), DVF (transactions immobilières), Banque de France (défaillances), Presse locale (RSS).

| Élément | Valeur |
|---------|--------|
| Commande | `python3 src/scripts/collect_all_v2.py [--depts 75 93 ...] [--sources bodacc sirene ...] [--days 30] [--all]` |
| Défaut | 20 départements stratégiques, lookback 30 jours, toutes les sources |
| Sortie | Insertion dans la table `signals` |
| Cron suggéré | Géré par le scheduler (voir `scheduler.py`) |

Sans `--depts` ni `--all`, le script cible un mix de 20 départements (IDF, grandes métropoles). `--all` couvre les 101 départements (métropole + Corse + DROM).

## Scripts d'analyse

### `detect_anomalies_v2.py`  -  Détection d'anomalies

Détection multivariée qui remplace le simple Z-score :
- **Isolation Forest** : combinaisons inhabituelles de métriques par département
- **DBSCAN** : regroupement des départements par profil économique, identification des outliers
- **Score de convergence v2** : pondéré par temporalité, causalité et fiabilité de la source (poids `SOURCE_WEIGHTS`, règles `CAUSAL_RULES`)

| Élément | Valeur |
|---------|--------|
| Commande | `python3 src/scripts/detect_anomalies_v2.py` |
| Sortie | Table `anomaly_detection_v2` (upsert sur `department, detection_date`) + log du top 10 risque et des clusters |
| Cron suggéré | Géré par le scheduler (jobs de détection à 7h et 19h) |

### `embed_signals.py`  -  Embeddings sémantiques

Génère des embeddings 768 dimensions via `nomic-embed-text` (Ollama) pour la recherche sémantique pgvector. Traite les signaux par lots et saute ceux déjà encodés.

| Élément | Valeur |
|---------|--------|
| Commande | `python3 src/scripts/embed_signals.py [--limit 50000]` |
| Recherche | `python3 src/scripts/embed_signals.py --search "ma requête"` (affiche les signaux similaires) |
| Sortie | Table `signal_embeddings` (signal_id, embedding, text_content) |
| Cron suggéré | Après chaque collecte importante (manuel ou ajout au scheduler) |

### `scoring_composite.py`  -  Scoring composite (librairie + CLI)

Calcule un score territorial composite à partir de 6 alpha factors normalisés par population :

| Facteur | Dimension |
|---------|-----------|
| α1 | Santé des entreprises (créations vs liquidations, BODACC + SIRENE) |
| α2 | Tension emploi (offres FT, ratio CDI, URSSAF AE) |
| α3 | Dynamisme immobilier (prix DVF, volume transactions) |
| α4 | Santé financière (OFGL dépenses/recettes, dette/hab) |
| α5 | Déclin ratio (liquidations + radiations vs créations) |
| α6 | Sentiment presse + Google Trends |

Score composite = Σ(αi × wi) / Σ(wi), normalisé 0-100.

Contrairement aux autres scripts, ce module est avant tout une **librairie** : sa fonction `get_department_scores()` est importée par l'API (`src/interfaces/api/v1/signals.py`). Il reste exécutable en CLI pour un calcul ponctuel.

| Élément | Valeur |
|---------|--------|
| Commande | `python3 src/scripts/scoring_composite.py` |
| Import API | `from src.scripts.scoring_composite import get_department_scores` |
| Sortie | Table `territorial_snapshots` (upsert) + classement loggé (top 20 / bottom 10) |
| Cron suggéré | Recalcul périodique après mise à jour des signaux |

## Scripts d'orchestration et de surveillance

### `scheduler.py`  -  Ordonnanceur APScheduler

Planifie automatiquement les collectes et détections via `AsyncIOScheduler` (timezone `Europe/Paris`). C'est le service à lancer pour faire tourner le pipeline en continu.

| Job | Trigger | Sources / action |
|-----|---------|------------------|
| `collect_frequent` | 0h, 6h, 12h, 18h | BODACC + France Travail + Presse (lookback 7j) |
| `collect_daily` | 6h15 | SIRENE + INSEE + OFGL (lookback 30j) |
| `collect_weekly` | dimanche 3h | DVF (lookback 90j) |
| `detect_microsignals` | 7h et 19h | Détection micro-signaux + temporelle + alertes Telegram |

| Élément | Valeur |
|---------|--------|
| Commande | `python3 src/scripts/scheduler.py` (tourne en continu) |
| Sortie | Déclenche les autres scripts, alimente les tables qu'ils visent |

Le job de détection importe `detect_microsignals_v2`, `detect_temporal` et `alert_telegram` de façon optionnelle (skip silencieux si le module est absent).

### `watcher.py`  -  Surveillance continue

Daemon qui compare toutes les N minutes les dernières valeurs aux moyennes historiques et détecte les écarts significatifs (Z-score). Les métriques surveillées sont groupées par priorité (high / medium / low).

| Élément | Valeur |
|---------|--------|
| Commande (daemon) | `python3 src/scripts/watcher.py [--interval 30] [--threshold 2.0]` |
| Commande (one-shot) | `python3 src/scripts/watcher.py --once` |
| Sortie | Table `watcher_alerts` (exposée via API) |
| Cron suggéré | Aucun (daemon long-running, intervalle interne 30 min) |

Paramètres internes : `WATCH_INTERVAL_MINUTES=30`, `LOOKBACK_DAYS=90`, `Z_THRESHOLD=2.0`, `MIN_DATA_POINTS=5`.

## Script de génération de données

### `generate_training_data.py`  -  Données de fine-tuning TAJINE

Génère des paires question/réponse synthétiques sur l'intelligence territoriale à partir des signaux réels en base. Sortie au format JSONL compatible Ollama (SFT). Pour chaque département ayant plus de 50 signaux, récupère un contexte, construit une question depuis des templates, puis génère la réponse via le LLM (`qwen3.5:27b`).

| Élément | Valeur |
|---------|--------|
| Commande | `python3 src/scripts/generate_training_data.py [--count 200] [--output training_data.jsonl] [--dry-run]` |
| `--dry-run` | Génère seulement les questions, sans appeler le LLM |
| Sortie | Fichier JSONL (rôles system/user/assistant + metadata) |
| Cron suggéré | Aucun (lancement manuel avant un fine-tuning) |

## Variables d'environnement

Les scripts chargent le `.env` à la racine du projet (`load_dotenv`).

| Variable | Description | Défaut | Scripts |
|----------|-------------|--------|---------|
| `DATABASE_URL` | DSN PostgreSQL | `postgresql://localhost:5432/tawiza` | `detect_anomalies_v2`, `embed_signals`, `watcher`, `collect_all_v2` |
| `COLLECTOR_DATABASE_URL` | DSN PostgreSQL (collecteur) | `postgresql+asyncpg://localhost:5432/tawiza` | `generate_training_data`, `scoring_composite` |
| `OLLAMA_URL` | URL du serveur Ollama | `http://localhost:11434` | `generate_training_data`, `embed_signals` |
| `FRANCE_TRAVAIL_CLIENT_ID` / `FRANCE_TRAVAIL_CLIENT_SECRET` | Identifiants API France Travail | - | `collect_all_v2` |
| `INSEE_CLIENT_ID` / `INSEE_CLIENT_SECRET` | Identifiants API INSEE | - | `collect_all_v2` |

Le suffixe `+asyncpg` est retiré automatiquement avant connexion `asyncpg`.

## Fichiers clés

```
src/scripts/
├── collect_all_v2.py          # Collecteur unifié 8 sources → signals
├── detect_anomalies_v2.py     # Isolation Forest + DBSCAN → anomaly_detection_v2
├── embed_signals.py           # Embeddings pgvector → signal_embeddings
├── scoring_composite.py       # 6 alpha factors (lib API) → territorial_snapshots
├── scheduler.py               # APScheduler, orchestre collectes + détection
├── watcher.py                 # Daemon Z-score → watcher_alerts
└── generate_training_data.py  # QA pairs synthétiques → JSONL fine-tuning
```

## État actuel

- `collect_all_v2`, `detect_anomalies_v2`, `scoring_composite` et `watcher` sont fonctionnels et alimentent leurs tables respectives
- `scheduler` orchestre l'ensemble du pipeline batch en continu
- `embed_signals` dépend d'Ollama (`nomic-embed-text`) pour la recherche sémantique pgvector
- `generate_training_data` produit des données SFT mais le fine-tuning n'est pas activé en production

## Limitations connues

- Le scheduler appelle `detect_microsignals_v2`, `detect_temporal` et `alert_telegram` en import optionnel : si un module manque, le job est ignoré silencieusement (warning)
- Le watcher tourne avec un état en mémoire : pas de reprise après redémarrage
- Les scripts nécessitant Ollama (`embed_signals`, `generate_training_data`) échouent si le serveur LLM est indisponible
- Les collectes France Travail et INSEE requièrent des identifiants API valides dans le `.env`
