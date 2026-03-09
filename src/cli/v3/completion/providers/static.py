"""Static completion providers for known values."""


from src.cli.v3.completion.base import CompletionProvider, CompletionResult

# Static values that don't change
STATIC_COMPLETIONS = {
    "agents": [
        ("manus", "Reasoning agent with think-execute loop"),
        ("s3", "Hybrid browser + desktop automation"),
        ("analyst", "Data analysis and insights"),
        ("coder", "Code generation and review"),
        ("browser", "Web automation and scraping"),
        ("ml", "Machine learning tasks"),
        ("research", "Deep research with multi-source"),
        ("crawler", "Web crawling and extraction"),
    ],
    "output_formats": [
        ("json", "Machine-readable JSON"),
        ("table", "Human-readable table"),
        ("csv", "Comma-separated values"),
        ("md", "Markdown format"),
    ],
    "depth_levels": [
        ("quick", "Fast search, basic report (~10s)"),
        ("standard", "Map + CSV export (~30s)"),
        ("full", "Web enrichment + Graph (~2-5min)"),
    ],
    "log_levels": [
        ("debug", "Show all messages"),
        ("info", "Normal operation"),
        ("warning", "Only warnings and errors"),
        ("error", "Only errors"),
    ],
    "services": [
        ("ollama", "Local LLM inference"),
        ("label-studio", "Data annotation"),
        ("llama-factory", "Model fine-tuning"),
        ("api", "Tawiza API server"),
        ("vm-sandbox", "Isolated execution"),
    ],
}


class StaticProvider(CompletionProvider):
    """Provides completions from static lists."""

    def __init__(self, category: str):
        """Initialize with category name.

        Args:
            category: Key in STATIC_COMPLETIONS
        """
        self._category = category

    @property
    def name(self) -> str:
        return f"static:{self._category}"

    @property
    def priority(self) -> int:
        return 100  # High priority

    def get_completions(self, incomplete: str, context: dict | None = None) -> list[CompletionResult]:
        """Get static completions matching the incomplete string."""
        items = STATIC_COMPLETIONS.get(self._category, [])
        results = []

        for item in items:
            if isinstance(item, tuple):
                value, description = item
            else:
                value, description = item, None

            if incomplete.lower() in value.lower():
                # Score based on match position (prefix match = higher)
                score = 2.0 if value.lower().startswith(incomplete.lower()) else 1.0

                results.append(CompletionResult(
                    value=value,
                    description=description,
                    score=score,
                    source="static",
                ))

        return sorted(results, key=lambda x: (-x.score, x.value))

    def supports_caching(self) -> bool:
        return True

    def cache_ttl(self) -> int:
        return 3600  # Static values don't change


def create_static_completer(category: str):
    """Create a Typer-compatible completer function.

    Args:
        category: Key in STATIC_COMPLETIONS

    Returns:
        Function suitable for typer autocompletion parameter
    """
    provider = StaticProvider(category)

    def completer(incomplete: str) -> list[str]:
        results = provider.get_completions(incomplete)
        return [r.value for r in results]

    return completer


# Pre-built completers for common use
agent_completer = create_static_completer("agents")
format_completer = create_static_completer("output_formats")
depth_completer = create_static_completer("depth_levels")
service_completer = create_static_completer("services")
