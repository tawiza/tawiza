# Investigation & Risk

Module d'investigation approfondie et d'évaluation de risque pour les entreprises. Combine raisonnement bayésien, extraction de signaux multi-sources et scoring ML pour produire des évaluations de risque détaillées.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Investigation Pipeline                    │
│                                                         │
│  ┌──────────────┐     ┌───────────────┐                 │
│  │   Signal     │────▶│   Bayesian    │                 │
│  │  Extractor   │     │   Reasoner    │                 │
│  └──────┬───────┘     └───────┬───────┘                 │
│         │                     │                         │
│         │  ┌──────────────────▼─────────────────────┐   │
│         │  │            Risk Scorer                  │   │
│         └─▶│  XGBoost / Heuristic fallback          │   │
│            └──────────────────┬─────────────────────┘   │
│                               │                         │
│            ┌──────────────────▼─────────────────────┐   │
│            │         Report Generator               │   │
│            │   Rapport structuré + explications      │   │
│            └────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Raisonnement bayésien (`bayesian_reasoner.py`)

### Approche

Le raisonneur bayésien calcule la probabilité de risque d'une entreprise :

1. **Prior** : Taux de défaillance moyen du secteur d'activité (données historiques BODACC)
2. **Likelihood Ratios** : Multiplicateurs pour chaque signal observé (positif ou négatif)
3. **Posterior** : Probabilité ajustée après observation de tous les signaux

```
P(risque | signaux) = P(risque) * LR1 * LR2 * ... * LRn / normalisation
```

### Niveaux de risque

| Niveau | Code | Plage |
|--------|------|-------|
| Faible | `FAIBLE` | 0-15% |
| Modéré | `MODERE` | 15-30% |
| Modéré-Élevé | `MODERE-ELEVE` | 30-50% |
| Élevé | `ELEVE` | 50-70% |
| Critique | `CRITIQUE` | 70-100% |

### Résultat

```python
@dataclass
class RiskAssessment:
    prior: float              # Taux de défaillance du secteur
    posterior: float           # Probabilité ajustée
    risk_level: RiskLevel      # Classification
    confidence: float          # Confiance (0-1)
    data_coverage: float       # Couverture des données (0-1)
    key_factors: list          # Facteurs contributifs ordonnés
    main_concerns: list[str]   # Préoccupations principales
```

## Extraction de signaux (`signal_extractor.py`)

Collecte parallèle depuis plusieurs sources :

| Source | Signaux extraits |
|--------|-----------------|
| **BODACC** | Privilèges, procédures collectives, cessions, modifications |
| **SIRENE** | Effectifs, forme juridique, ancienneté, établissements |
| **INPI** | Dirigeants, mandats multiples, changements de direction |
| **Web** | Avis, actualités, réputation en ligne |

### Catégories de signaux

| Catégorie | Description | Impact typique |
|-----------|-------------|----------------|
| `financial` | Signaux financiers (privilèges, incidents) | Négatif à critique |
| `legal` | Signaux juridiques (procédures, contentieux) | Négatif |
| `operational` | Signaux opérationnels (effectifs, activité) | Variable |
| `director` | Signaux sur les dirigeants (mandats, changements) | Variable |
| `weak_signal` | Signaux faibles (actualités, tendances) | Variable |

### Structure d'un signal

```python
@dataclass
class Signal:
    category: SignalCategory       # financial, legal, ...
    name: str                      # Nom descriptif
    value: Any                     # Valeur observée
    source: str                    # Source (bodacc, sirene, ...)
    impact: SignalImpact           # positive, neutral, negative, critical
    likelihood_ratio: float        # Multiplicateur bayésien
    details: str                   # Description
```

## Scoring de risque ML (`risk/scorer.py`)

### Modèle principal : XGBoost

Le `RiskScorer` utilise XGBoost pour prédire un score de risque 0-100 :

- **Features** (`features.py`) : Extraction de caractéristiques depuis les données SIRENE/BODACC (âge, effectif, secteur, nombre d'établissements, etc.)
- **Fallback heuristique** : Si XGBoost n'est pas disponible, un scoring par règles pondérées est utilisé
- **Intervalles de confiance** : Chaque score est accompagné d'un intervalle (lower, upper)

### Niveaux de risque

| Niveau | Score | Code |
|--------|-------|------|
| Très faible | 0-15 | `TRES_FAIBLE` |
| Faible | 15-30 | `FAIBLE` |
| Modéré | 30-50 | `MODERE` |
| Élevé | 50-70 | `ELEVE` |
| Très élevé | 70-85 | `TRES_ELEVE` |
| Critique | 85-100 | `CRITIQUE` |

### Explainability

Le `RiskExplainer` (`risk/explainer.py`) fournit des explications humaines pour chaque score :
- Top facteurs contributifs avec poids
- Comparaison avec la moyenne du secteur
- Recommandations d'action

## Cascade model

Le pipeline complet pour une investigation d'entreprise :

1. **Signal Extraction** : Collecte parallèle depuis toutes les sources
2. **Bayesian Reasoning** : Calcul du posterior avec les likelihood ratios
3. **ML Scoring** : Score XGBoost + intervalle de confiance
4. **Report Generation** : Rapport structuré combinant les deux approches
5. **Knowledge Graph Update** : Mise à jour du KG avec les nouvelles relations découvertes

## API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/investigation/investigate` | Lancer une investigation complète |
| `GET` | `/api/v1/investigation/{siren}` | Récupérer le résultat d'une investigation |

## Fichiers clés

```
src/infrastructure/agents/tajine/investigation/
├── bayesian_reasoner.py     # Raisonnement bayésien
├── signal_extractor.py      # Extraction multi-sources
├── investigation_tool.py    # Outil d'investigation pour l'agent
└── report_generator.py      # Génération de rapports

src/infrastructure/agents/tajine/risk/
├── scorer.py                # Risk Scorer (XGBoost + fallback)
├── features.py              # Feature extraction (EnterpriseFeatures)
└── explainer.py             # Explications humaines du score

src/interfaces/api/v1/
└── investigation.py         # Endpoints API
```

## Configuration

Pas de variables d'environnement spécifiques. Le module utilise :
- `DATABASE_URL` pour les priors sectoriels (BODACC historique)
- `OLLAMA_BASE_URL` pour la génération de rapports narratifs (optionnel)

## État actuel

- L'extraction de signaux BODACC/SIRENE est fonctionnelle
- Le raisonnement bayésien produit des évaluations cohérentes
- Le scoring heuristique (fallback) fonctionne
- Le modèle XGBoost n'est pas encore entraîné sur des données réelles
- La génération de rapports est basique (pas encore de narration LLM)
- En cours de validation avec des cas réels de défaillances connues

## Limitations connues

- Les priors sectoriels (`SECTOR_PRIORS`) sont des estimations statiques, pas des données INSEE actualisées
- L'extraction INPI n'est pas encore implémentée (dirigeants)
- Le modèle XGBoost nécessite un dataset d'entraînement labellisé (non disponible)
- La couverture des signaux web (avis, actualités) est limitée
- Pas de mise à jour incrémentale  -  chaque investigation repart de zéro
