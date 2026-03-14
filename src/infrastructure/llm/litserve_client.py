"""
LitServe Client Adapter

Provides a drop-in replacement for OllamaAdapter that connects to LitServe.
Automatically gets benefits of batching and caching.
"""

from typing import Any

import httpx
from loguru import logger


class LitServeClient:
    """
    Client for LitServe-wrapped Ollama server.

    Drop-in replacement for OllamaAdapter that communicates with LitServe.
    Provides same interface but with batching and caching benefits.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        timeout: float = 120.0,
        pool_connections: int = 10,
        pool_maxsize: int = 20,
    ):
        """
        Initialize LitServe client.

        Args:
            base_url: LitServe server URL
            timeout: Request timeout in seconds
            pool_connections: Connection pool size
            pool_maxsize: Maximum pool size
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Create HTTP client with connection pooling
        limits = httpx.Limits(
            max_connections=pool_maxsize, max_keepalive_connections=pool_connections
        )
        self.client = httpx.AsyncClient(timeout=timeout, limits=limits, http2=True)

        logger.info(
            f"LitServe client initialized: {self.base_url} "
            f"(pool: {pool_connections}/{pool_maxsize})"
        )

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """
        Generate completion.

        Compatible with OllamaAdapter.generate().

        Args:
            model: Model name
            prompt: Input prompt
            system: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            stream: Whether to stream (not supported in LitServe)

        Returns:
            dict: Response with 'response' field
        """
        if stream:
            logger.warning("Streaming not supported via LitServe, using non-streaming")

        payload = {
            "type": "completion",
            "model": model,
            "prompt": prompt,
            "system": system,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = await self.client.post(f"{self.base_url}/predict", json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("type") == "error":
                raise RuntimeError(result.get("error", "Unknown error"))

            return result

        except httpx.HTTPError as e:
            logger.error(f"LitServe request failed: {e}")
            raise

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        stream: bool = False,
    ) -> dict[str, Any]:
        """
        Chat completion.

        Compatible with OllamaAdapter.chat().

        Args:
            model: Model name
            messages: Chat messages
            temperature: Sampling temperature
            stream: Whether to stream (not supported)

        Returns:
            dict: Response with 'message' field
        """
        if stream:
            logger.warning("Streaming not supported via LitServe, using non-streaming")

        payload = {"type": "chat", "model": model, "messages": messages, "temperature": temperature}

        try:
            response = await self.client.post(f"{self.base_url}/predict", json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("type") == "error":
                raise RuntimeError(result.get("error", "Unknown error"))

            return result

        except httpx.HTTPError as e:
            logger.error(f"LitServe chat request failed: {e}")
            raise

    async def get_embedding(self, model: str, text: str) -> list[float]:
        """
        Get embedding vector.

        Compatible with OllamaAdapter.get_embedding().

        Args:
            model: Model name (e.g., nomic-embed-text)
            text: Input text

        Returns:
            list: Embedding vector
        """
        payload = {"type": "embedding", "model": model, "text": text}

        try:
            response = await self.client.post(f"{self.base_url}/predict", json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("type") == "error":
                raise RuntimeError(result.get("error", "Unknown error"))

            return result.get("embedding", [])

        except httpx.HTTPError as e:
            logger.error(f"LitServe embedding request failed: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check if LitServe server is healthy.

        Returns:
            bool: True if healthy
        """
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"LitServe health check failed: {e}")
            return False

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("LitServe client closed")

    def get_stats(self) -> dict[str, Any]:
        """
        Get client statistics.

        Returns:
            dict: Basic stats (placeholder)
        """
        return {"base_url": self.base_url, "timeout": self.timeout}
