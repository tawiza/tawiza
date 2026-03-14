# Agent TAJINE

Agent cognitif central de Tawiza. TAJINE orchestre l'ensemble du raisonnement et de la collecte de données pour l'intelligence territoriale.

## Architecture — Cycle PPDSL

Le cycle **Perceive-Plan-Delegate-Synthesize-Learn** est le coeur du fonctionnement de TAJINE :

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────────┐    ┌──────────┐
│ PERCEIVE │───▶│   PLAN   │───▶│ DELEGATE │───▶│ SYNTHESIZE │───▶│  LEARN   │
│          │    │          │    │          │    │            │    │          │
│ Intent   │    │ Sous-    │    │ DataHunt │    │ Fusion     │    │ Fine-    │
│ Contexte │    │ tâches   │    │ Browser  │    │ Cognitive  │    │ tuning   │
│ Territoire│   │ Priorité │    │ Manus    │    │ Charts     │    │ Feedback │
└──────────┘    └──────────┘    └──────────┘    └────────────┘    └──────────┘
```

1. **Perceive** : Classifie l'intent utilisateur, extrait le territoire (département/région), le secteur d'activité et l'horizon temporel.
2. **Plan** : Le `StrategicPlanner` décompose la requête en sous-tâches ordonnées par priorité, avec mapping intent-to-tool (rule-based ou LLM-powered via Ollama).
3. **Delegate** : Distribue les sous-tâches aux agents spécialisés — `DataHunter` pour les APIs, `BrowserAgent` pour le web, `ManusAgent` pour les tâches complexes.
4. **Synthesize** : Fusionne les résultats via le `CognitiveEngine`, génère des insights structurés et des visualisations.
5. **Learn** : Collecte les données d'exécution pour le fine-tuning via `DataCollector`, stocke dans la mémoire épisodique.

## Les 5 niveaux cognitifs

Le `CognitiveEngine` traite les résultats à travers 5 niveaux d'abstraction croissante :

| Niveau | Nom | Description | Exemple |
|--------|-----|-------------|---------|
| 1 | **Discovery** | Extraction factuelle | "Il y a 2400 entreprises tech en Haute-Garonne" |
| 2 | **Causal** | Analyse causale (DAG, corrélation) | "La hausse des créations est liée à l'écosystème aéro" |
| 3 | **Scenario** | Simulation what-if (Monte Carlo) | "Avec +15% d'investissement, +8% de créations à 3 ans" |
| 4 | **Strategy** | Recommandations optimales | "Prioriser les subventions R&D pour le secteur health-tech" |
| 5 | **Theoretical** | Principes généraux | "Modèle de cluster d'innovation type Porter" |

Trois modes de fonctionnement :
- **Rule-based** : Sans LLM, analyse par mots-clés et patterns
- **Direct LLM** : Modèle fixe via `LLMProvider`
- **Routed LLM** : Sélection intelligente du modèle via `HybridLLMRouter`

## Modules internes

### `tajine_agent.py` — Agent principal
Point d'entrée du cycle PPDSL. Orchestre les composants.

### `planning.py` — StrategicPlanner
Décomposition de tâches. Mapping intent-to-tool + décomposition LLM via prompt structuré.

### `react_agent.py` — ReAct Agent
Boucle Reason+Act autonome : THINK → ACT (appel outil) → OBSERVE → ANSWER. Jusqu'à 6 itérations. Utilise qwen3.5:27b.

### `llm_router.py` — HybridLLMRouter
Routage entre modèles locaux (Ollama/Qwen) et modèles puissants (CoALM). Deux modes utilisateur : **Fast** (local) et **Complet** (powerful).

### `cognitive/` — Moteur cognitif
- `engine.py` : Orchestrateur des 5 niveaux
- `levels/` : Implémentation de chaque niveau (discovery, causal, scenario, strategy, theoretical)
- `synthesizer.py` : `UnifiedSynthesizer` pour fusionner les 5 niveaux
- `scenario/monte_carlo.py` : Simulations Monte Carlo
- `causal/dag_manager.py` : Graphes de causalité (DAG)
- `reflection.py` : Réflexion et auto-évaluation

### `memory/` — Mémoire épisodique
- `episodic_store.py` : Stockage des interactions passées
- `retriever.py` : Récupération contextuelle pour enrichir les réponses

### `reasoning/` — Raisonnement avancé
- `chain_of_thought.py` : Chaîne de pensée structurée
- `tree_of_thoughts.py` : Exploration arborescente de raisonnements

### `safla/` — Intégration SAFLA
Bridge avec le framework SAFLA pour la mémoire adaptative et la métacognition.

## Fichiers clés

```
src/infrastructure/agents/tajine/
├── tajine_agent.py          # Agent principal (PPDSL)
├── planning.py              # StrategicPlanner
├── react_agent.py           # Boucle ReAct
├── llm_router.py            # Routage LLM
├── delegation.py            # Délégation aux sous-agents
├── departments.py           # Mapping territoires français
├── cognitive/               # 5 niveaux cognitifs
├── hunter/                  # DataHunter (voir data-hunter.md)
├── investigation/           # Investigation (voir investigation.md)
├── risk/                    # Scoring de risque
├── memory/                  # Mémoire épisodique
├── reasoning/               # Chain/Tree of Thoughts
├── learning/                # Fine-tuning et collecte
├── semantic/                # Recherche vectorielle (pgvector/Qdrant)
├── territorial/             # Analyse territoriale spécialisée
├── evaluator/               # Évaluation qualité des réponses
├── validation/              # Validation Knowledge Graph
├── trust.py                 # TrustManager
├── tools/                   # Outils disponibles pour l'agent
└── telemetry/               # Instrumentation et métriques
```

## Configuration

| Variable | Description |
|----------|-------------|
| `OLLAMA_BASE_URL` | URL du serveur Ollama (défaut: `http://localhost:11434`) |
| `OLLAMA_TIMEOUT` | Timeout requêtes LLM en secondes (défaut: `120`) |

Le modèle utilisé par défaut est `qwen3.5:27b` pour le tier LOCAL (mode Fast). Le mode Complet utilise des modèles plus puissants (CoALM 70B+).

## État actuel

- Le cycle PPDSL de base fonctionne de bout en bout
- En cours de simplification et calibrage des niveaux cognitifs
- Le mode ReAct est opérationnel avec 10+ outils
- Le fine-tuning automatique est implémenté mais pas encore activé en production
- L'intégration SAFLA est expérimentale

## Limitations connues

- Le `StrategicPlanner` dépend de la qualité du modèle LLM pour la décomposition complexe
- Les simulations Monte Carlo (niveau Scenario) nécessitent des données historiques suffisantes
- La mémoire épisodique n'a pas encore de mécanisme d'oubli/compaction
- Le routage LLM ne supporte pas encore le fallback automatique si Ollama est indisponible
