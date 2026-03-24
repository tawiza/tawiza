"""Embeddings service using Ollama."""

from dataclasses import dataclass

import httpx
from loguru import logger


@dataclass
class EmbeddingsConfig:
    """Embeddings configuration."""

    ollama_url: str = "http://localhost:11434"
    model: str = "nomic-embed-text"


class EmbeddingsService:
    """Generate embeddings using Ollama."""

    def __init__(self, config: EmbeddingsConfig | None = None) -> None:
        self.config = config or EmbeddingsConfig()
        logger.info(f"Embeddings service initialized with model: {self.config.model}")

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for single text."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.config.ollama_url}/api/embed",
                json={"model": self.config.model, "input": text},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            embs = data.get("embeddings", [[]])
            return embs[0] if embs else []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        for text in texts:
            embedding = await self.embed(text)
            embeddings.append(embedding)
        return embeddings
