"""Command suggestion system for CLI typos and errors."""



def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate the Levenshtein distance between two strings.

    The Levenshtein distance is the minimum number of single-character edits
    (insertions, deletions, or substitutions) required to change one word into another.

    Args:
        s1: First string
        s2: Second string

    Returns:
        The Levenshtein distance as an integer
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def similarity_score(s1: str, s2: str) -> float:
    """
    Calculate similarity score between two strings (0.0 to 1.0).

    Args:
        s1: First string
        s2: Second string

    Returns:
        Similarity score where 1.0 is identical and 0.0 is completely different
    """
    distance = levenshtein_distance(s1.lower(), s2.lower())
    max_len = max(len(s1), len(s2))

    if max_len == 0:
        return 1.0

    return 1.0 - (distance / max_len)


def find_similar_command(
    typed_command: str,
    available_commands: list[str],
    threshold: float = 0.6,
    max_suggestions: int = 3
) -> list[tuple[str, float]]:
    """
    Find similar commands based on Levenshtein distance.

    Args:
        typed_command: The command the user typed
        available_commands: List of valid commands
        threshold: Minimum similarity score to consider (0.0 to 1.0)
        max_suggestions: Maximum number of suggestions to return

    Returns:
        List of tuples (command, similarity_score) sorted by similarity
    """
    suggestions = []

    for command in available_commands:
        score = similarity_score(typed_command, command)
        if score >= threshold:
            suggestions.append((command, score))

    # Sort by similarity score (highest first)
    suggestions.sort(key=lambda x: x[1], reverse=True)

    return suggestions[:max_suggestions]


def suggest_command(
    typed_command: str,
    available_commands: list[str],
    threshold: float = 0.6
) -> str | None:
    """
    Get a suggestion message for a mistyped command.

    Args:
        typed_command: The command the user typed
        available_commands: List of valid commands
        threshold: Minimum similarity score to consider

    Returns:
        Suggestion message or None if no good suggestions found
    """
    similar = find_similar_command(typed_command, available_commands, threshold)

    if not similar:
        return None

    if len(similar) == 1:
        command, score = similar[0]
        return f"Did you mean '[cyan]{command}[/cyan]'?"

    # Multiple suggestions
    commands = ", ".join([f"'[cyan]{cmd}[/cyan]'" for cmd, _ in similar])
    return f"Did you mean {commands}?"


# List of all main commands in Tawiza CLI
MAIN_COMMANDS = [
    "version",
    "system",
    "models",
    "train",
    "data",
    "browser",
    "live",
    "live-visual",
    "chat",
    "automate",
    "auto",
    "credentials",
    "captcha",
    "finetune",
    "annotate",
    "prompts",
]

# Common sub-commands
SYSTEM_COMMANDS = ["health", "status", "init", "info", "diagnose", "gpu", "services"]
MODEL_COMMANDS = ["list", "show", "delete", "versions", "compare", "ollama"]
PROMPT_COMMANDS = ["list", "show", "create", "render", "delete", "stats", "init-defaults"]
FINETUNE_COMMANDS = ["start", "status", "list", "watch", "models"]
ANNOTATE_COMMANDS = ["projects", "list", "export", "import"]


def get_subcommand_suggestions(main_command: str, typed_subcommand: str) -> str | None:
    """
    Get suggestions for subcommands based on the main command.

    Args:
        main_command: The main command (e.g., "system", "models")
        typed_subcommand: The subcommand the user typed

    Returns:
        Suggestion message or None
    """
    subcommand_map = {
        "system": SYSTEM_COMMANDS,
        "models": MODEL_COMMANDS,
        "prompts": PROMPT_COMMANDS,
        "finetune": FINETUNE_COMMANDS,
        "annotate": ANNOTATE_COMMANDS,
    }

    available_subcommands = subcommand_map.get(main_command, [])

    if not available_subcommands:
        return None

    return suggest_command(typed_subcommand, available_subcommands)
