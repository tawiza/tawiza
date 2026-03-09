"""Result presenter - interactive result handling."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResultAction(Enum):
    """Available actions for results."""
    VIEW = "view"       # View full result
    SAVE = "save"       # Save to file
    COPY = "copy"       # Copy to clipboard
    OPEN = "open"       # Open in editor
    EXPORT = "export"   # Export to format
    CHAIN = "chain"     # Send to next task


@dataclass
class DisplayResult:
    """Formatted result for display."""
    content: str
    is_inline: bool
    preview: str | None = None
    detected_format: str = "text"
    actions: list[ResultAction] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ResultPresenter:
    """Handles result formatting and user interaction."""

    INLINE_THRESHOLD = 500  # Characters
    PREVIEW_LINES = 10

    def __init__(self):
        self._results: dict[str, Any] = {}
        self._last_key: str | None = None

    def format_for_display(self, content: Any) -> DisplayResult:
        """Format result for display with appropriate styling.

        Args:
            content: The result content to display

        Returns:
            DisplayResult with formatting info
        """
        content_str = str(content)
        detected_format = self._detect_format(content_str)
        is_inline = len(content_str) <= self.INLINE_THRESHOLD

        preview = None
        if not is_inline:
            lines = content_str.split("\n")
            preview_lines = lines[:self.PREVIEW_LINES]
            preview = "\n".join(preview_lines)

            # Truncate if preview is still too long (for single long lines)
            if len(preview) > self.INLINE_THRESHOLD:
                preview = preview[:self.INLINE_THRESHOLD] + "..."

            if len(lines) > self.PREVIEW_LINES:
                remaining = len(lines) - self.PREVIEW_LINES
                preview += f"\n... ({remaining} more lines)"

        # All results get these actions
        actions = [
            ResultAction.VIEW,
            ResultAction.SAVE,
            ResultAction.COPY,
            ResultAction.CHAIN,
        ]

        return DisplayResult(
            content=content_str,
            is_inline=is_inline,
            preview=preview,
            detected_format=detected_format,
            actions=actions,
        )

    def _detect_format(self, content: str) -> str:
        """Detect the format of content.

        Args:
            content: Content string to analyze

        Returns:
            Format name: "table", "code", "json", "text"
        """
        # Check for CSV/table
        lines = content.strip().split("\n")
        if len(lines) >= 2:
            first_line_commas = lines[0].count(",")
            if first_line_commas >= 1 and all(
                line.count(",") == first_line_commas for line in lines[:5]
            ):
                return "table"

        # Check for code patterns
        code_patterns = [
            r"^def\s+\w+\s*\(",
            r"^class\s+\w+",
            r"^import\s+",
            r"^function\s+",
            r"^\s*if\s+.*:",
            r"^\s*for\s+.*:",
        ]
        for pattern in code_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return "code"

        # Check for JSON
        if content.strip().startswith("{") or content.strip().startswith("["):
            try:
                import json
                json.loads(content)
                return "json"
            except (json.JSONDecodeError, ValueError):
                pass

        return "text"

    def store_result(self, key: str, result: Any) -> None:
        """Store a result for later retrieval.

        Args:
            key: Identifier for the result
            result: The result to store
        """
        self._results[key] = result
        self._last_key = key

    def get_result(self, key: str) -> Any | None:
        """Retrieve a stored result.

        Args:
            key: Result identifier

        Returns:
            The stored result or None
        """
        return self._results.get(key)

    def get_last_result(self) -> Any | None:
        """Get the most recently stored result.

        Returns:
            Last stored result or None
        """
        if self._last_key:
            return self._results.get(self._last_key)
        return None

    def list_results(self) -> list[str]:
        """List all stored result keys.

        Returns:
            List of result identifiers
        """
        return list(self._results.keys())
