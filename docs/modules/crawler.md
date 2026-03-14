# Crawler Adaptatif

Module de crawling web intelligent avec optimisation par Multi-Armed Bandit (MAB). Le crawler sélectionne automatiquement les meilleures sources et stratégies de collecte selon les résultats obtenus.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   AdaptiveCrawler                        │
│                                                         │
│  ┌──────────────────┐     ┌─────────────────────────┐   │
│  │   MABScheduler   │     │     ParserRegistry      │   │
│  │   (UCB algo)     │     │  HTML · JSON · Feed     │   │
│  └────────┬─────────┘     └────────────┬────────────┘   │
│           │                            │                │
│  ┌────────▼────────────────────────────▼────────────┐   │
│  │              Worker Pool (async)                  │   │
│  │                                                   │   │
│  │  ┌──────────────┐  ┌───────────────────────────┐  │   │
│  │  │ HTTPXWorker  │  │ PlaywrightWorker          │  │   │
│  │  │ (statique)   │  │ (JS-heavy, lazy-loaded)   │  │   │
│  │  └──────────────┘  └───────────────────────────┘  │   │
│  │                                                   │   │
│  │  ┌──────────────────────────────────────────────┐ │   │
│  │  │         RateLimiter (par domaine)            │ │   │
│  │  └──────────────────────────────────────────────┘ │   │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Composants

### Scheduler MAB (`scheduler/`)

Le `MABScheduler` utilise l'algorithme **Upper Confidence Bound (UCB)** pour sélectionner les sources à crawler en priorité. Chaque source est un "bras" du bandit avec un score de récompense.

- `mab_scheduler.py` : Ordonnanceur principal UCB
- `linucb_scheduler.py` : Variante LinUCB contextuelle (prend en compte le territoire et le secteur)
- `source_arm.py` : Modèle d'un bras/source avec statistiques (essais, récompenses, UCB score)

Types de sources supportées :
- `api` : API REST (INSEE, SIRENE, etc.)
- `rss` : Flux RSS
- `web` : Pages web statiques
- `dynamic` : Sites JavaScript nécessitant un rendu navigateur

### Workers (`workers/`)

| Worker | Utilisation | Performance |
|--------|-------------|-------------|
| `HTTPXWorker` | Contenu statique (APIs, RSS, HTML simple) | Rapide, léger |
| `PlaywrightWorker` | Sites JS-heavy (societe.com, pappers.fr, etc.) | Plus lent, consomme plus |

Le `PlaywrightWorker` est **lazy-loaded** : il n'est initialisé que quand un site JS-heavy est rencontré.

Sites JS-heavy connus (détection automatique) :
- `app.sirene.fr`
- `annuaire-entreprises.data.gouv.fr`
- `societe.com`, `pappers.fr`, `infogreffe.fr`, `verif.com`

Composants auxiliaires :
- `rate_limiter.py` : Limites par domaine (ex: 100 req/min pour api.insee.fr)
- `headers_manager.py` : Rotation de User-Agent et headers réalistes
- `proxy_pool.py` : Pool de proxies pour la distribution des requêtes

### Backends stealth

Pour les sites avec protection anti-bot, le crawler peut utiliser :
- **Camoufox** : Firefox modifié pour éviter la détection
- **Nodriver** : Driver Chrome sans détection Selenium

Ces backends sont utilisés via le `PlaywrightWorker` quand les protections standard échouent.

### Parsers (`parsers/`)

| Parser | Format | Description |
|--------|--------|-------------|
| `HTMLParser` | HTML | Extraction de contenu structuré depuis le DOM |
| `JSONParser` | JSON | Parsing de réponses API |
| `FeedParser` | RSS/Atom | Parsing de flux de syndication |

Le `ParserRegistry` sélectionne automatiquement le parser selon le Content-Type de la réponse.

## Événements

Le crawler émet des événements via `CrawlerCallback` pour le streaming temps réel :

| Événement | Description |
|-----------|-------------|
| `crawl_started` | Début d'un crawl |
| `page_fetched` | Page récupérée avec succès |
| `page_failed` | Échec de récupération |
| `crawl_completed` | Fin du crawl |

Ces événements sont relayés à l'agent TAJINE pour affichage dans le panel Agent Live.

## Fichiers clés

```
src/infrastructure/crawler/
├── adaptive_crawler.py       # Crawler principal
├── events.py                 # Événements et callbacks
├── scheduler/
│   ├── mab_scheduler.py      # Ordonnanceur UCB
│   ├── linucb_scheduler.py   # Variante contextuelle
│   └── source_arm.py         # Modèle de source/bras
├── workers/
│   ├── httpx_worker.py       # Worker HTTP statique
│   ├── playwright_worker.py  # Worker navigateur JS
│   ├── rate_limiter.py       # Rate limiting par domaine
│   ├── headers_manager.py    # Gestion des headers
│   └── proxy_pool.py         # Pool de proxies
├── parsers/
│   ├── html_parser.py        # Parser HTML
│   ├── json_parser.py        # Parser JSON
│   ├── feed_parser.py        # Parser RSS/Atom
│   └── registry.py           # Registre de parsers
└── tasks/                    # Tâches de crawl asynchrones
```

## Configuration

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| `exploration_param` | Exploration UCB (plus haut = plus exploratoire) | `2.0` |
| `max_concurrent` | Workers parallèles maximum | `10` |
| `enable_playwright` | Activer le rendu JS | `true` |

Limites de rate par domaine (configurées dans le code) :
- `api.insee.fr` : 100 req/min
- `data.gouv.fr` : 50 req/min

## État actuel

- Le crawler de base avec MAB et dual-worker (HTTPX + Playwright) est fonctionnel
- Le rate limiting par domaine fonctionne
- Le LinUCB contextuel est implémenté mais peu testé
- Les backends stealth (Camoufox, Nodriver) sont intégrés mais pas activés par défaut
- En cours de stabilisation pour les sites avec protections anti-bot avancées

## Limitations connues

- Le proxy pool nécessite une configuration manuelle des proxies
- Le Playwright Worker consomme beaucoup de mémoire sur les crawls longs
- Pas de détection automatique de CAPTCHAs (échec silencieux)
- Le scheduler MAB perd son apprentissage au redémarrage (pas de persistence)
- Le parsing HTML est générique — pas de parsers spécialisés par site
