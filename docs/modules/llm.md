# Infrastructure LLM

Module d'inference et d'adaptation LLM pour Tawiza. Il fournit les clients
utilises par les agents, les services applicatifs, les outils MCP, le debat
assiste par IA, la vision et les embeddings.

## Role

`src/infrastructure/llm/` est la couche d'acces aux modeles. Elle isole le
reste de l'application des details d'appel a Ollama, des API compatibles chat,
du routage entre modeles et des optimisations de batch.

Le module sert principalement a :

- generer du texte pour TAJINE, les agents autonomes et les outils MCP ;
- appeler Ollama en local pour le chat, les completions, la vision et les
  embeddings ;
- router une demande vers un modele local ou plus puissant selon la complexite ;
- basculer entre plusieurs providers quand un backend echoue ;
- adapter les modeles texte/vision aux composants de debat et d'analyse
  d'images ;
- mutualiser les appels repetes via batching, deduplication et cache optionnel.

## Architecture

```
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

- `generate()` pour les completions texte via `/api/generate` ;
- `chat()` pour les conversations et tool calls via `/api/chat` ;
- `analyze_screenshot()` pour les modeles vision ;
- `embed()` et `embed_batch()` via `/api/embed` ;
- `health_check()`, `discover_models()` et `select_best_model()` pour detecter
  les modeles disponibles.

Les appels des agents utilisent ce client directement quand un raisonnement
local suffit.

### `hybrid_router.py` - HybridLLMRouter

Routeur intelligent utilise par TAJINE. `TaskComplexityAnalyzer` estime la
complexite du prompt par longueur, mots-cles strategiques, mots-cles analytiques
et signaux temporels.

Le routeur envoie ensuite la requete vers :

- le modele local pour les taches simples ou moderees ;
- le modele puissant pour les taches complexes, strategiques ou a faible score
  de confiance ;
- `OumiClient` quand le mode force `oumi` est demande.

`OumiClient` est actuellement un stub : il revient vers Ollama si un fallback est
fourni, sinon il retourne une reponse de test.

### `multi_provider.py` - MultiProviderLLM

Abstraction multi-provider avec failover par priorite. Les providers
implementes sont :

| Provider | Client | Usage |
|----------|--------|-------|
| Ollama | `OllamaLLMClient` | backend local primaire |
| OpenAI | `OpenAILLMClient` | API compatible `/chat/completions` |
| Anthropic | `AnthropicLLMClient` | API Claude `/v1/messages` |

`create_default_multi_provider()` cree toujours un provider Ollama, puis ajoute
OpenAI et Anthropic si leurs cles sont disponibles. `CAMELModelBackend` adapte ce
routeur a l'interface attendue par les agents CAMEL.

### `adaptive_provider.py` et `vision_analyzer.py`

`AdaptiveLLMProvider` implemente le protocole `LLMProvider` du domaine debat. Il
utilise le modele texte par defaut quand le prompt ne contient pas d'image, puis
le modele vision si `images` est fourni.

`VisionAnalyzer` ajoute des operations de haut niveau :

- analyse libre de screenshot ;
- extraction d'informations d'entreprise ;
- comparaison de deux screenshots.

### `llm_batcher.py`

`LLMBatcher` collecte les requetes pendant une fenetre courte, les regroupe par
modele, deduplique les prompts identiques et execute les batches avec une limite
de concurrence.

`EmbeddingBatcher` specialise le meme principe pour les embeddings, avec cache
en memoire par hash du texte.

### `litserve_client.py` et `litserve_wrapper.py`

LitServe est optionnel. `OllamaLitServe` enveloppe `OllamaAdapter` derriere un
serveur LitServe capable de traiter des completions, chats et embeddings.
`LitServeClient` appelle ce serveur via `/predict` et expose une interface proche
de l'adapter Ollama.

Le streaming n'est pas supporte par `LitServeClient` : les appels `stream=True`
sont convertis en appels non-streaming avec un warning.

### `factory.py`

Factories pour creer des composants LLM preconfigures :

- `create_debate_system_with_llm()` cree un `DebateSystem` avec
  `AdaptiveLLMProvider` ;
- `create_vision_analyzer()` cree un `VisionAnalyzer` alimente par le provider
  adaptatif.

## Fichiers cles

```
src/infrastructure/llm/
|-- __init__.py             # Exports publics du module
|-- adaptive_provider.py    # Selection texte/vision
|-- factory.py              # Factories debat et vision
|-- hybrid_router.py        # Routage local/powerful/oumi
|-- litserve_client.py      # Client HTTP vers LitServe
|-- litserve_wrapper.py     # Serveur LitServe autour d'OllamaAdapter
|-- llm_batcher.py          # Batching LLM et embeddings
|-- multi_provider.py       # Providers Ollama/OpenAI/Anthropic + failover
|-- ollama_client.py        # Client Ollama direct
`-- vision_analyzer.py      # Services d'analyse d'images
```

## Configuration

| Variable | Description | Defaut |
|----------|-------------|--------|
| `OLLAMA_BASE_URL` | URL du serveur Ollama pour les clients directs et le routeur | `http://localhost:11434` |
| `OLLAMA_MODEL_NAME` | Modele Ollama par defaut expose par `src/core/config.py` | `qwen2.5:7b` |
| `OLLAMA_EMBEDDING_MODEL` | Modele d'embedding expose par `src/core/config.py` | `nomic-embed-text` |
| `OLLAMA_TIMEOUT` | Timeout des requetes Ollama | `300` dans `src/core/config.py`, `120` dans `docs/configuration.md` |
| `OLLAMA_MODEL_POWERFUL` | Modele puissant utilise par `HybridLLMRouter` si aucun argument explicite n'est fourni | meme valeur que le modele local |
| `OPENAI_API_KEY` | Active le provider OpenAI dans `create_default_multi_provider()` | non defini |
| `ANTHROPIC_API_KEY` | Active le provider Anthropic dans `create_default_multi_provider()` | non defini |
| `VECTORDB__USE_LITSERVE` | Active LitServe pour le service d'embeddings configure dans `src/infrastructure/config/settings.py` | `false` |
| `VECTORDB__LITSERVE_URL` | URL du serveur LitServe pour les embeddings | `http://localhost:8001` |

Les README mentionnent aussi Groq/OpenRouter comme options cloud produit. Dans
ce module precis, le failover implemente est Ollama -> OpenAI-compatible ->
Anthropic ; une integration Groq/OpenRouter native devra etre ajoutee separement
si l'on veut l'exposer ici.

## Points d'integration

- `src/infrastructure/agents/tajine/tajine_agent.py` lazy-load
  `HybridLLMRouter` et `OllamaClient` pour le raisonnement ;
- `src/infrastructure/agents/tajine/planning.py` utilise `OllamaClient` pour la
  decomposition de taches ;
- `src/application/services/agent_orchestrator.py` garde un client Ollama pour
  les fonctionnalites agentiques ;
- `src/application/services/embedding_service.py` peut creer un `LitServeClient`
  pour accelerer les embeddings ;
- `src/infrastructure/dashboard/api.py` et les outils MCP appellent les
  factories de debat ;
- `tests/unit/infrastructure/llm/` et `tests/infrastructure/llm/` couvrent les
  providers, le routeur, l'auto-detection Ollama, la vision et les factories.

## Etat actuel

- `OllamaClient`, `HybridLLMRouter`, `MultiProviderLLM`,
  `AdaptiveLLMProvider` et `VisionAnalyzer` disposent de tests unitaires.
- Le routage local/powerful repose sur des heuristiques simples et ne mesure pas
  encore le cout reel, la latence historique ou la qualite des sorties.
- `OumiClient` est un stub avec fallback optionnel vers Ollama.
- Deux piles Ollama coexistent : `src/infrastructure/llm/ollama_client.py` pour
  les agents et `src/infrastructure/ml/ollama/` pour l'adapter ML. LitServe
  depend de l'adapter ML.
- Le failover cloud de `MultiProviderLLM` supporte OpenAI et Anthropic, mais pas
  encore les variables `GROQ_API_KEY` et `OPENROUTER_API_KEY` annoncees dans les
  README.
- Le client LitServe ne supporte pas le streaming.

## Limitations connues

- Les modeles par defaut varient selon les fichiers (`qwen2.5:7b`,
  `qwen3.5:27b`, `qwen3-coder:30b`) ; il faut verifier le chemin d'appel avant
  de changer une valeur globale.
- Les erreurs de generation peuvent declencher un fallback, mais pas tous les
  appels disposent d'un provider secondaire configure.
- Les clients HTTP doivent etre fermes via `close()` dans les usages long-lived
  pour eviter de conserver des connexions ouvertes.
- Les prompts vision supposent que le modele configure accepte le champ
  `images` d'Ollama.
