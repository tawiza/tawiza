"""
Conversation Context Management

Manages conversation state, history, and context for the AI assistant.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any


class MessageRole(StrEnum):
    """Message roles in conversation"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """Single message in conversation"""

    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create from dictionary"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConversationContext:
    """
    Manages conversation state and context

    Maintains conversation history, user profile, and working memory
    for context-aware responses.
    """

    session_id: str
    user_id: str = "default_user"
    messages: list[Message] = field(default_factory=list)
    user_profile: dict[str, Any] = field(default_factory=dict)
    conversation_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    # Working memory for current conversation
    entities: dict[str, Any] = field(default_factory=dict)
    topics: list[str] = field(default_factory=list)
    current_intent: str | None = None

    def add_message(self, role: MessageRole, content: str, **metadata):
        """Add a message to conversation history"""
        message = Message(role=role, content=content, metadata=metadata)
        self.messages.append(message)
        self.last_activity = datetime.now()
        return message

    def add_user_message(self, content: str, **metadata):
        """Add user message"""
        return self.add_message(MessageRole.USER, content, **metadata)

    def add_assistant_message(self, content: str, **metadata):
        """Add assistant message"""
        return self.add_message(MessageRole.ASSISTANT, content, **metadata)

    def add_system_message(self, content: str, **metadata):
        """Add system message"""
        return self.add_message(MessageRole.SYSTEM, content, **metadata)

    def get_recent_messages(self, n: int = 10) -> list[Message]:
        """Get N most recent messages"""
        return self.messages[-n:] if len(self.messages) > n else self.messages

    def get_conversation_history(self, role: MessageRole | None = None) -> list[Message]:
        """Get conversation history, optionally filtered by role"""
        if role:
            return [m for m in self.messages if m.role == role]
        return self.messages

    def update_entity(self, entity_id: str, entity_data: dict[str, Any]):
        """Update entity in working memory"""
        if entity_id not in self.entities:
            self.entities[entity_id] = {
                "id": entity_id,
                "first_seen": datetime.now(),
                "mentions": 0,
                "data": {},
            }

        self.entities[entity_id]["mentions"] += 1
        self.entities[entity_id]["last_seen"] = datetime.now()
        self.entities[entity_id]["data"].update(entity_data)

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Get entity from working memory"""
        return self.entities.get(entity_id)

    def add_topic(self, topic: str):
        """Add topic to conversation"""
        if topic not in self.topics:
            self.topics.append(topic)

    def get_current_topic(self) -> str | None:
        """Get current conversation topic"""
        return self.topics[-1] if self.topics else None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "messages": [m.to_dict() for m in self.messages],
            "user_profile": self.user_profile,
            "conversation_state": self.conversation_state,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "entities": self.entities,
            "topics": self.topics,
            "current_intent": self.current_intent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationContext":
        """Create from dictionary"""
        context = cls(
            session_id=data["session_id"],
            user_id=data.get("user_id", "default_user"),
            user_profile=data.get("user_profile", {}),
            conversation_state=data.get("conversation_state", {}),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            entities=data.get("entities", {}),
            topics=data.get("topics", []),
            current_intent=data.get("current_intent"),
        )

        # Restore messages
        context.messages = [Message.from_dict(m) for m in data.get("messages", [])]

        return context


class ContextManager:
    """
    Manages conversation contexts and provides context-aware operations
    """

    def __init__(self, max_context_length: int = 20, max_history_tokens: int = 4000):
        self.max_context_length = max_context_length
        self.max_history_tokens = max_history_tokens
        self.sessions: dict[str, ConversationContext] = {}

    def create_session(self, session_id: str, user_id: str = "default_user") -> ConversationContext:
        """Create a new conversation session"""
        context = ConversationContext(session_id=session_id, user_id=user_id)
        self.sessions[session_id] = context
        return context

    def get_session(self, session_id: str) -> ConversationContext | None:
        """Get existing session"""
        return self.sessions.get(session_id)

    def get_or_create_session(
        self, session_id: str, user_id: str = "default_user"
    ) -> ConversationContext:
        """Get existing session or create new one"""
        if session_id not in self.sessions:
            return self.create_session(session_id, user_id)
        return self.sessions[session_id]

    def update_context(
        self,
        session_id: str,
        new_message: str | None = None,
        role: MessageRole = MessageRole.USER,
        **updates,
    ) -> ConversationContext:
        """Update conversation context"""
        context = self.get_or_create_session(session_id)

        # Add new message if provided
        if new_message:
            context.add_message(role, new_message)

        # Apply updates to conversation state
        context.conversation_state.update(updates)

        # Prune context if too long
        if len(context.messages) > self.max_context_length:
            context = self.prune_context(context)

        return context

    def prune_context(self, context: ConversationContext) -> ConversationContext:
        """
        Prune conversation context to stay within limits

        Keeps most recent messages and important context
        """
        # Always keep system messages
        system_messages = [m for m in context.messages if m.role == MessageRole.SYSTEM]

        # Get recent conversation
        recent_messages = context.messages[-self.max_context_length :]

        # Combine, removing duplicate system messages
        pruned_messages = system_messages + [
            m for m in recent_messages if m.role != MessageRole.SYSTEM
        ]

        context.messages = pruned_messages
        return context

    def resolve_references(self, text: str, context: ConversationContext) -> str:
        """
        Resolve pronouns and references in text

        Uses conversation context to resolve "it", "that", entity references
        """
        # Simple pronoun resolution (can be enhanced with NLP)
        resolved = text

        # Get most recent entities mentioned
        recent_entities = sorted(
            context.entities.values(), key=lambda e: e.get("last_seen", datetime.min), reverse=True
        )

        # If text contains "it" or "that", try to resolve
        if any(word in text.lower() for word in ["it", "that", "this"]) and recent_entities:
            # Use most recently mentioned entity
            entity = recent_entities[0]
            # This is a simple heuristic - real implementation would use NER
            context.metadata["last_referenced_entity"] = entity["id"]

        return resolved

    def extract_context_for_prompt(
        self, context: ConversationContext, max_messages: int = 10
    ) -> str:
        """
        Extract relevant context for LLM prompt

        Creates a formatted conversation history for the prompt
        """
        recent = context.get_recent_messages(max_messages)

        formatted = []
        for msg in recent:
            if msg.role == MessageRole.SYSTEM:
                continue  # System messages handled separately

            role_label = "User" if msg.role == MessageRole.USER else "Assistant"
            formatted.append(f"{role_label}: {msg.content}")

        return "\n".join(formatted)

    def get_relevant_entities(self, context: ConversationContext) -> list[dict[str, Any]]:
        """Get entities relevant to current conversation"""
        # Sort by recency and relevance
        entities = sorted(
            context.entities.values(),
            key=lambda e: (e["mentions"], e.get("last_seen", datetime.min)),
            reverse=True,
        )

        return entities[:5]  # Top 5 most relevant

    def detect_topic_shift(self, context: ConversationContext, new_input: str) -> bool:
        """
        Detect if conversation topic has shifted

        Returns True if topic change detected
        """
        current_topic = context.get_current_topic()
        if not current_topic:
            return False

        # Simple keyword-based detection (can be enhanced with embeddings)
        # For now, just check if new input shares keywords with current topic
        current_keywords = set(current_topic.lower().split())
        input_keywords = set(new_input.lower().split())

        overlap = len(current_keywords & input_keywords)

        # If less than 20% overlap, likely a topic shift
        return overlap < len(current_keywords) * 0.2

    def save_session(self, session_id: str, filepath: str):
        """Save session to file"""
        context = self.get_session(session_id)
        if not context:
            raise ValueError(f"Session {session_id} not found")

        with open(filepath, "w") as f:
            json.dump(context.to_dict(), f, indent=2)

    def load_session(self, filepath: str) -> ConversationContext:
        """Load session from file"""
        with open(filepath) as f:
            data = json.load(f)

        context = ConversationContext.from_dict(data)
        self.sessions[context.session_id] = context
        return context
