"""
Response Generation for AI Assistant

Generates intelligent, context-aware responses using LLM integration.
"""

import re
from typing import Any

from .context_manager import ConversationContext, MessageRole


class ResponseGenerator:
    """
    Generates intelligent responses using LLM

    Integrates with Ollama/LitServe for response generation
    """

    def __init__(
        self,
        llm_client,  # OllamaAdapter or LitServeClient
        model_name: str = "llama3.2:3b",
        temperature: float = 0.7,
        max_tokens: int = 500,
    ):
        """
        Initialize response generator

        Args:
            llm_client: OllamaAdapter or LitServeClient instance
            model_name: Model to use for generation
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
        """
        self.llm = llm_client
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Response templates for common scenarios
        self.templates = {
            "greeting": [
                "Hello! I'm the Tawiza AI assistant. How can I help you today?",
                "Hi there! I'm here to help you with fine-tuning, training, and model management. What would you like to do?",
                "Welcome! I can assist you with the Tawiza platform. What brings you here?",
            ],
            "farewell": [
                "Goodbye! Feel free to come back if you need more help.",
                "See you later! Don't hesitate to ask if you have more questions.",
                "Take care! I'm here whenever you need assistance.",
            ],
            "clarification": [
                "I'm not sure I understand. Could you rephrase that?",
                "Could you provide more details about what you're trying to do?",
                "I want to make sure I help you correctly. Can you elaborate?",
            ],
            "fallback": [
                "I'm not quite sure how to help with that. Try asking about fine-tuning models, viewing system status, or managing prompts.",
                "That's outside my current capabilities. I can help you with model training, system commands, and data management.",
                "I don't have information about that. Would you like to know what I can help you with?",
            ],
        }

        # System prompts for different contexts
        self.system_prompts = {
            "general": """You are the Tawiza AI Assistant, a helpful and knowledgeable assistant for the Tawiza platform.

Tawiza is a comprehensive AI/ML operations platform that provides:
- Model fine-tuning and training (LLaMA-Factory, OpenRLHF)
- Ollama integration for local LLM serving
- Vector database (pgvector) for semantic search
- LitServe for optimized LLM serving (2-5x faster)
- Data annotation with Label Studio
- MLflow for experiment tracking
- Continuous learning and retraining pipelines

You help users with:
- Running CLI commands
- Understanding system capabilities
- Troubleshooting issues
- Best practices for fine-tuning and training
- Explaining technical concepts

Be concise, helpful, and provide actionable guidance. When referencing commands, use the actual CLI syntax.
If you don't know something, say so and suggest alternatives.""",
            "technical": """You are a technical expert assistant for the Tawiza platform.

Provide detailed, accurate technical guidance about:
- Fine-tuning workflows and hyperparameters
- Model architectures and selection
- Performance optimization
- System configuration
- Troubleshooting errors

Use technical language appropriately and provide code examples when relevant.""",
            "beginner": """You are a friendly, patient tutor for the Tawiza platform.

Help beginners understand:
- Basic concepts of fine-tuning and LLMs
- How to get started with Tawiza
- Step-by-step guidance
- Common pitfalls to avoid

Use simple language and provide encouragement. Break down complex topics into understandable chunks.""",
        }

    async def generate_response(
        self,
        user_input: str,
        context: ConversationContext,
        use_rag: bool = False,
        rag_results: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Generate response to user input

        Args:
            user_input: User's message
            context: Conversation context
            use_rag: Whether to use RAG (Retrieval-Augmented Generation)
            rag_results: Retrieved documents for RAG

        Returns:
            Generated response
        """
        # Detect intent
        intent = self._detect_simple_intent(user_input)

        # Use template for simple intents
        if intent in ["greeting", "farewell"]:
            import random

            return random.choice(self.templates[intent])

        # Build prompt
        prompt = self._build_prompt(user_input, context, rag_results)

        # Select system prompt based on user profile
        system_prompt = self._select_system_prompt(context)

        # Generate with LLM
        try:
            response = await self._generate_with_llm(prompt=prompt, system_prompt=system_prompt)

            # Post-process response
            response = self._post_process_response(response)

            return response

        except Exception as e:
            print(f"Error generating response: {e}")
            import random

            return random.choice(self.templates["fallback"])

    def _detect_simple_intent(self, text: str) -> str | None:
        """Detect simple intents using pattern matching"""
        text_lower = text.lower().strip()

        # Greetings
        if any(word in text_lower for word in ["hello", "hi", "hey", "greetings"]):
            return "greeting"

        # Farewells
        if any(word in text_lower for word in ["bye", "goodbye", "exit", "quit"]):
            return "farewell"

        # Help requests
        if any(word in text_lower for word in ["help", "what can you", "how do i"]):
            return "help"

        return None

    def _build_prompt(
        self,
        user_input: str,
        context: ConversationContext,
        rag_results: list[dict[str, Any]] | None = None,
    ) -> str:
        """Build prompt for LLM"""

        parts = []

        # Add conversation history
        if len(context.messages) > 1:
            parts.append("Conversation history:")
            recent_messages = context.get_recent_messages(5)
            for msg in recent_messages[:-1]:  # Exclude current message
                if msg.role == MessageRole.USER:
                    parts.append(f"User: {msg.content}")
                elif msg.role == MessageRole.ASSISTANT:
                    parts.append(f"Assistant: {msg.content}")
            parts.append("")

        # Add RAG context if available
        if rag_results:
            parts.append("Relevant information:")
            for i, result in enumerate(rag_results[:3], 1):
                parts.append(f"{i}. {result.get('content', '')}")
            parts.append("")

        # Add current user input
        parts.append(f"User: {user_input}")
        parts.append("Assistant:")

        return "\n".join(parts)

    def _select_system_prompt(self, context: ConversationContext) -> str:
        """Select appropriate system prompt based on context"""
        # Check user profile for preferences
        user_level = context.user_profile.get("experience_level", "general")

        if user_level == "expert":
            return self.system_prompts["technical"]
        elif user_level == "beginner":
            return self.system_prompts["beginner"]
        else:
            return self.system_prompts["general"]

    async def _generate_with_llm(self, prompt: str, system_prompt: str) -> str:
        """Generate response using LLM"""

        # Check if using OllamaAdapter or LitServeClient
        if hasattr(self.llm, "generate"):
            # OllamaAdapter or LitServeClient
            response = await self.llm.generate(
                prompt=prompt,
                model=self.model_name,
                system=system_prompt,
                options={
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            )
            return response.get("response", "")

        # Fallback for other clients
        return "I'm having trouble connecting to the language model. Please try again."

    def _post_process_response(self, response: str) -> str:
        """Post-process LLM response"""

        # Remove trailing whitespace
        response = response.strip()

        # Remove common LLM artifacts
        response = re.sub(r"(User:|Assistant:)$", "", response).strip()

        # Ensure response ends with punctuation
        if response and response[-1] not in ".!?":
            response += "."

        # Limit length if too long
        if len(response) > 1000:
            # Find last sentence within limit
            sentences = response.split(". ")
            truncated = []
            length = 0

            for sentence in sentences:
                if length + len(sentence) > 950:
                    break
                truncated.append(sentence)
                length += len(sentence) + 2

            response = ". ".join(truncated)
            if not response.endswith("."):
                response += "."

        return response

    def generate_help_response(self) -> str:
        """Generate help message"""
        return """I can help you with the following:

**Model Management:**
- List available models: `tawiza models list`
- Show model details: `tawiza models show <model-name>`
- Pull models: `tawiza models pull <model-name>`

**Fine-tuning:**
- Start fine-tuning: `tawiza finetune start --config <config-file>`
- Check status: `tawiza finetune status <job-id>`
- List jobs: `tawiza finetune list`

**Prompts:**
- List prompts: `tawiza prompts list`
- Test prompt: `tawiza prompts test <prompt-id>`

**System:**
- System status: `tawiza system status`
- View logs: `tawiza system logs`

Ask me about any of these topics, or try commands like:
- "How do I fine-tune a model?"
- "Show me system status"
- "What models are available?"
- "Explain fine-tuning parameters"
"""

    def generate_capabilities_summary(self) -> str:
        """Generate summary of assistant capabilities"""
        return """🤖 Tawiza AI Assistant Capabilities

I'm here to help you with:

1. **Command Guidance**: Get help with CLI commands and syntax
2. **Technical Q&A**: Ask questions about fine-tuning, models, and the platform
3. **Troubleshooting**: Debug issues and get solutions
4. **Best Practices**: Learn optimal approaches for your use cases
5. **Explanations**: Understand technical concepts in simple terms

**Platform Features I Know About:**
- Model fine-tuning with LLaMA-Factory and OpenRLHF
- Ollama local LLM serving
- Vector database for semantic search (pgvector)
- LitServe optimization (2-5x faster inference)
- MLflow experiment tracking
- Label Studio for data annotation
- Continuous learning pipelines

Just ask me anything about the Tawiza platform!
"""
