# Signaux & Anomalies

Module de détection de micro-signaux économiques territoriaux. Identifie des tendances et anomalies **avant** qu'elles soient visibles dans les statistiques officielles, en croisant de multiples sources de données.

## Architecture

```
Sources de données (SIRENE, BODACC, France Travail, DVF, ...)
         │
         ▼
┌────────────────────────┐
│   SignalDetector        │   Croisement multi-sources
│   (signal_detector.py)  │   Seuils adaptatifs
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│   MicroSignals API      │   Détection en arrière-plan
│   (microsignals.py)     │   Historique, validation, stats
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│   Dashboard Frontend    │   Visualisation temps réel
│   Alertes & Tendances   │
└────────────────────────┘
```

## Types de signaux

### Catégories

| Catégorie | Code | Description |
|-----------|------|-------------|
| **Crise** | `crisis` | Alertes de défaillance, liquidations en hausse |
| **Croissance** | `growth` | Dynamisme, créations d'entreprises, embauches |
| **Mutation** | `mutation` | Transformation sectorielle, changements de NAF |
| **Emploi** | `employment` | Variations des offres, tensions sur le marché |
| **Marchés publics** | `public_market` | Volumes de marchés, secteurs actifs |
| **Innovation** | `innovation` | Brevets, startups, investissements R&D |

### Sévérité

| Niveau | Code | Signification |
|--------|------|---------------|
| Critique | `critical` | Action immédiate requise |
| Alerte | `warning` | À surveiller |
| Info | `info` | Information contextuelle |
| Opportunité | `opportunity` | Opportunité détectée |

## Pipeline de traitement

1. **Collecte** : Les indicateurs sont extraits de chaque source (SIRENE créations, BODACC radiations, DVF transactions, etc.)
2. **Normalisation** : Chaque indicateur est converti en `SignalIndicator` avec valeur, seuil, direction et poids
3. **Croisement** : Les indicateurs de sources différentes sont croisés pour confirmer/infirmer un signal
4. **Scoring** : Un score de confiance est calculé selon le nombre de sources concordantes
5. **Émission** : Les signaux détectés sont stockés en base et exposés via l'API

## Détection de micro-signaux

Le script `detect_microsignals_v2.py` exécute la détection en arrière-plan :

```python
# Indicateur individuel
@dataclass
class SignalIndicator:
    name: str           # Nom de l'indicateur
    source: str         # Source (sirene, bodacc, france_travail, dvf...)
    value: float        # Valeur observée
    threshold: float    # Seuil de déclenchement
    direction: str      # "up", "down", "stable"
    weight: float       # Poids dans le calcul final
```

Un indicateur est **déclenché** quand `value > threshold` (direction up) ou `value < threshold` (direction down).

## API

### Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/microsignals/detect` | Lance une détection en arrière-plan |
| `GET` | `/api/v1/microsignals/status` | Statut de la dernière détection |
| `GET` | `/api/v1/microsignals/` | Liste des micro-signaux détectés |
| `GET` | `/api/v1/microsignals/stats` | Statistiques agrégées |

## Fichiers clés

```
src/infrastructure/agents/tajine/territorial/
├── signal_detector.py        # Détecteur principal multi-sources
├── predictive_signals.py     # Signaux prédictifs
├── metrics_collector.py      # Collecte de métriques territoriales
└── narrative_analyzer.py     # Analyse narrative des tendances

src/interfaces/api/v1/
├── microsignals.py           # API micro-signaux (CRUD + détection)
└── signals.py                # API signaux (requêtes simples)

src/scripts/
└── detect_microsignals_v2.py # Script de détection batch
```

## Configuration

La détection utilise la base PostgreSQL pour stocker les signaux :

| Variable | Description |
|----------|-------------|
| `COLLECTOR_DATABASE_URL` | URL PostgreSQL pour le stockage des signaux |

Les seuils sont définis dans le code (`signal_detector.py`) et seront configurables dans une future version.

## État actuel

- La détection de base fonctionne par croisement SIRENE/BODACC/DVF
- L'API de gestion des micro-signaux est opérationnelle
- La détection en arrière-plan est fonctionnelle via le script batch
- En cours de validation sur des données réelles de plusieurs départements

## Limitations connues

- Les seuils de détection sont codés en dur (pas encore configurables dynamiquement)
- La couverture des sources est inégale selon les territoires
- Pas encore de ML avancé (Isolation Forest, etc.) — détection par seuils statistiques
- La fréquence de détection est manuelle (pas de cron automatique en production)
- Les signaux prédictifs (`predictive_signals.py`) sont au stade expérimental
