"""Ollama LLM client with GPU ROCm support for browser automation."""

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
from loguru import logger


class OllamaClient:
    """
    Ollama LLM client optimized for browser automation tasks.

    Supports:
    - GPU ROCm acceleration
    - Vision models (llava) for screenshot analysis
    - Streaming responses for live interaction
    - Code generation for web interactions
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        vision_model: str = "qwen2.5:7b",  # Use same model if no vision model available
        timeout: int = 300,  # 5 minutes for large model inference
    ):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama API base URL
            model: Default text model (qwen3-coder:30b for code/web automation)
            vision_model: Vision model for screenshot analysis
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.vision_model = vision_model
        self.timeout = timeout

        self.client = httpx.AsyncClient(timeout=timeout)

        logger.info(f"Ollama client initialized (model={model}, vision={vision_model})")

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> str:
        """
        Generate text completion.

        Args:
            prompt: User prompt
            model: Model to use (defaults to self.model)
            system: System prompt
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream response

        Returns:
            Generated text
        """
        model = model or self.model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
            },
        }

        if system:
            payload["system"] = system

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        if stream:
            return self._generate_stream(payload)
        else:
            return await self._generate_sync(payload)

    async def _generate_sync(self, payload: dict[str, Any]) -> str:
        """Generate text synchronously."""
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()

        result = response.json()
        return result.get("response", "")

    async def _generate_stream(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        """Generate text with streaming."""
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json=payload,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        chunk = json.loads(line)
                        # Yield response text if present
                        if "response" in chunk:
                            yield chunk["response"]
                        # Check if streaming is complete
                        if chunk.get("done", False):
                            logger.debug("Streaming complete (done=true)")
                            break
                    except json.JSONDecodeError:
                        continue

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """
        Chat completion (supports conversation history and tool calls).

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use
            temperature: Sampling temperature
            stream: Whether to stream response
            tools: Optional list of tool schemas (OpenAI format)
            max_tokens: Maximum tokens to generate (converted to num_predict for Ollama)

        Returns:
            Response dict with 'content' and optionally 'tool_calls'
        """
        model = model or self.model

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "think": False,  # Disable thinking mode for qwen3 (avoids hidden token consumption)
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
            },
        }

        # Convert OpenAI-style max_tokens to Ollama's num_predict
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        # Add tools if provided
        if tools:
            payload["tools"] = tools

        if stream:
            return self._chat_stream(payload)
        else:
            return await self._chat_sync(payload)

    async def _chat_sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Chat synchronously, returning full response with tool calls."""
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()

        result = response.json()
        message = result.get("message", {})

        return {
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls", []),
            "role": message.get("role", "assistant"),
            "done": result.get("done", True),
        }

    async def _chat_stream(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        """Chat with streaming."""
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        chunk = json.loads(line)
                        # Yield message content if present
                        if "message" in chunk:
                            yield chunk["message"].get("content", "")
                        # Check if streaming is complete
                        if chunk.get("done", False):
                            logger.debug("Chat streaming complete (done=true)")
                            break
                    except json.JSONDecodeError:
                        continue

    async def analyze_screenshot(
        self,
        screenshot_path: str,
        prompt: str,
        stream: bool = False,
    ) -> str:
        """
        Analyze screenshot using vision model.

        Args:
            screenshot_path: Path to screenshot file
            prompt: Question/instruction about the screenshot
            stream: Whether to stream response

        Returns:
            Analysis result
        """
        # Read and encode screenshot
        screenshot_data = Path(screenshot_path).read_bytes()
        screenshot_b64 = base64.b64encode(screenshot_data).decode("utf-8")

        payload = {
            "model": self.vision_model,
            "prompt": prompt,
            "images": [screenshot_b64],
            "stream": stream,
            "options": {
                "temperature": 0.3,  # Lower for more consistent vision analysis
            },
        }

        if stream:
            return self._generate_stream(payload)
        else:
            return await self._generate_sync(payload)

    async def guide_web_action(
        self,
        task: str,
        page_html: str,
        screenshot_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Guide next web action based on task and page state.

        Uses both text (HTML) and vision (screenshot) for intelligent decisions.

        Args:
            task: User's task description
            page_html: Current page HTML (first 5000 chars)
            screenshot_path: Optional screenshot for vision analysis

        Returns:
            Suggested action with selector and strategy
        """
        # Prepare prompt for code model
        system_prompt = """You are an expert web automation assistant.
Analyze the page and suggest the NEXT action to accomplish the task.

Respond in JSON format:
{
  "action": "click|fill|extract|navigate",
  "selector": "CSS selector for target element",
  "value": "value for fill actions (optional)",
  "reasoning": "why this action makes sense",
  "confidence": 0.0-1.0
}"""

        user_prompt = f"""Task: {task}

Current page HTML (truncated):
```html
{page_html[:5000]}
```

What should I do next?"""

        # Get text-based analysis
        logger.debug("Getting text-based action guidance...")
        text_response = await self.generate(
            prompt=user_prompt,
            system=system_prompt,
            model=self.model,
            temperature=0.3,
        )

        try:
            # Parse JSON response
            action_plan = json.loads(text_response)
        except json.JSONDecodeError:
            # Fallback if not valid JSON
            logger.warning("Failed to parse JSON from LLM, using fallback")
            action_plan = {"action": "extract", "reasoning": text_response, "confidence": 0.5}

        # If screenshot available, enhance with vision analysis
        if screenshot_path and Path(screenshot_path).exists():
            logger.debug("Enhancing with vision analysis...")

            vision_prompt = f"""Look at this webpage screenshot.
The user wants to: {task}

Current plan: {action_plan.get("action")} - {action_plan.get("reasoning")}

Is this the right action? Are there any visual elements we should click instead?
Respond with: CONFIRM if plan is good, or suggest better action."""

            vision_feedback = await self.analyze_screenshot(
                screenshot_path,
                vision_prompt,
            )

            action_plan["vision_feedback"] = vision_feedback

            # Adjust confidence based on vision feedback
            if "CONFIRM" in vision_feedback.upper():
                action_plan["confidence"] = min(1.0, action_plan.get("confidence", 0.5) + 0.2)
            else:
                action_plan["confidence"] = max(0.3, action_plan.get("confidence", 0.5) - 0.1)

        return action_plan

    async def extract_data_with_llm(
        self,
        page_html: str,
        target: str,
    ) -> dict[str, Any]:
        """
        Extract specific data from HTML using LLM.

        Args:
            page_html: Page HTML content
            target: What to extract (e.g., "product prices", "article titles")

        Returns:
            Extracted data in structured format
        """
        system_prompt = """You are a data extraction expert.
Extract the requested information from the HTML and return as JSON.

Return format:
{
  "items": [extracted items],
  "count": number of items,
  "confidence": 0.0-1.0
}"""

        user_prompt = f"""Extract: {target}

From this HTML (truncated):
```html
{page_html[:8000]}
```

Return the extracted data as JSON."""

        response = await self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.2,  # Low temperature for consistent extraction
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"items": [response], "count": 1, "confidence": 0.5, "raw_response": response}

    async def embed(
        self,
        text: str,
        model: str | None = None,
    ) -> list[float]:
        """
        Generate embedding vector for text.

        Uses Ollama's /api/embed endpoint.

        Args:
            text: Text to embed
            model: Embedding model (default: nomic-embed-text or current model)

        Returns:
            List of floats representing the embedding vector
        """
        embed_model = model or "nomic-embed-text"

        try:
            response = await self.client.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": embed_model,
                    "input": text,
                },
            )
            response.raise_for_status()

            result = response.json()
            # Ollama returns {"embeddings": [[...values...]]}
            embeddings = result.get("embeddings", [[]])
            if embeddings and len(embeddings) > 0:
                return embeddings[0]

            logger.warning(f"Empty embedding response for text: {text[:50]}...")
            return []

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Embedding model '{embed_model}' not found, falling back to {self.model}"
                )
                # Fallback: try with current model (some models support embeddings)
                try:
                    response = await self.client.post(
                        f"{self.base_url}/api/embed",
                        json={"model": self.model, "input": text},
                    )
                    response.raise_for_status()
                    result = response.json()
                    embeddings = result.get("embeddings", [[]])
                    return embeddings[0] if embeddings else []
                except Exception:
                    pass
            logger.error(f"Embedding request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []

    async def embed_batch(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model: Embedding model

        Returns:
            List of embedding vectors
        """
        # Ollama supports batch input in /api/embed
        embed_model = model or "nomic-embed-text"

        try:
            response = await self.client.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": embed_model,
                    "input": texts,
                },
            )
            response.raise_for_status()

            result = response.json()
            return result.get("embeddings", [])

        except Exception as e:
            logger.error(f"Batch embedding error: {e}")
            # Fallback to sequential
            return [await self.embed(text, model) for text in texts]

    async def is_available(self) -> bool:
        """Check if Ollama is available (alias for health_check)."""
        return await self.health_check()

    async def health_check(self) -> bool:
        """
        Check if Ollama is running and models are available.

        Returns:
            True if healthy
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]

            logger.info(f"Ollama health check OK. Available models: {model_names}")

            # Check if our models are available
            has_text_model = self.model in model_names
            has_vision_model = self.vision_model in model_names

            if not has_text_model:
                logger.warning(f"Text model '{self.model}' not found")
            if not has_vision_model:
                logger.warning(f"Vision model '{self.vision_model}' not found")

            return has_text_model or has_vision_model

        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def discover_models(self) -> list[dict[str, Any]]:
        """Discover available Ollama models.

        Calls GET /api/tags and returns model info sorted by size (largest first).

        Returns:
            List of dicts with 'name' and 'size' keys, sorted by size descending.
            Empty list if Ollama is unreachable.
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])

            result = []
            for m in models:
                name = m.get("name", "")
                size = m.get("size", 0)
                result.append({"name": name, "size": size})

            # Sort by size descending (largest model first)
            result.sort(key=lambda x: x["size"], reverse=True)
            return result

        except Exception as e:
            logger.warning(f"Ollama model discovery failed: {e}")
            return []

    async def select_best_model(self, preferred_model: str | None = None) -> str | None:
        """Auto-select the best available Ollama model.

        Args:
            preferred_model: Model name to prefer if available.

        Returns:
            Selected model name, or None if no models available.
        """
        models = await self.discover_models()

        if not models:
            return None

        model_names = [m["name"] for m in models]

        # If preferred model is available, use it
        if preferred_model and preferred_model in model_names:
            return preferred_model

        # Filter out embedding models (typically small and not for generation)
        embedding_keywords = ["embed", "nomic", "bge", "e5"]
        generation_models = [
            m for m in models
            if not any(kw in m["name"].lower() for kw in embedding_keywords)
        ]

        if generation_models:
            return generation_models[0]["name"]

        # Fallback: return largest model even if it looks like embedding
        return models[0]["name"]

    @staticmethod
    def format_model_size(size_bytes: int) -> str:
        """Format model size in human-readable format."""
        if size_bytes >= 1_000_000_000:
            return f"{size_bytes / 1_000_000_000:.1f}GB"
        elif size_bytes >= 1_000_000:
            return f"{size_bytes / 1_000_000:.0f}MB"
        else:
            return f"{size_bytes / 1_000:.0f}KB"

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Convenience function for quick testing
async def test_ollama():
    """Test Ollama client."""
    client = OllamaClient()

    # Health check
    healthy = await client.health_check()
    print(f"Ollama healthy: {healthy}")

    if healthy:
        # Test generation
        response = await client.generate(
            prompt="What is the capital of France?",
            temperature=0.1,
        )
        print(f"Response: {response}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_ollama())
