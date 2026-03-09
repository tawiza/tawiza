"""Helper utilities for CLI.

Modules:
- suggestions: Command suggestions and fuzzy matching
- ux_helpers: UX enhancements (fuzzy finder, progress, notifications, clipboard)
"""

from .suggestions import find_similar_command, suggest_command
from .ux_helpers import (
    alert_attention,
    # Progress
    animated_progress,
    # Terminal
    beep,
    # Clipboard
    copy_to_clipboard,
    fuzzy_match,
    # Fuzzy finding
    fuzzy_select,
    # Utils
    get_available_features,
    iterate_with_progress,
    notify_completion,
    # Notifications
    notify_desktop,
    output_with_copy_option,
    paste_from_clipboard,
    print_features_status,
    # Async
    run_with_notification,
    # Files
    select_file,
)

__all__ = [
    # Suggestions
    "find_similar_command",
    "suggest_command",
    # Fuzzy
    "fuzzy_select",
    "fuzzy_match",
    # Progress
    "animated_progress",
    "iterate_with_progress",
    # Notifications
    "notify_desktop",
    "notify_completion",
    # Clipboard
    "copy_to_clipboard",
    "paste_from_clipboard",
    "output_with_copy_option",
    # Terminal
    "beep",
    "alert_attention",
    # Files
    "select_file",
    # Async
    "run_with_notification",
    # Utils
    "get_available_features",
    "print_features_status",
]
