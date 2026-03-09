"""LLM Summarizer with fallback chain: Ollama → Groq → OpenRouter.

Inspired by World Monitor's LLM fallback pattern.
Each provider has its own circuit breaker for automatic failover.

Chain:
    1. Ollama (qwen3.5:27b, local, free, 30s timeout)
    2. Groq (llama-3.3-70b-versatile, fast cloud, free tier)
    3. OpenRouter (meta-llama/llama-3.3-70b, paid fallback)
"""

import os
import time

import httpx
from loguru import logger

from src.infrastructure.datasources.circuit_breaker import (
    BreakerConfig,
    CircuitBreaker,
)

# System prompt for summarization + sentiment
SUMMARIZE_SYSTEM = (
    "Tu es un analyste économique français. "
    "Résume l'article suivant en 2-3 phrases concises en français. "
    "Concentre-toi sur les faits clés, les acteurs mentionnés et l'impact territorial. "
    "Ne commence pas par 'Cet article' ou 'L'article'. Va droit au but."
)

SENTIMENT_SYSTEM = (
    "Tu es un analyste de sentiment spécialisé en actualité économique française. "
    "Analyse le titre et le contenu suivant. Réponds UNIQUEMENT par un seul mot parmi: "
    "positif, negatif, neutre. Rien d'autre."
)


class LLMSummarizer:
    """Article summarizer with provider fallback chain.

    Uses circuit breakers per provider to avoid hammering a dead service.
    Falls through: Ollama → Groq → OpenRouter.
    """

    def __init__(
        self,
        ollama_url: str | None = None,
        ollama_model: str = "qwen3:8b",
        groq_api_key: str | None = None,
        groq_model: str = "llama-3.3-70b-versatile",
        openrouter_api_key: str | None = None,
        openrouter_model: str = "meta-llama/llama-3.3-70b-instruct",
    ):
        self._ollama_url = ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._ollama_model = ollama_model
        self._groq_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self._groq_model = groq_model
        self._openrouter_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self._openrouter_model = openrouter_model

        self._client = httpx.AsyncClient(timeout=120)

        # Circuit breakers per provider
        self._breakers = {
            "ollama": CircuitBreaker(
                BreakerConfig(
                    name="llm_ollama",
                    max_failures=3,
                    cooldown_seconds=60,
                    timeout_seconds=90,
                )
            ),
            "groq": CircuitBreaker(
                BreakerConfig(
                    name="llm_groq",
                    max_failures=3,
                    cooldown_seconds=300,
                    timeout_seconds=15,
                )
            ),
            "openrouter": CircuitBreaker(
                BreakerConfig(
                    name="llm_openrouter",
                    max_failures=3,
                    cooldown_seconds=300,
                    timeout_seconds=20,
                )
            ),
        }

        # Stats
        self._calls = {"ollama": 0, "groq": 0, "openrouter": 0, "failed": 0}

    async def summarize(self, title: str, text: str, max_length: int = 200) -> dict:
        """Summarize an article using the fallback chain.

        Args:
            title: Article title
            text: Article text/summary from RSS
            max_length: Max summary length hint

        Returns:
            dict with keys: summary, provider, latency_ms, error (if all failed)
        """
        prompt = f"Titre: {title}\n\nContenu: {text[:2000]}"

        # Try each provider in order (manual breaker management for async calls)
        for provider_name, call_fn in [
            ("ollama", self._call_ollama),
            ("groq", self._call_groq),
            ("openrouter", self._call_openrouter),
        ]:
            breaker = self._breakers[provider_name]
            if not breaker.is_available:
                continue

            start = time.time()
            try:
                import asyncio

                result = await asyncio.wait_for(
                    call_fn(prompt),
                    timeout=breaker.config.timeout_seconds,
                )
                if result:
                    breaker._record_success(result)
                    latency = (time.time() - start) * 1000
                    self._calls[provider_name] += 1
                    return {
                        "summary": result.strip()[: max_length * 3],
                        "provider": provider_name,
                        "latency_ms": round(latency, 1),
                    }
            except Exception as e:
                breaker._record_failure(str(e))
                logger.warning(f"[summarizer] {provider_name} failed: {e}")

        self._calls["failed"] += 1
        return {"summary": None, "provider": None, "error": "All providers failed"}

    async def analyze_sentiment(self, title: str, text: str) -> str:
        """Analyze sentiment of an article. Returns: positif, negatif, neutre."""
        prompt = f"Titre: {title}\n\nContenu: {text[:500]}"

        for provider_name, call_fn in [
            ("ollama", self._call_ollama_sentiment),
            ("groq", self._call_groq),
            ("openrouter", self._call_openrouter),
        ]:
            breaker = self._breakers[provider_name]
            if not breaker.is_available:
                continue
            try:
                import asyncio

                result = await asyncio.wait_for(
                    call_fn(prompt)
                    if provider_name != "ollama"
                    else self._call_ollama_sentiment(prompt),
                    timeout=15,
                )
                if result:
                    word = result.strip().lower().split()[0].rstrip(".,;:")
                    if word in ("positif", "negatif", "neutre", "positive", "negative", "neutral"):
                        return {
                            "positive": "positif",
                            "negative": "negatif",
                            "neutral": "neutre",
                        }.get(word, word)
            except Exception:
                pass

        return "neutre"

    async def _call_ollama_sentiment(self, prompt: str) -> str | None:
        """Quick Ollama call for sentiment (low num_predict)."""
        response = await self._client.post(
            f"{self._ollama_url}/api/generate",
            json={
                "model": self._ollama_model,
                "prompt": prompt,
                "system": SENTIMENT_SYSTEM,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.1, "num_predict": 5, "num_ctx": 2048},
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    async def summarize_with_sentiment(self, title: str, text: str) -> dict:
        """Summarize + analyze sentiment in one call."""
        import asyncio

        summary_task = asyncio.create_task(self.summarize(title, text))
        sentiment_task = asyncio.create_task(self.analyze_sentiment(title, text))

        summary_result = await summary_task
        sentiment = await sentiment_task
        summary_result["sentiment"] = sentiment
        return summary_result

    async def summarize_batch(self, articles: list[dict], max_concurrent: int = 5) -> list[dict]:
        """Summarize multiple articles concurrently.

        Args:
            articles: List of dicts with 'title' and 'summary'/'text' keys
            max_concurrent: Max concurrent summarizations

        Returns:
            List of dicts with 'url', 'summary', 'provider'
        """
        import asyncio

        sem = asyncio.Semaphore(max_concurrent)
        results = []

        async def _summarize_one(article: dict) -> dict:
            async with sem:
                text = article.get("summary") or article.get("text") or article.get("title", "")
                result = await self.summarize(article.get("title", ""), text)
                result["url"] = article.get("url", "")
                return result

        tasks = [_summarize_one(a) for a in articles if a.get("title")]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [r if isinstance(r, dict) else {"error": str(r)} for r in results]

    async def _call_ollama(self, prompt: str) -> str | None:
        """Call Ollama /api/generate."""
        response = await self._client.post(
            f"{self._ollama_url}/api/generate",
            json={
                "model": self._ollama_model,
                "prompt": prompt,
                "system": SUMMARIZE_SYSTEM,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 256,
                    "num_ctx": 4096,
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        text = response.json().get("response", "")
        return text if text.strip() else None

    async def _call_groq(self, prompt: str) -> str | None:
        """Call Groq via OpenAI-compatible API."""
        if not self._groq_key:
            return None

        response = await self._client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._groq_key}"},
            json={
                "model": self._groq_model,
                "messages": [
                    {"role": "system", "content": SUMMARIZE_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 256,
            },
            timeout=15,
        )
        response.raise_for_status()
        choices = response.json().get("choices", [])
        if choices:
            return choices[0]["message"]["content"]
        return None

    async def _call_openrouter(self, prompt: str) -> str | None:
        """Call OpenRouter via OpenAI-compatible API."""
        if not self._openrouter_key:
            return None

        response = await self._client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._openrouter_key}",
                "HTTP-Referer": "https://tawiza.fr",
                "X-Title": "Tawiza-V2",
            },
            json={
                "model": self._openrouter_model,
                "messages": [
                    {"role": "system", "content": SUMMARIZE_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 256,
            },
            timeout=20,
        )
        response.raise_for_status()
        choices = response.json().get("choices", [])
        if choices:
            return choices[0]["message"]["content"]
        return None

    def stats(self) -> dict:
        """Get summarizer statistics."""
        breaker_stats = {
            name: {
                "state": b.state.value,
                "failures": b._failure_count,
                "cooldown_remaining": round(b.cooldown_remaining, 0),
            }
            for name, b in self._breakers.items()
        }
        return {
            "calls": self._calls.copy(),
            "total": sum(self._calls.values()),
            "breakers": breaker_stats,
            "providers_available": {
                "ollama": True,
                "groq": bool(self._groq_key),
                "openrouter": bool(self._openrouter_key),
            },
        }

    async def close(self):
        await self._client.aclose()


# Global singleton
_summarizer: LLMSummarizer | None = None


def get_summarizer() -> LLMSummarizer:
    global _summarizer
    if _summarizer is None:
        _summarizer = LLMSummarizer()
    return _summarizer
