"""Command Input widget with history and autocomplete."""

import contextlib

from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, Static


class CommandInput(Vertical):
    """Command input widget with history and autocomplete support."""

    DEFAULT_CSS = """
    CommandInput {
        dock: bottom;
        height: 5;
        border-top: solid $primary;
        background: $surface-darken-1;
        padding: 0 1;
    }

    CommandInput .label {
        height: 1;
        padding: 0;
        color: $accent;
    }

    CommandInput Input {
        height: 3;
        background: $surface;
        border: solid $primary;
    }

    CommandInput Input:focus {
        border: solid $accent;
    }

    CommandInput .hints {
        height: 1;
        color: $text-muted;
    }
    """

    class CommandSubmitted(Message):
        """Message emitted when a command is submitted."""

        def __init__(self, command: str):
            super().__init__()
            self.command = command

    def __init__(
        self,
        placeholder: str = "Enter a command or task description...",
        label: str = "💬 COMMAND INPUT",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._placeholder = placeholder
        self._label = label
        self._history: list[str] = []
        self._history_index = -1
        self._suggestions: list[str] = []

    def compose(self):
        """Compose the command input."""
        yield Static(f"[bold]{self._label}[/]", classes="label")
        yield Input(placeholder=self._placeholder, id="cmd-input-field")
        yield Static(
            "[dim][Enter] Send  [Tab] Autocomplete  [↑↓] History  [Ctrl+C] Cancel[/]",
            classes="hints",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command submission."""
        command = event.value.strip()
        if command:
            # Add to history
            if not self._history or self._history[-1] != command:
                self._history.append(command)
            self._history_index = -1

            # Clear input
            event.input.value = ""

            # Post message
            self.post_message(self.CommandSubmitted(command))

    def on_key(self, event) -> None:
        """Handle key events for history navigation."""
        input_widget = self.query_one("#cmd-input-field", Input)

        if event.key == "up":
            # Navigate history up
            if self._history:
                if self._history_index == -1:
                    self._history_index = len(self._history) - 1
                elif self._history_index > 0:
                    self._history_index -= 1
                input_widget.value = self._history[self._history_index]
            event.stop()

        elif event.key == "down":
            # Navigate history down
            if self._history and self._history_index != -1:
                if self._history_index < len(self._history) - 1:
                    self._history_index += 1
                    input_widget.value = self._history[self._history_index]
                else:
                    self._history_index = -1
                    input_widget.value = ""
            event.stop()

        elif event.key == "tab":
            # Autocomplete (basic implementation)
            current = input_widget.value.strip()
            if current and self._suggestions:
                matches = [s for s in self._suggestions if s.startswith(current)]
                if matches:
                    input_widget.value = matches[0]
            event.stop()

    def set_suggestions(self, suggestions: list[str]) -> None:
        """Set autocomplete suggestions."""
        self._suggestions = suggestions

    def get_history(self) -> list[str]:
        """Get command history."""
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear command history."""
        self._history.clear()
        self._history_index = -1

    def focus_input(self) -> None:
        """Focus the input widget."""
        with contextlib.suppress(Exception):
            self.query_one("#cmd-input-field", Input).focus()
