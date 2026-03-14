"""
Dialog Management for AI Assistant

Manages conversation flow and dialog state.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any

from .context_manager import ConversationContext


class DialogState(StrEnum):
    """Dialog states"""

    IDLE = "idle"
    GREETING = "greeting"
    HELPING = "helping"
    CLARIFYING = "clarifying"
    EXECUTING = "executing"
    CONFIRMING = "confirming"
    ENDING = "ending"


@dataclass
class DialogAction:
    """Action to take in dialog"""

    action_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    next_state: DialogState | None = None
    requires_confirmation: bool = False


class DialogManager:
    """
    Manages conversation flow and state transitions

    Handles dialog states, actions, and multi-turn conversations
    """

    def __init__(self):
        self.current_state = DialogState.IDLE
        self.state_history: list = []

        # Action handlers
        self.action_handlers: dict[str, Callable] = {
            "greet": self._handle_greeting,
            "provide_help": self._handle_help_request,
            "execute_command": self._handle_command_execution,
            "clarify": self._handle_clarification,
            "confirm": self._handle_confirmation,
            "end_conversation": self._handle_end_conversation,
        }

    async def process_turn(self, user_input: str, context: ConversationContext) -> dict[str, Any]:
        """
        Process a conversation turn

        Args:
            user_input: User's input
            context: Conversation context

        Returns:
            Dialog action and response data
        """
        # Determine dialog action
        action = self._determine_action(user_input, context)

        # Execute action
        result = await self._execute_action(action, user_input, context)

        # Update state
        self._transition_state(action.next_state)

        # Store in history
        self.state_history.append(
            {
                "timestamp": datetime.now(),
                "state": self.current_state.value,
                "action": action.action_type,
                "user_input": user_input,
            }
        )

        return {
            "action": action.action_type,
            "state": self.current_state.value,
            "result": result,
            "requires_confirmation": action.requires_confirmation,
        }

    def _determine_action(self, user_input: str, context: ConversationContext) -> DialogAction:
        """Determine what action to take based on input"""

        text_lower = user_input.lower().strip()

        # Greeting detection
        if any(word in text_lower for word in ["hello", "hi", "hey", "greetings"]):
            return DialogAction(action_type="greet", next_state=DialogState.GREETING)

        # Help request detection
        if any(phrase in text_lower for phrase in ["help", "what can you", "how do i", "?"]):
            return DialogAction(action_type="provide_help", next_state=DialogState.HELPING)

        # Command execution detection
        if any(word in text_lower for word in ["run", "execute", "start", "show", "list"]):
            return DialogAction(
                action_type="execute_command",
                parameters={"command_hint": text_lower},
                next_state=DialogState.EXECUTING,
                requires_confirmation=True,
            )

        # Exit/goodbye detection
        if any(word in text_lower for word in ["bye", "goodbye", "exit", "quit"]):
            return DialogAction(action_type="end_conversation", next_state=DialogState.ENDING)

        # Clarification needed
        if len(text_lower.split()) < 3 or text_lower.count("?") > 2:
            return DialogAction(action_type="clarify", next_state=DialogState.CLARIFYING)

        # Default: provide help
        return DialogAction(action_type="provide_help", next_state=DialogState.HELPING)

    async def _execute_action(
        self, action: DialogAction, user_input: str, context: ConversationContext
    ) -> dict[str, Any]:
        """Execute dialog action"""

        handler = self.action_handlers.get(action.action_type)
        if not handler:
            return {"error": f"Unknown action: {action.action_type}"}

        return await handler(user_input, context, action.parameters)

    async def _handle_greeting(
        self, user_input: str, context: ConversationContext, params: dict
    ) -> dict[str, Any]:
        """Handle greeting"""
        return {
            "response_type": "greeting",
            "suggestions": [
                "What would you like to do?",
                "Ask me about models, fine-tuning, or system status",
            ],
        }

    async def _handle_help_request(
        self, user_input: str, context: ConversationContext, params: dict
    ) -> dict[str, Any]:
        """Handle help request"""

        # Detect specific help topic
        topics = {
            "model": ["model", "models", "llm"],
            "finetune": ["finetune", "fine-tune", "training", "train"],
            "system": ["system", "status", "health"],
            "prompt": ["prompt", "prompts"],
        }

        detected_topic = None
        for topic, keywords in topics.items():
            if any(kw in user_input.lower() for kw in keywords):
                detected_topic = topic
                break

        return {
            "response_type": "help",
            "topic": detected_topic,
            "suggestions": [
                "List available models",
                "Start a fine-tuning job",
                "Check system status",
            ],
        }

    async def _handle_command_execution(
        self, user_input: str, context: ConversationContext, params: dict
    ) -> dict[str, Any]:
        """Handle command execution"""

        # Extract potential command
        params.get("command_hint", "")

        # Parse command from natural language
        suggested_command = self._parse_command_from_nl(user_input)

        return {
            "response_type": "command_suggestion",
            "suggested_command": suggested_command,
            "needs_confirmation": True,
            "explanation": "I think you want to run this command. Shall I proceed?",
        }

    async def _handle_clarification(
        self, user_input: str, context: ConversationContext, params: dict
    ) -> dict[str, Any]:
        """Handle clarification request"""
        return {
            "response_type": "clarification",
            "questions": [
                "What specific aspect would you like help with?",
                "Could you provide more details?",
            ],
        }

    async def _handle_confirmation(
        self, user_input: str, context: ConversationContext, params: dict
    ) -> dict[str, Any]:
        """Handle confirmation"""

        text_lower = user_input.lower()

        # Positive confirmation
        if any(word in text_lower for word in ["yes", "yeah", "sure", "ok", "proceed"]):
            return {"response_type": "confirmed", "action": "execute_pending_action"}

        # Negative confirmation
        if any(word in text_lower for word in ["no", "nope", "cancel", "stop"]):
            return {"response_type": "cancelled", "action": "cancel_pending_action"}

        # Unclear - ask again
        return {"response_type": "unclear", "action": "request_clarification"}

    async def _handle_end_conversation(
        self, user_input: str, context: ConversationContext, params: dict
    ) -> dict[str, Any]:
        """Handle conversation ending"""
        return {"response_type": "farewell", "should_exit": True}

    def _transition_state(self, new_state: DialogState | None):
        """Transition to new dialog state"""
        if new_state:
            self.current_state = new_state

    def _parse_command_from_nl(self, text: str) -> str | None:
        """
        Parse CLI command from natural language

        This is a simple pattern-matching approach. Can be enhanced with NLU.
        """
        text_lower = text.lower()

        # Model-related commands
        if "list" in text_lower and "model" in text_lower:
            return "tawiza models list"

        if "show" in text_lower and "model" in text_lower:
            # Try to extract model name
            return "tawiza models show <model-name>"

        if "pull" in text_lower and "model" in text_lower:
            return "tawiza models pull <model-name>"

        # Fine-tuning commands
        if "start" in text_lower and any(
            w in text_lower for w in ["finetune", "fine-tune", "training"]
        ):
            return "tawiza finetune start --config <config-file>"

        if "status" in text_lower and any(
            w in text_lower for w in ["finetune", "fine-tune", "job"]
        ):
            return "tawiza finetune status <job-id>"

        if "list" in text_lower and any(w in text_lower for w in ["finetune", "fine-tune", "job"]):
            return "tawiza finetune list"

        # System commands
        if "status" in text_lower or "health" in text_lower:
            return "tawiza system status"

        if "log" in text_lower:
            return "tawiza system logs"

        # Prompt commands
        if "list" in text_lower and "prompt" in text_lower:
            return "tawiza prompts list"

        if "test" in text_lower and "prompt" in text_lower:
            return "tawiza prompts test <prompt-id>"

        return None

    def get_conversation_summary(self) -> dict[str, Any]:
        """Get summary of conversation flow"""
        return {
            "current_state": self.current_state.value,
            "total_turns": len(self.state_history),
            "states_visited": list({h["state"] for h in self.state_history}),
            "actions_taken": list({h["action"] for h in self.state_history}),
        }
