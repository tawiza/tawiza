"""
Ollama Chat Model wrapper for browser-use integration.

This module provides a wrapper that makes OllamaAdapter compatible
with browser-use's BaseChatModel protocol.
- sandboxes =EB@; "EB2"
- F=@
"""

from typing import TypeVar

from browser_use.llm.base import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion
from loguru import logger

from src.infrastructure.ml.ollama import OllamaAdapter

T = TypeVar("T")


class OllamaBrowserChatModel:
    """
    Wrapper around OllamaAdapter that implements browser-use's BaseChatModel protocol.

    This allows using Ollama models with browser-use Agent.
    """

    def __init__(self, ollama_adapter: OllamaAdapter, model: str = "qwen3-coder:30b"):
        """
        Initialize Ollama browser chat model.

        Args:
            ollama_adapter: The Ollama adapter instance
            model: Model name to use (default: qwen3-coder:30b)
        """
        self.ollama = ollama_adapter
        self.model = model
        logger.info(f"OllamaBrowserChatModel initialized with model: {model}")

    @property
    def provider(self) -> str:
        """Get provider name."""
        return "ollama"

    @property
    def name(self) -> str:
        """Get model name."""
        return self.model

    @property
    def model_name(self) -> str:
        """Get model name (legacy support)."""
        return self.model

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        output_format: type[T] | None = None,
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        """
        Invoke the chat model with messages.

        Args:
            messages: List of messages (system, user, assistant)
            output_format: Optional Pydantic model for structured output

        Returns:
            ChatInvokeCompletion with response
        """
        try:
            # Convert browser-use messages to Ollama format
            ollama_messages = []
            for msg in messages:
                # Extract content from the message
                if hasattr(msg, "role") and hasattr(msg, "content"):
                    ollama_messages.append({"role": msg.role, "content": msg.content})
                else:
                    # Fallback: try to convert to dict
                    msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg
                    if isinstance(msg_dict, dict):
                        ollama_messages.append(msg_dict)

            logger.debug(f"Sending {len(ollama_messages)} messages to Ollama model {self.model}")

            # Call Ollama chat API
            response = await self.ollama.chat(
                model=self.model,
                messages=ollama_messages,
                temperature=0.1,  # Low temperature for more deterministic behavior
                stream=False,
            )

            # Extract the response content
            response_content = response.get("message", {}).get("content", "")

            logger.debug(f"Received response from Ollama ({len(response_content)} chars)")

            # If output_format is specified, try to parse as structured output
            if output_format:
                try:
                    # Try to parse the response as JSON and validate with Pydantic
                    import json

                    parsed = json.loads(response_content)
                    structured_output = output_format(**parsed)
                    return ChatInvokeCompletion(
                        content=structured_output,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to parse structured output: {e}. Returning raw content."
                    )
                    # Fall back to string content
                    return ChatInvokeCompletion(
                        content=response_content,
                    )

            # Return simple string response
            return ChatInvokeCompletion(
                content=response_content,
            )

        except Exception as e:
            logger.error(f"Error invoking Ollama chat model: {e}", exc_info=True)
