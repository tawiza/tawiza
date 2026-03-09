"""Completion provider registry and main entry point."""


from src.cli.v3.completion.base import CompletionProvider, CompletionResult
from src.cli.v3.completion.providers.contextual import HistoryProvider
from src.cli.v3.completion.providers.dynamic import DynamicAgentProvider, DynamicModelProvider
from src.cli.v3.completion.providers.static import StaticProvider

# Registry of completion providers by category
_providers: dict[str, list[CompletionProvider]] = {}


def register_completer(category: str, provider: CompletionProvider) -> None:
    """Register a completion provider for a category.

    Args:
        category: Category name (e.g., "models", "agents")
        provider: CompletionProvider instance
    """
    if category not in _providers:
        _providers[category] = []
    _providers[category].append(provider)
    # Sort by priority (highest first)
    _providers[category].sort(key=lambda p: -p.priority)


def get_completer(category: str) -> CompletionProvider | None:
    """Get the highest priority completer for a category.

    Args:
        category: Category name

    Returns:
        CompletionProvider or None
    """
    providers = _providers.get(category, [])
    return providers[0] if providers else None


def complete(
    category: str,
    incomplete: str = "",
    context: dict | None = None,
    max_results: int = 10,
) -> list[CompletionResult]:
    """Get completions for a category.

    Combines results from all registered providers, sorted by relevance.

    Args:
        category: Category name
        incomplete: Partial input to complete
        context: Optional context dict
        max_results: Maximum results to return

    Returns:
        List of CompletionResult sorted by score
    """
    providers = _providers.get(category, [])
    all_results: list[CompletionResult] = []

    for provider in providers:
        try:
            results = provider.get_completions(incomplete, context)
            all_results.extend(results)
        except Exception:
            continue

    # Sort by score (descending) then value (ascending)
    all_results.sort(key=lambda r: (-r.score, r.value))

    # Deduplicate by value
    seen = set()
    unique = []
    for r in all_results:
        if r.value not in seen:
            seen.add(r.value)
            unique.append(r)

    return unique[:max_results]


def create_typer_completer(category: str):
    """Create a Typer-compatible completer function.

    Args:
        category: Category name

    Returns:
        Function suitable for typer autocompletion parameter
    """

    def completer(incomplete: str) -> list[str]:
        results = complete(category, incomplete)
        return [r.value for r in results]

    return completer


# Register default providers
def _init_default_providers():
    """Initialize default completion providers."""
    # Static providers
    for cat in ["agents", "output_formats", "depth_levels", "log_levels", "services"]:
        register_completer(cat, StaticProvider(cat))

    # Dynamic providers
    register_completer("models", DynamicModelProvider())
    register_completer("agents", DynamicAgentProvider())

    # Contextual providers (lower priority)
    history = HistoryProvider()
    for cat in ["agents", "models"]:
        register_completer(cat, history)


# Initialize on import
_init_default_providers()
