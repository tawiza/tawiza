"""
LLM Call Batcher - Batch multiple LLM requests for efficiency.

Provides request batching and deduplication for LLM calls:
- Automatic request batching within time windows
- Deduplication of identical requests
- Concurrent batch processing
- Cache integration

Benefits:
- Reduced API calls (combine similar requests)
- Lower latency (parallel processing)
- Cost savings (fewer tokens, less overhead)

Usage:
    batcher = LLMBatcher(ollama_client)

    # Queue requests
    future1 = await batcher.queue(prompt1, model)
    future2 = await batcher.queue(prompt2, model)

    # Wait for results
    result1 = await future1
    result2 = await future2
"""

import asyncio
import contextlib
import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")


@dataclass
class BatchRequest:
    """Single request in a batch."""

    prompt: str
    model: str
    system: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)
    future: asyncio.Future = field(default_factory=lambda: asyncio.get_event_loop().create_future())
    queued_at: float = field(default_factory=time.time)

    @property
    def key(self) -> str:
        """Generate deduplication key."""
        key_data = {
            "prompt": self.prompt,
            "model": self.model,
            "system": self.system,
            "temperature": round(self.temperature, 2),
            "max_tokens": self.max_tokens,
        }
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_json.encode()).hexdigest()[:16]


class LLMBatcher:
    """
    Batches multiple LLM requests for efficient processing.

    Features:
    - Time-windowed batching (collect requests, process together)
    - Request deduplication (same prompt = same result)
    - Model-specific batching (separate batches per model)
    - Concurrent processing with limits
    - Integration with caching

    Usage:
        batcher = LLMBatcher(
            generate_func=ollama.generate,
            batch_window_ms=100,
            max_batch_size=10,
        )

        async with batcher:
            # Queue multiple requests
            results = await asyncio.gather(
                batcher.queue("What is Python?", "qwen3.5:27b"),
                batcher.queue("What is Rust?", "qwen3.5:27b"),
                batcher.queue("What is Go?", "qwen3.5:27b"),
            )
    """

    def __init__(
        self,
        generate_func: Callable[..., Awaitable[str]],
        batch_window_ms: int = 100,
        max_batch_size: int = 10,
        max_concurrent_batches: int = 5,
        deduplication: bool = True,
        cache_func: Callable[[str, str], Awaitable[str | None]] | None = None,
    ):
        """
        Initialize LLM batcher.

        Args:
            generate_func: Async function to call LLM (prompt, model, **kwargs) -> response
            batch_window_ms: Time window to collect requests before processing
            max_batch_size: Maximum requests per batch
            max_concurrent_batches: Maximum concurrent batch processing
            deduplication: Deduplicate identical requests
            cache_func: Optional cache lookup function (prompt, model) -> cached_result
        """
        self._generate_func = generate_func
        self._batch_window_ms = batch_window_ms
        self._max_batch_size = max_batch_size
        self._max_concurrent = max_concurrent_batches
        self._deduplication = deduplication
        self._cache_func = cache_func

        # Request queues per model
        self._queues: dict[str, list[BatchRequest]] = defaultdict(list)
        self._queue_lock = asyncio.Lock()

        # Deduplication tracking
        self._pending_requests: dict[str, BatchRequest] = {}

        # Processing semaphore
        self._semaphore = asyncio.Semaphore(max_concurrent_batches)

        # Background processor task
        self._processor_task: asyncio.Task | None = None
        self._running = False

        # Statistics
        self._stats = {
            "requests_queued": 0,
            "requests_processed": 0,
            "batches_processed": 0,
            "deduplicated": 0,
            "cache_hits": 0,
            "total_latency_ms": 0.0,
            "avg_batch_size": 0.0,
        }

        logger.info(
            f"LLMBatcher initialized: window={batch_window_ms}ms, "
            f"max_batch={max_batch_size}, concurrent={max_concurrent_batches}"
        )

    async def start(self) -> None:
        """Start the background batch processor."""
        if not self._running:
            self._running = True
            self._processor_task = asyncio.create_task(self._process_loop())
            logger.info("LLMBatcher processor started")

    async def stop(self) -> None:
        """Stop the batch processor."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._processor_task
            self._processor_task = None
        logger.info("LLMBatcher processor stopped")

    async def queue(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **extra_params,
    ) -> str:
        """
        Queue a request for batched processing.

        Args:
            prompt: User prompt
            model: Model name
            system: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **extra_params: Additional parameters

        Returns:
            Generated response (awaitable)
        """
        self._stats["requests_queued"] += 1

        # Check cache first
        if self._cache_func:
            cached = await self._cache_func(prompt, model)
            if cached:
                self._stats["cache_hits"] += 1
                return cached

        # Create request
        request = BatchRequest(
            prompt=prompt,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_params=extra_params,
        )

        # Check for deduplication
        if self._deduplication:
            async with self._queue_lock:
                if request.key in self._pending_requests:
                    existing = self._pending_requests[request.key]
                    self._stats["deduplicated"] += 1
                    logger.debug(f"Deduplicated request: {request.key}")
                    return await existing.future

                self._pending_requests[request.key] = request

        # Add to queue
        async with self._queue_lock:
            self._queues[model].append(request)

        # Return future to wait for result
        return await request.future

    async def _process_loop(self) -> None:
        """Background loop to process batches."""
        while self._running:
            try:
                await asyncio.sleep(self._batch_window_ms / 1000)
                await self._process_batches()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch processor error: {e}")

    async def _process_batches(self) -> None:
        """Process all pending batches."""
        async with self._queue_lock:
            models_to_process = list(self._queues.keys())

        tasks = []
        for model in models_to_process:
            async with self._queue_lock:
                if model not in self._queues or not self._queues[model]:
                    continue

                # Take up to max_batch_size requests
                batch = self._queues[model][: self._max_batch_size]
                self._queues[model] = self._queues[model][self._max_batch_size :]

            if batch:
                tasks.append(self._process_batch(model, batch))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_batch(
        self,
        model: str,
        batch: list[BatchRequest],
    ) -> None:
        """
        Process a single batch of requests.

        Args:
            model: Model name
            batch: List of requests to process
        """
        async with self._semaphore:
            self._stats["batches_processed"] += 1
            batch_start = time.time()

            logger.debug(f"Processing batch: model={model}, size={len(batch)}")

            # Process requests concurrently within the batch
            tasks = [self._process_single(request) for request in batch]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Set results on futures
            for request, result in zip(batch, results, strict=False):
                if isinstance(result, Exception):
                    request.future.set_exception(result)
                else:
                    request.future.set_result(result)

                # Clean up deduplication tracking
                if self._deduplication and request.key in self._pending_requests:
                    del self._pending_requests[request.key]

            batch_latency = (time.time() - batch_start) * 1000
            self._stats["total_latency_ms"] += batch_latency
            self._stats["requests_processed"] += len(batch)

            # Update average batch size
            total_batches = self._stats["batches_processed"]
            total_requests = self._stats["requests_processed"]
            self._stats["avg_batch_size"] = total_requests / total_batches

            logger.debug(f"Batch completed: {len(batch)} requests in {batch_latency:.0f}ms")

    async def _process_single(self, request: BatchRequest) -> str:
        """Process a single request."""
        try:
            return await self._generate_func(
                prompt=request.prompt,
                model=request.model,
                system=request.system,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                **request.extra_params,
            )
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    def flush(self) -> None:
        """Force processing of all pending requests."""
        asyncio.create_task(self._process_batches())

    def get_stats(self) -> dict[str, Any]:
        """Get batcher statistics."""
        pending = sum(len(q) for q in self._queues.values())
        avg_latency = (
            self._stats["total_latency_ms"] / self._stats["batches_processed"]
            if self._stats["batches_processed"] > 0
            else 0.0
        )

        return {
            **self._stats,
            "pending_requests": pending,
            "avg_batch_latency_ms": round(avg_latency, 2),
            "deduplication_rate": (
                f"{self._stats['deduplicated'] / self._stats['requests_queued'] * 100:.1f}%"
                if self._stats["requests_queued"] > 0
                else "0.0%"
            ),
        }

    def get_queue_status(self) -> dict[str, int]:
        """Get current queue sizes per model."""
        return {model: len(queue) for model, queue in self._queues.items()}

    async def __aenter__(self) -> "LLMBatcher":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        # Flush remaining requests
        await self._process_batches()
        await self.stop()


class EmbeddingBatcher:
    """
    Specialized batcher for embedding requests.

    Embedding requests are particularly suitable for batching as they're:
    - Typically short, fixed-size inputs
    - Deterministic (same input = same output)
    - Often requested in bulk

    Usage:
        batcher = EmbeddingBatcher(embedding_func, batch_size=32)

        async with batcher:
            embeddings = await asyncio.gather(
                batcher.embed("text 1"),
                batcher.embed("text 2"),
                batcher.embed("text 3"),
            )
    """

    def __init__(
        self,
        embed_func: Callable[[str], Awaitable[list[float]]],
        batch_embed_func: Callable[[list[str]], Awaitable[list[list[float]]]] | None = None,
        batch_size: int = 32,
        batch_window_ms: int = 50,
    ):
        """
        Initialize embedding batcher.

        Args:
            embed_func: Function to embed single text
            batch_embed_func: Optional function to embed batch (more efficient)
            batch_size: Maximum batch size
            batch_window_ms: Time window for batching
        """
        self._embed_func = embed_func
        self._batch_embed_func = batch_embed_func
        self._batch_size = batch_size
        self._batch_window_ms = batch_window_ms

        self._queue: list[tuple[str, asyncio.Future]] = []
        self._lock = asyncio.Lock()
        self._processor_task: asyncio.Task | None = None
        self._running = False

        # Cache for embeddings
        self._cache: dict[str, list[float]] = {}

        logger.info(f"EmbeddingBatcher initialized: batch_size={batch_size}")

    async def start(self) -> None:
        """Start the batch processor."""
        if not self._running:
            self._running = True
            self._processor_task = asyncio.create_task(self._process_loop())

    async def stop(self) -> None:
        """Stop the batch processor."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._processor_task

    async def embed(self, text: str) -> list[float]:
        """
        Get embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Check cache
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        if text_hash in self._cache:
            return self._cache[text_hash]

        # Create future and queue
        future = asyncio.get_event_loop().create_future()

        async with self._lock:
            self._queue.append((text, future))

        result = await future

        # Cache result
        self._cache[text_hash] = result

        return result

    async def _process_loop(self) -> None:
        """Background processing loop."""
        while self._running:
            await asyncio.sleep(self._batch_window_ms / 1000)
            await self._process_batch()

    async def _process_batch(self) -> None:
        """Process current batch."""
        async with self._lock:
            if not self._queue:
                return

            batch = self._queue[: self._batch_size]
            self._queue = self._queue[self._batch_size :]

        texts = [text for text, _ in batch]
        futures = [future for _, future in batch]

        try:
            if self._batch_embed_func and len(texts) > 1:
                # Use batch function if available
                embeddings = await self._batch_embed_func(texts)
            else:
                # Fall back to individual calls
                embeddings = await asyncio.gather(*[self._embed_func(text) for text in texts])

            for future, embedding in zip(futures, embeddings, strict=False):
                future.set_result(embedding)

        except Exception as e:
            for future in futures:
                if not future.done():
                    future.set_exception(e)

    async def __aenter__(self) -> "EmbeddingBatcher":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._process_batch()
        await self.stop()
