"""
AI Assistant Service for Tawiza

Provides intelligent conversational interface for the Tawiza platform.
"""

import uuid
from datetime import datetime
from typing import Any

from src.application.conversation.context_manager import (
    ContextManager,
    ConversationContext,
)
from src.application.conversation.dialog_manager import DialogManager
from src.application.conversation.response_generator import ResponseGenerator
from src.infrastructure.ml.ollama.ollama_adapter import OllamaAdapter


class AssistantService:
    """
    Main AI Assistant service

    Orchestrates conversation management, dialog flow, and response generation
    with optional RAG (Retrieval-Augmented Generation) integration.
    """

    def __init__(
        self,
        llm_client: OllamaAdapter | None = None,
        embedding_service: Any | None = None,
        model_name: str = "llama3.2:3b",
        use_rag: bool = False,
    ):
        """
        Initialize Assistant Service

        Args:
            llm_client: OllamaAdapter or LitServeClient for LLM
            embedding_service: EmbeddingService for RAG (optional)
            model_name: LLM model to use
            use_rag: Enable Retrieval-Augmented Generation
        """
        # Initialize LLM client
        if llm_client is None:
            from src.infrastructure.config.settings import get_settings

            settings = get_settings()
            llm_client = OllamaAdapter(base_url=settings.ollama.base_url)

        self.llm = llm_client
        self.embedding_service = embedding_service
        self.model_name = model_name
        self.use_rag = use_rag and embedding_service is not None

        # Initialize components
        self.context_manager = ContextManager(max_context_length=20)
        self.dialog_manager = DialogManager()
        self.response_generator = ResponseGenerator(llm_client=llm_client, model_name=model_name)

    async def chat(
        self, message: str, session_id: str | None = None, user_id: str = "default_user", **metadata
    ) -> dict[str, Any]:
        """
        Process a chat message

        Args:
            message: User's message
            session_id: Session ID (creates new if None)
            user_id: User identifier
            **metadata: Additional metadata

        Returns:
            Response with message and metadata
        """
        # Create or get session
        if session_id is None:
            session_id = str(uuid.uuid4())

        context = self.context_manager.get_or_create_session(session_id, user_id)

        # Add user message to context
        context.add_user_message(message, **metadata)

        # Process dialog turn
        dialog_result = await self.dialog_manager.process_turn(message, context)

        # Get RAG context if enabled
        rag_results = None
        if self.use_rag and self.embedding_service:
            rag_results = await self._get_rag_context(message)

        # Generate response
        response_text = await self.response_generator.generate_response(
            user_input=message, context=context, use_rag=self.use_rag, rag_results=rag_results
        )

        # Add assistant message to context
        context.add_assistant_message(
            response_text,
            dialog_action=dialog_result["action"],
            dialog_state=dialog_result["state"],
        )

        return {
            "session_id": session_id,
            "message": response_text,
            "dialog_state": dialog_result["state"],
            "dialog_action": dialog_result["action"],
            "requires_confirmation": dialog_result.get("requires_confirmation", False),
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "model": self.model_name,
                "used_rag": self.use_rag and rag_results is not None,
            },
        }

    async def get_help(self) -> str:
        """Get help message"""
        return self.response_generator.generate_help_response()

    async def get_capabilities(self) -> str:
        """Get capabilities summary"""
        return self.response_generator.generate_capabilities_summary()

    async def _get_rag_context(self, query: str, limit: int = 3) -> list[dict[str, Any]] | None:
        """
        Get relevant context from vector database using RAG

        Args:
            query: User's query
            limit: Number of results to retrieve

        Returns:
            List of relevant documents
        """
        if not self.embedding_service:
            return None

        try:
            # Search vector database
            results = await self.embedding_service.search(
                query=query, limit=limit, distance_threshold=0.8
            )

            # Format results for RAG
            rag_results = []
            for result in results:
                rag_results.append(
                    {
                        "content": result.content,
                        "metadata": result.metadata,
                        "score": 1.0 - (result.distance / 2.0),  # Normalize to 0-1
                    }
                )

            return rag_results

        except Exception as e:
            print(f"Error getting RAG context: {e}")
            return None

    def get_session(self, session_id: str) -> ConversationContext | None:
        """Get conversation session"""
        return self.context_manager.get_session(session_id)

    def get_conversation_history(self, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get conversation history for session"""
        context = self.context_manager.get_session(session_id)
        if not context:
            return []

        recent = context.get_recent_messages(limit)
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "metadata": msg.metadata,
            }
            for msg in recent
        ]

    def clear_session(self, session_id: str) -> bool:
        """Clear conversation session"""
        if session_id in self.context_manager.sessions:
            del self.context_manager.sessions[session_id]
            return True
        return False

    async def suggest_command(self, natural_language_query: str) -> str | None:
        """
        Suggest CLI command from natural language

        Args:
            natural_language_query: User's query in natural language

        Returns:
            Suggested CLI command
        """
        # Use dialog manager to parse command
        return self.dialog_manager._parse_command_from_nl(natural_language_query)

    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs"""
        return list(self.context_manager.sessions.keys())

    def export_conversation(self, session_id: str, filepath: str):
        """
        Export conversation to file

        Args:
            session_id: Session to export
            filepath: Output file path
        """
        self.context_manager.save_session(session_id, filepath)

    def import_conversation(self, filepath: str) -> str:
        """
        Import conversation from file

        Args:
            filepath: Input file path

        Returns:
            Session ID of imported conversation
        """
        context = self.context_manager.load_session(filepath)
        return context.session_id


# Singleton instance for CLI use
_assistant_instance: AssistantService | None = None


def get_assistant(
    llm_client: OllamaAdapter | None = None,
    embedding_service: Any | None = None,
    model_name: str = "llama3.2:3b",
    use_rag: bool = False,
) -> AssistantService:
    """
    Get or create AssistantService instance

    Args:
        llm_client: OllamaAdapter instance (creates default if None)
        embedding_service: EmbeddingService for RAG
        model_name: Model to use
        use_rag: Enable RAG

    Returns:
        AssistantService instance
    """
    global _assistant_instance

    if _assistant_instance is None:
        _assistant_instance = AssistantService(
            llm_client=llm_client,
            embedding_service=embedding_service,
            model_name=model_name,
            use_rag=use_rag,
        )

    return _assistant_instance
