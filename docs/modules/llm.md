# Infrastructure LLM

Module d'inférence et d'adaptation LLM pour Tawiza. Il fournit les clients
utilisés par les agents, les services applicatifs, les outils MCP, le débat
assisté par IA, la vision et les embeddings.

## Rôle

`src/infrastructure/llm/` est la couche d'accès aux modèles. Elle isole le
reste de l'application des détails d'appel à Ollama, des API compatibles chat,
du routage entre modèles et des optimisations de batch.

Le module sert principalement à :

- générer du texte pour TAJINE, les agents autonomes et les outils MCP ;
- appeler Ollama en local pour le chat, les complétions, la vision et les
  embeddings ;
- router une demande vers un modèle local ou plus puissant selon la complexité ;
- basculer entre plusieurs providers quand un backend échoue ;
- adapter les modèles texte/vision aux composants de débat et d'analyse
  d'images ;
- mutualiser les appels répétés via batching, déduplication et cache optionnel.

## Architecture

```text
Agents, API, services applicatifs
        |
        v
src/infrastructure/llm/
        |
        +-- OllamaClient
        |      -> /api/generate, /api/chat, /api/embed
        |
        +-- HybridLLMRouter
        |      -> TaskComplexityAnalyzer
        |      -> Ollama local model / powerful model
        |      -> OumiClient stub with Ollama fallback
        |
        +-- MultiProviderLLM
        |      -> Ollama
        |      -> OpenAI-compatible API
        |      -> Anthropic API
        |      -> CAMELModelBackend adapter
        |
        +-- AdaptiveLLMProvider + VisionAnalyzer
        |      -> text model for text prompts
        |      -> vision model when image bytes are present
        |
        +-- LLMBatcher + EmbeddingBatcher
        |      -> time-window batching
        |      -> deduplication
        |      -> optional cache lookup
        |
        +-- LitServeClient + OllamaLitServe
               -> optional optimized serving on http://localhost:8001
```

## Composants

### `ollama_client.py` - OllamaClient

Client asynchrone HTTPX pour Ollama. Il expose :

- `generate()` pour les complétions texte via `/api/generate` ;
- `chat()` pour les conversations et tool calls via `/api/chat` ;
- `analyze_screenshot()` pour les modèles vision ;
- `embed()` et `embed_batch()` via `/api/embed` ;
- `health_check()`, `discover_models()` et `select_best_model()` pour détecter
  les modèles disponibles.

Les appels des agents utilisent ce client directement quand un raisonnement
local suffit.

### `hybrid_router.py` - HybridLLMRouter

Routeur intelligent utilisé par TAJINE. `TaskComplexityAnalyzer` estime la
complexité du prompt par longueur, mots-clés stratégiques, mots-clés analytiques
et signaux temporels.

Le routeur envoie ensuite la requête vers :

- le modèle local pour les tâches simples ou modérées ;
- le modèle puissant pour les tâches complexes, stratégiques ou à faible score
  de confiance ;
- `OumiClient` quand le mode forcé `oumi` est demandé.

`OumiClient` est actuellement un stub : il revient vers Ollama si un fallback est
fourni, sinon il retourne une réponse de test.

### `multi_provider.py` - MultiProviderLLM

Abstraction multi-provider avec failover par priorité. Les providers
implémentés sont :

| Provider | Client | Usage |
|----------|--------|-------|
| Ollama | `OllamaLLMClient` | backend local primaire |
| OpenAI | `OpenAILLMClient` | API compatible `/chat/completions` |
| Anthropic | `AnthropicLLMClient` | API Claude `/v1/messages` |

`create_default_multi_provider()` crée toujours un provider Ollama, puis ajoute
OpenAI et Anthropic si leurs clés sont disponibles. `CAMELModelBackend` adapte ce
routeur à l'interface attendue par les agents CAMEL.

### `adaptive_provider.py` et `vision_analyzer.py`

`AdaptiveLLMProvider` implémente le protocole `LLMProvider` du domaine débat. Il
utilise le modèle texte par défaut quand le prompt ne contient pas d'image, puis
le modèle vision si `images` est fourni.

`VisionAnalyzer` ajoute des opérations de haut niveau :

- analyse libre de screenshot ;
- extraction d'informations d'entreprise ;
- comparaison de deux screenshots.

### `llm_batcher.py`

`LLMBatcher` collecte les requêtes pendant une fenêtre courte, les regroupe par
modèle, déduplique les prompts identiques et exécute les batches avec une limite
de concurrence.

`EmbeddingBatcher` spécialise le même principe pour les embeddings, avec cache
en mémoire par hash du texte.

### `litserve_client.py` et `litserve_wrapper.py`

LitServe est optionnel. `OllamaLitServe` enveloppe `OllamaAdapter` derrière un
serveur LitServe capable de traiter des complétions, chats et embeddings.
`LitServeClient` appelle ce serveur via `/predict` et expose une interface proche
de l'adapter Ollama.

Le streaming n'est pas supporté par `LitServeClient` : les appels `stream=True`
sont convertis en appels non-streaming avec un warning.

### `factory.py`

Factories pour créer des composants LLM préconfigurés :

- `create_debate_system_with_llm()` crée un `DebateSystem` avec
  `AdaptiveLLMProvider` ;
- `create_vision_analyzer()` crée un `VisionAnalyzer` alimenté par le provider
  adaptatif.

## Fichiers clés

```text
src/infrastructure/llm/
|-- __init__.py             # Exports publics du module
|-- adaptive_provider.py    # Sélection texte/vision
|-- factory.py              # Factories débat et vision
|-- hybrid_router.py        # Routage local/powerful/oumi
|-- litserve_client.py      # Client HTTP vers LitServe
|-- litserve_wrapper.py     # Serveur LitServe autour d'OllamaAdapter
|-- llm_batcher.py          # Batching LLM et embeddings
|-- multi_provider.py       # Providers Ollama/OpenAI/Anthropic + failover
|-- ollama_client.py        # Client Ollama direct
`-- vision_analyzer.py      # Services d'analyse d'images
```

## Configuration

| Variable | Description | Défaut |
|----------|-------------|--------|
| `OLLAMA_BASE_URL` | URL du serveur Ollama pour les clients directs et le routeur | `http://localhost:11434` |
| `OLLAMA_MODEL_NAME` | Modèle Ollama par défaut exposé par `src/core/config.py` | `qwen2.5:7b` |
| `OLLAMA_EMBEDDING_MODEL` | Modèle d'embedding exposé par `src/core/config.py` | `nomic-embed-text` |
| `OLLAMA_TIMEOUT` | Timeout des requêtes Ollama | `300` dans `src/core/config.py`, `120` dans `docs/configuration.md` |
| `OLLAMA_MODEL_POWERFUL` | Modèle puissant utilisé par `HybridLLMRouter` si aucun argument explicite n'est fourni | même valeur que le modèle local |
| `OPENAI_API_KEY` | Active le provider OpenAI dans `create_default_multi_provider()` | non défini |
| `ANTHROPIC_API_KEY` | Active le provider Anthropic dans `create_default_multi_provider()` | non défini |
| `VECTORDB__USE_LITSERVE` | Active LitServe pour le service d'embeddings configuré dans `src/infrastructure/config/settings.py` | `false` |
| `VECTORDB__LITSERVE_URL` | URL du serveur LitServe pour les embeddings | `http://localhost:8001` |

Les README mentionnent aussi Groq/OpenRouter comme options cloud produit. Dans
ce module précis, le failover implémenté est Ollama -> OpenAI-compatible ->
Anthropic ; une intégration Groq/OpenRouter native devra être ajoutée séparément
si l'on veut l'exposer ici.

## Points d'intégration

- `src/infrastructure/agents/tajine/tajine_agent.py` lazy-load
  `HybridLLMRouter` et `OllamaClient` pour le raisonnement ;
- `src/infrastructure/agents/tajine/planning.py` utilise `OllamaClient` pour la
  décomposition de tâches ;
- `src/application/services/agent_orchestrator.py` garde un client Ollama pour
  les fonctionnalités agentiques ;
- `src/application/services/embedding_service.py` peut créer un `LitServeClient`
  pour accélérer les embeddings ;
- `src/infrastructure/dashboard/api.py` et les outils MCP appellent les
  factories de débat ;
- `tests/unit/infrastructure/llm/` et `tests/infrastructure/llm/` couvrent les
  providers, le routeur, l'auto-détection Ollama, la vision et les factories.

## État actuel

- `OllamaClient`, `HybridLLMRouter`, `MultiProviderLLM`,
  `AdaptiveLLMProvider` et `VisionAnalyzer` disposent de tests unitaires.
- Le routage local/powerful repose sur des heuristiques simples et ne mesure pas
  encore le coût réel, la latence historique ou la qualité des sorties.
- `OumiClient` est un stub avec fallback optionnel vers Ollama.
- Deux piles Ollama coexistent : `src/infrastructure/llm/ollama_client.py` pour
  les agents et `src/infrastructure/ml/ollama/` pour l'adapter ML. LitServe
  dépend de l'adapter ML.
- Le failover cloud de `MultiProviderLLM` supporte OpenAI et Anthropic, mais pas
  encore les variables `GROQ_API_KEY` et `OPENROUTER_API_KEY` annoncées dans les
  README.
- Le client LitServe ne supporte pas le streaming.

## Limitations connues

- Les modèles par défaut varient selon les fichiers (`qwen2.5:7b`,
  `qwen3.5:27b`, `qwen3-coder:30b`) ; il faut vérifier le chemin d'appel avant
  de changer une valeur globale.
- Les erreurs de génération peuvent déclencher un fallback, mais pas tous les
  appels disposent d'un provider secondaire configuré.
- Les clients HTTP doivent être fermés via `close()` dans les usages long-lived
  pour éviter de conserver des connexions ouvertes.
- Les prompts vision supposent que le modèle configuré accepte le champ
  `images` d'Ollama.
