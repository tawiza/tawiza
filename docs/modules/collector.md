# Collector

Pipeline de collecte de micro-signaux territoriaux. Interroge des sources publiques françaises (APIs + crawling), normalise les données, détecte des anomalies par recoupement, puis calcule des scores territoriaux quantitatifs. Le tout est orchestré par un scheduler et exposé via une API REST.

## Positionnement vs Data Hunter et Crawler

Trois modules manipulent des sources de données, avec des rôles distincts :

- **Collector** (ce module) : pipeline de fond **autonome et planifié**. Collecte en continu sur un ensemble fixe de départements, écrit dans la table `signals` PostgreSQL, et calcule des scores territoriaux. Indépendant de l'agent.
- **Data Hunter** (voir `data-hunter.md`) : collecte **à la demande**, déclenchée par l'agent TAJINE pour répondre à une requête utilisateur (4 stratégies adaptatives).
- **Crawler** (voir `crawler.md`) : moteur de crawling web générique avec MAB, utilisé comme **renfort** par le Data Hunter. Le Collector a son propre pipeline de crawling presse (`crawling/`), plus simple et spécialisé.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       CollectorScheduler                          │
│              (APScheduler - jobs cron + watchdog réseau)          │
└───────────────┬──────────────────────────────┬──────────────────┘
                │                               │
       ┌────────▼─────────┐           ┌─────────▼──────────┐
       │   collectors/    │           │     crawling/      │
       │  APIs (13)       │           │  Presse locale     │
       │  + crawlers (2)  │           │  Trafilatura + NLP │
       └────────┬─────────┘           └─────────┬──────────┘
                │                               │
                │      ┌──────────────────┐     │
                └─────▶│   processing/    │◀────┘
                       │ NLP · Geo · OCR  │
                       └────────┬─────────┘
                                │
                       ┌────────▼─────────┐
                       │    storage/      │
                       │ signals (PG)     │
                       └────────┬─────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                    │
   ┌────────▼────────┐ ┌────────▼────────┐ ┌─────────▼────────┐
   │  crossref +     │ │     quant/      │ │      epci/       │
   │  detection/     │ │ scoring · qlib  │ │ scores par       │
   │  anomalies      │ │ ML · temporel   │ │ intercommunalité │
   └─────────────────┘ └─────────────────┘ └──────────────────┘
```

## Composants

### Collecteurs (`collectors/`)

Tous les collecteurs héritent de `BaseCollector` (`collectors/base.py`), qui fournit rate limiting (token bucket), retry avec backoff exponentiel, client HTTP mutualisé et statistiques. Chaque collecteur produit des `CollectedSignal` (source, date, code géographique, métrique, type de signal, confiance).

Collecteurs API (`collectors/api/`) :

| Collecteur | Source | Données |
|------------|--------|---------|
| `sirene.py` | INSEE SIRENE | Créations / radiations d'entreprises |
| `bodacc.py` | BODACC | Procédures collectives (liquidations, redressements) |
| `france_travail.py` | France Travail | Offres d'emploi |
| `dvf.py` | DVF | Transactions immobilières, prix au m² |
| `sitadel.py` | Sitadel | Permis de construire (logements + locaux) |
| `dgfip.py` | DGFiP | Données fiscales (data.economie.gouv.fr) |
| `urssaf.py` | URSSAF | Emploi et cotisations sociales |
| `caf.py` | CAF | Prestations sociales |
| `education_nationale.py` | Éducation Nationale | Données scolaires |
| `banque_france.py` | Banque de France | Statistiques de défaillances |
| `google_trends.py` | Google Trends | Intérêt de recherche par région |
| `gdelt.py` | GDELT | Signaux presse (GDELT v2 Doc API) |
| `commoncrawl.py` | Common Crawl | Intelligence web via snapshots archivés (LLM + WARC) |

Crawlers (`collectors/crawlers/`) :

| Crawler | Cible | Détail |
|---------|-------|--------|
| `presse_locale.py` | Presse régionale | Flux RSS + extraction Trafilatura |
| `leboncoin.py` | LeBonCoin | Signaux de détresse d'entreprises (Playwright anti-bot) |

### Pipeline de crawling (`crawling/`)

Le `CrawlingPipeline` (`crawling/pipeline.py`) est l'algorithme cœur de détection de micro-signaux presse, en 8 étapes : découverte d'URL → fetch (Trafilatura, fallback Playwright) → extraction de texte → analyse NLP (mots-clés + NER spaCy) → scoring de confiance → résolution géographique → stockage → recoupement.

Les règles de signal (`SignalRule`) mappent des listes de mots-clés français à un type (`positif`, `negatif`, `neutre`) et une métrique.

`crawling/crossref.py` contient le moteur de **détection cross-source** : il recoupe les signaux de plusieurs sources via des `CrossRefPattern` (z-score par condition, minimum de sources convergentes) pour produire des `MicroSignal` (déclin territorial, dynamisme territorial, tension emploi, crise sectorielle). Les micro-signaux détectés sont persistés en tant qu'anomalies.

### Traitement (`processing/`)

| Fichier | Rôle |
|---------|------|
| `nlp.py` | `FrenchNLP` : NER spaCy français (LOC, ORG, PER, MISC) |
| `geocoder.py` | Résolution géographique via `french-cities` (commune → INSEE, code postal → commune, commune → département/EPCI) |
| `ocr.py` | OCR de documents (PDF BODACC, captures, permis) via GLM-OCR sur Ollama |
| `contextualizer.py` | Génération de descriptions lisibles des anomalies via Ollama (LLM local) |

### Stockage (`storage/`)

Modèles SQLAlchemy (`storage/models.py`) :
- `Signal` : table unifiée `signals` pour tous les signaux collectés (source, localisation, métrique, type, confiance, données brutes JSONB). Contrainte d'unicité `(source, source_url, event_date)`.
- `Anomaly` : table `anomalies` pour les détections cross-source.

`storage/repository.py` expose `SignalRepository` : repository asynchrone (asyncpg) avec init de schéma, insertion par batch et requêtes filtrées.

### Détection (`detection/`)

`detection/anomaly.py` : détection statistique d'anomalies sur les signaux (z-score, IQR en baseline, PyOD pour le multivarié avancé). Produit des `DetectedAnomaly` classés par `classify_anomaly`. Complémentaire du recoupement cross-source de `crawling/crossref.py`.

### Analyse quantitative (`quant/`)

Inspirée de la finance quantitative, adaptée au territoire. Décomposée en phases :

| Fichier | Phase | Rôle |
|---------|-------|------|
| `factors.py` | 2 | Calcul des facteurs alpha normalisés par département |
| `scoring.py` | 2 | Score de santé territoriale composite (z-score, pondération) |
| `population.py` | - | Population INSEE 2024 pour normalisation |
| `temporal.py` | 3 | Moyennes mobiles, taux de variation, corrélations à retard cross-source |
| `trends.py` | 3 | Détection de changements de tendance (croisements MA + ROC + facteurs) |
| `factor_mining.py` | 4 | Génération et test d'hypothèses de facteurs via Ollama (Information Coefficient) |
| `ml_detection.py` | 4 | Détection non supervisée (Isolation Forest) et clustering (HDBSCAN/DBSCAN) |

Le sous-module `quant/qlib/` adapte les concepts du `DataHandler` de Microsoft QLib à l'intelligence territoriale : les « instruments » deviennent des « territoires » (départements), les métriques financières deviennent des indicateurs territoriaux, et l'analyse est cross-sectionnelle entre territoires.

- `handler.py` : `TerritorialDataHandler`, orchestrateur (charge PostgreSQL, applique les chaînes de traitement, génère les features)
- `expressions.py` : bibliothèque d'`ALPHA_EXPRESSIONS` prédéfinies
- `ops.py` : opérateurs d'expressions alpha (fonctions sur Series/DataFrame MultiIndex date/territoire)
- `processor.py` : transformateurs de données chaînables
- `dataset.py` : `TerritorialDataset`, abstraction pour les workflows ML

### Granularité EPCI (`epci/`)

Analyse au niveau intercommunalité plutôt que département.

- `referentiel.py` : mapping des ~34 871 communes vers leurs ~1 255 EPCIs, téléchargé et caché depuis geo.api.gouv.fr
- `enrichment.py` : enrichissement par batch des signaux existants (ajout de `code_epci` à partir de `code_commune`)
- `scoring.py` : scoring composite agrégé au niveau EPCI

### Scheduler (`scheduler/`)

`scheduler/jobs.py` - `CollectorScheduler` (APScheduler) tourne dans le cycle de vie du backend FastAPI. Jobs configurés :

| Job | Fréquence | Contenu |
|-----|-----------|---------|
| `api_collectors` | Quotidien 6h + 18h | Collecteurs API sur tous les départements |
| `crawling_pipeline` | Toutes les 4h | Pipeline presse locale (Trafilatura + NLP) |
| `cross_source_detection` | Quotidien 7h | Détection cross-source post-collecte |
| `crawlintel` | Hebdo (dimanche 2h) | Common Crawl (rotation de 3 départements/run) |
| `network_watchdog` | Toutes les 15 min | Relance la collecte au retour du réseau |

Les départements surveillés (`MONITORED_DEPARTMENTS`) couvrent les 15 plus grandes aires urbaines françaises + l'Île-de-France. Les collecteurs lourds (`google_trends`, `presse_locale`, `commoncrawl`) sont **lazy-loaded**.

### API (`api.py`)

Routeur FastAPI préfixé `/api/collector` (rate-limité via slowapi). Principaux endpoints : `signals`, `signals/summary`, `anomalies`, `ranking`, `departments/heatmap`, `departments/scores`, `departments/{dept}/factors`, `departments/{dept}/trends`, `trends/alerts`, `correlations`, `ml/anomalies`, `ml/clusters`, `ml/factors`, `qlib/expressions`, `qlib/features`, `timeline`, `epci/scores`, `scheduler/status`, `run/{collector_name}`.

## Fichiers clés

```
src/collector/
├── api.py                      # Endpoints FastAPI (/api/collector)
├── collectors/
│   ├── base.py                 # BaseCollector + CollectedSignal
│   ├── api/                    # 13 collecteurs API (SIRENE, BODACC, DVF, ...)
│   └── crawlers/               # presse_locale.py, leboncoin.py
├── crawling/
│   ├── pipeline.py             # CrawlingPipeline (8 étapes)
│   └── crossref.py             # Détection cross-source → MicroSignal
├── processing/
│   ├── nlp.py                  # NER spaCy français
│   ├── geocoder.py             # Résolution commune/EPCI/département
│   ├── ocr.py                  # OCR via GLM-OCR / Ollama
│   └── contextualizer.py       # Descriptions LLM des anomalies
├── storage/
│   ├── models.py               # Signal, Anomaly (SQLAlchemy)
│   └── repository.py           # SignalRepository (async)
├── detection/
│   └── anomaly.py              # Détection statistique (z-score, IQR, PyOD)
├── quant/
│   ├── factors.py              # Facteurs alpha (Phase 2)
│   ├── scoring.py              # Score composite (Phase 2)
│   ├── temporal.py             # Analyse temporelle (Phase 3)
│   ├── trends.py               # Détection de tendances (Phase 3)
│   ├── factor_mining.py        # Factor mining LLM (Phase 4)
│   ├── ml_detection.py         # ML non supervisé (Phase 4)
│   ├── population.py           # Population INSEE
│   └── qlib/                   # Adaptation QLib (handler, expressions, ops, ...)
├── epci/
│   ├── referentiel.py          # Mapping commune → EPCI
│   ├── enrichment.py           # Enrichissement code_epci
│   └── scoring.py              # Scoring au niveau EPCI
├── scheduler/
│   └── jobs.py                 # CollectorScheduler (APScheduler)
└── config/
    └── sources.yaml            # Déclaration des sources et seuils de détection
```

## Configuration

Variables d'environnement :

| Variable | Description |
|----------|-------------|
| `COLLECTOR_DATABASE_URL` | URL PostgreSQL des signaux (défaut: `postgresql+asyncpg://localhost:5432/tawiza`) |
| `INSEE_CLIENT_ID` / `INSEE_CLIENT_SECRET` | Identifiants API INSEE (SIRENE) |
| `FRANCE_TRAVAIL_CLIENT_ID` / `FRANCE_TRAVAIL_CLIENT_SECRET` | Identifiants API France Travail |

Le scheduler lit aussi les identifiants depuis un fichier `.env` à la racine du package. Le fichier `config/sources.yaml` déclare les sources (type, schedule cron, rate limit, description), les départements à surveiller et les seuils de détection (`zscore_threshold`, `min_cross_sources`, `lookback_weeks`).

## État actuel

- Le pipeline de bout en bout (collecte → stockage → détection → scoring) est fonctionnel
- 13 collecteurs API + 2 crawlers implémentés, tous héritant de `BaseCollector`
- La détection cross-source et le scoring quantitatif (Phases 2 à 4) sont opérationnels
- Le watchdog réseau relance automatiquement la collecte au retour de connectivité
- Les collecteurs lourds (Common Crawl, presse, Google Trends) sont lazy-loaded
- La granularité EPCI est intégrée mais l'enrichissement se lance manuellement

## Limitations connues

- La collecte porte sur un sous-ensemble fixe de départements (pas toute la France)
- Le crawler LeBonCoin dépend d'un routage anti-bot externe et reste fragile
- Le factor mining et la contextualisation des anomalies dépendent de la disponibilité d'Ollama
- L'OCR (GLM-OCR) et certaines dépendances lourdes sont optionnels
- Les scores quantitatifs nécessitent un historique suffisant pour converger (cold start)
- Le scheduler perd ses statistiques de session au redémarrage (pas de persistance)
