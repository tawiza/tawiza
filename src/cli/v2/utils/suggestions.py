"""Smart suggestions for Tawiza CLI v2."""

from dataclasses import dataclass

from rich.console import Console

from src.cli.v2.ui.theme import THEME


@dataclass
class Suggestion:
    """A command suggestion."""

    command: str
    description: str
    priority: int = 0  # Higher = more relevant


# Command flow graph - what comes after what
COMMAND_FLOWS: dict[str, list[Suggestion]] = {
    # After status
    "status": [
        Suggestion("tawiza chat", "Start chatting with AI", 10),
        Suggestion("tawiza run analyst", "Run data analysis agent", 8),
        Suggestion("tawiza pro doctor", "Run system diagnostics", 5),
    ],
    # After chat
    "chat": [
        Suggestion("tawiza run coder", "Run coding agent on your idea", 10),
        Suggestion("tawiza pro model-list", "See available models", 5),
    ],
    # After run
    "run": [
        Suggestion("tawiza status", "Check system status", 8),
        Suggestion("tawiza pro logs-show", "View execution logs", 7),
    ],
    # After agent
    "agent": [
        Suggestion('tawiza agent "Another task"', "Run another autonomous task", 10),
        Suggestion("tawiza run analyst", "Run a specific agent", 8),
        Suggestion("tawiza pro logs-show", "View execution logs", 7),
    ],
    # After model operations
    "pro model-list": [
        Suggestion("tawiza pro model-pull <model>", "Download a new model", 10),
        Suggestion("tawiza chat -m <model>", "Chat with a specific model", 8),
    ],
    "pro model-pull": [
        Suggestion("tawiza pro model-list", "Verify model installed", 10),
        Suggestion("tawiza chat", "Start using the model", 8),
    ],
    # After GPU operations
    "pro gpu-info": [
        Suggestion("tawiza pro gpu-benchmark", "Run GPU benchmark", 10),
        Suggestion("tawiza pro gpu-passthrough-status", "Check passthrough config", 8),
    ],
    "pro gpu-passthrough-enable": [
        Suggestion("reboot", "Reboot to apply changes", 10),
        Suggestion("tawiza pro gpu-vm-list", "Check VM GPU assignments", 5),
    ],
    "pro gpu-passthrough-disable": [
        Suggestion("reboot", "Reboot to use GPU on host", 10),
    ],
    # After data operations
    "pro data-import": [
        Suggestion("tawiza pro data-list", "Verify import", 10),
        Suggestion("tawiza pro train-start", "Start training on data", 8),
    ],
    "pro data-list": [
        Suggestion("tawiza pro data-import <file>", "Import new dataset", 8),
        Suggestion("tawiza pro train-start", "Train on a dataset", 7),
    ],
    # After training
    "pro train-start": [
        Suggestion("tawiza pro train-status", "Monitor training progress", 10),
        Suggestion("tawiza pro gpu-monitor", "Watch GPU usage", 8),
    ],
    "pro train-status": [
        Suggestion("tawiza pro train-stop <id>", "Stop a running job", 5),
        Suggestion("tawiza pro logs-show", "View training logs", 7),
    ],
    # After config
    "pro config-show": [
        Suggestion("tawiza pro config-set <key> <value>", "Change a setting", 10),
        Suggestion("tawiza pro config-edit", "Interactive config editor", 8),
    ],
    "pro config-set": [
        Suggestion("tawiza pro config-show", "Verify changes", 10),
    ],
    # After system commands
    "pro doctor": [
        Suggestion("tawiza pro ollama-start", "Start Ollama if not running", 8),
        Suggestion("tawiza pro cache-clear", "Clear cache if issues", 5),
    ],
    "pro cache-clear": [
        Suggestion("tawiza status", "Verify system status", 8),
    ],
    # After ollama
    "pro ollama-start": [
        Suggestion("tawiza pro model-list", "Check available models", 10),
        Suggestion("tawiza chat", "Start chatting", 8),
    ],
    "pro ollama-stop": [
        Suggestion("tawiza pro ollama-start", "Restart Ollama", 5),
    ],
}

# Context-aware suggestions based on system state
CONTEXTUAL_SUGGESTIONS: dict[str, callable] = {}


def _check_ollama_running() -> bool:
    """Check if Ollama is running."""
    try:
        import httpx

        response = httpx.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def _check_gpu_available() -> bool:
    """Check if GPU is available on host."""
    try:
        import subprocess

        result = subprocess.run(["rocm-smi", "--showid"], capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def get_suggestions(last_command: str, context: dict = None) -> list[Suggestion]:
    """Get suggestions based on last command and context."""
    suggestions = []

    # Get flow-based suggestions
    if last_command in COMMAND_FLOWS:
        suggestions.extend(COMMAND_FLOWS[last_command])

    # Add contextual suggestions
    if not _check_ollama_running():
        suggestions.append(
            Suggestion("tawiza pro ollama-start", "Ollama not running - start it", priority=15)
        )

    # Sort by priority
    suggestions.sort(key=lambda s: s.priority, reverse=True)

    return suggestions[:3]  # Return top 3


def print_suggestions(last_command: str, console: Console = None):
    """Print suggestions after command execution."""
    if console is None:
        console = Console()

    suggestions = get_suggestions(last_command)

    if not suggestions:
        return

    console.print()
    console.print("  [dim]┌─ Next steps ─────────────────────────[/]")

    for i, s in enumerate(suggestions, 1):
        console.print(f"  [dim]│[/] [{THEME['accent']}]{i}.[/] {s.command}")
        console.print(f"  [dim]│[/]    [dim]{s.description}[/]")

    console.print("  [dim]└──────────────────────────────────────[/]")


# Command examples for help text
COMMAND_EXAMPLES: dict[str, list[str]] = {
    "chat": [
        "tawiza chat                     # Interactive chat",
        "tawiza chat 'Hello!'            # Quick message",
        "tawiza chat -m llama3:8b        # Use specific model",
    ],
    "run": [
        "tawiza run analyst              # Interactive agent selection",
        "tawiza run coder -t 'Fix bug'   # Run with task",
        "tawiza run ml -d data.csv       # Process data file",
    ],
    "agent": [
        "tawiza agent 'What time is it in Tokyo?'  # Simple task",
        "tawiza agent 'Analyze trends' -d data.csv # With data",
        "tawiza agent 'Scrape HN' -v               # Verbose mode",
    ],
    "status": [
        "tawiza status                   # Quick status",
        "tawiza status -v                # Detailed status",
    ],
    "pro model-list": [
        "tawiza pro model-list           # List all models",
    ],
    "pro model-pull": [
        "tawiza pro model-pull qwen3.5:27b # Pull recommended model",
        "tawiza pro model-pull llama3:70b # Pull large model",
    ],
    "pro gpu-info": [
        "tawiza pro gpu-info             # Basic GPU info",
        "tawiza pro gpu-info -v          # With IOMMU groups",
    ],
    "pro train-start": [
        "tawiza pro train-start qwen3.5:27b -d data.jsonl",
        "tawiza pro train-start llama3:8b -d train.csv -e 5",
    ],
    "pro config-set": [
        "tawiza pro config-set model qwen3:30b",
        "tawiza pro config-set timeout 120",
    ],
    "pro data-import": [
        "tawiza pro data-import data.csv",
        "tawiza pro data-import train.jsonl -n my-dataset",
    ],
}


def get_examples(command: str) -> list[str]:
    """Get examples for a command."""
    return COMMAND_EXAMPLES.get(command, [])


def format_examples(command: str) -> str:
    """Format examples for display in help."""
    examples = get_examples(command)
    if not examples:
        return ""

    lines = ["\n[bold]Examples:[/]"]
    for ex in examples:
        lines.append(f"  [dim]{ex}[/]")

    return "\n".join(lines)
