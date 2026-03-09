"""Dynamic completion providers that query live system state."""


from src.cli.v3.completion.base import CompletionProvider, CompletionResult
from src.cli.v3.completion.cache import CompletionCache

# Shared cache instance
_cache = CompletionCache()


class DynamicModelProvider(CompletionProvider):
    """Provides completions for Ollama models."""

    @property
    def name(self) -> str:
        return "dynamic:models"

    @property
    def priority(self) -> int:
        return 80

    def get_completions(self, incomplete: str, context: dict | None = None) -> list[CompletionResult]:
        """Get model completions from Ollama API."""
        # Check cache first
        cached = _cache.get("models")
        if cached is not None:
            return self._filter_results(cached, incomplete)

        # Fetch from Ollama
        models = self._fetch_models()
        _cache.set("models", models, ttl=60)

        return self._filter_results(models, incomplete)

    def _fetch_models(self) -> list[CompletionResult]:
        """Fetch available models from Ollama."""
        try:
            import httpx

            response = httpx.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])

                return [
                    CompletionResult(
                        value=m.get("name", "unknown"),
                        description=f"{m.get('size', 0) / 1e9:.1f}GB" if m.get("size") else None,
                        source="dynamic",
                    )
                    for m in models
                ]
        except Exception:
            pass

        # Fallback to common models
        return [
            CompletionResult(value="qwen3.5:27b", description="Default model", source="fallback"),
            CompletionResult(value="llama3:8b", description="Meta Llama 3", source="fallback"),
            CompletionResult(value="codellama:13b", description="Code specialized", source="fallback"),
            CompletionResult(value="mixtral:8x7b", description="Mixture of experts", source="fallback"),
        ]

    def _filter_results(self, results: list[CompletionResult], incomplete: str) -> list[CompletionResult]:
        """Filter results by incomplete string."""
        if not incomplete:
            return results

        filtered = []
        for r in results:
            if incomplete.lower() in r.value.lower():
                # Boost prefix matches
                if r.value.lower().startswith(incomplete.lower()):
                    r.score = 2.0
                filtered.append(r)

        return sorted(filtered, key=lambda x: (-x.score, x.value))

    def supports_caching(self) -> bool:
        return True

    def cache_ttl(self) -> int:
        return 60


class DynamicAgentProvider(CompletionProvider):
    """Provides completions for running/available agents."""

    @property
    def name(self) -> str:
        return "dynamic:agents"

    @property
    def priority(self) -> int:
        return 70

    def get_completions(self, incomplete: str, context: dict | None = None) -> list[CompletionResult]:
        """Get agent completions including running tasks."""
        import json
        from pathlib import Path

        results = []

        # Get running tasks
        tasks_file = Path.home() / ".tawiza" / "agent_tasks.json"
        if tasks_file.exists():
            try:
                tasks = json.loads(tasks_file.read_text())
                active = [
                    (tid, t) for tid, t in tasks.items()
                    if t.get("status") in ("running", "pending")
                ]

                for tid, task in active:
                    if incomplete.lower() in tid.lower():
                        results.append(CompletionResult(
                            value=tid[:8],
                            description=f"{task.get('agent', 'unknown')} - {task.get('status')}",
                            source="dynamic",
                        ))
            except Exception:
                pass

        return results

    def supports_caching(self) -> bool:
        return True

    def cache_ttl(self) -> int:
        return 5  # Tasks change frequently


class DynamicServiceProvider(CompletionProvider):
    """Provides completions for services based on their status."""

    @property
    def name(self) -> str:
        return "dynamic:services"

    @property
    def priority(self) -> int:
        return 75

    def get_completions(self, incomplete: str, context: dict | None = None) -> list[CompletionResult]:
        """Get service completions with current status."""
        services = {
            "ollama": "http://localhost:11434/api/tags",
            "label-studio": "http://localhost:8082/api/health",
            "llama-factory": "http://localhost:7860/",
            "api": "http://localhost:8002/health",
        }

        results = []
        for name, url in services.items():
            if incomplete.lower() in name.lower():
                status = self._check_status(url)
                results.append(CompletionResult(
                    value=name,
                    description=f"[{status}]",
                    score=2.0 if status == "OK" else 1.0,
                    source="dynamic",
                ))

        return sorted(results, key=lambda x: (-x.score, x.value))

    def _check_status(self, url: str) -> str:
        """Quick status check."""
        try:
            import httpx
            response = httpx.get(url, timeout=2)
            return "OK" if response.status_code < 400 else "ERROR"
        except Exception:
            return "DOWN"


def create_model_completer():
    """Create a Typer-compatible model completer."""
    provider = DynamicModelProvider()

    def completer(incomplete: str) -> list[str]:
        results = provider.get_completions(incomplete)
        return [r.value for r in results]

    return completer


model_completer = create_model_completer()
