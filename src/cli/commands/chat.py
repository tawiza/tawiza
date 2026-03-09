"""
Chat command for conversational AI assistant

Provides an interactive chat interface in the CLI with:
- Real-time streaming responses
- Persistent conversation history
- Automatic project context
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.text import Text

# Mascot integration
from src.cli.ui.mascot_hooks import (
    AnimatedMascot,
    chat_response_mascot,
    chat_welcome_mascot,
    mini_mascot,
)
from src.cli.ui.theme import (
    SUNSET_THEME,
    get_sunset_banner,
)

app = typer.Typer(help="Chat with the Tawiza AI assistant")
console = Console()

# History directory
HISTORY_DIR = Path.home() / ".tawiza" / "chat_history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


# Session state
current_session_id: str | None = None


def _save_message(session_id: str, role: str, content: str):
    """Save message to persistent history."""
    history_file = HISTORY_DIR / f"{session_id}.json"

    history = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text())
        except json.JSONDecodeError:
            history = []

    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })

    history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False))


def _load_history(session_id: str, limit: int = 10) -> list[dict]:
    """Load conversation history from file."""
    history_file = HISTORY_DIR / f"{session_id}.json"

    if not history_file.exists():
        return []

    try:
        history = json.loads(history_file.read_text())
        return history[-limit:] if limit else history
    except json.JSONDecodeError:
        return []


def _get_project_context() -> str:
    """Get automatic project context from current directory."""
    context_parts = []
    cwd = Path.cwd()

    # Check for README
    for readme_name in ["README.md", "readme.md", "README.txt", "README"]:
        readme_path = cwd / readme_name
        if readme_path.exists():
            content = readme_path.read_text()[:2000]
            context_parts.append(f"# Project README:\n{content}")
            break

    # Check for pyproject.toml or package.json
    if (cwd / "pyproject.toml").exists():
        content = (cwd / "pyproject.toml").read_text()[:1000]
        context_parts.append(f"# pyproject.toml:\n{content}")
    elif (cwd / "package.json").exists():
        content = (cwd / "package.json").read_text()[:1000]
        context_parts.append(f"# package.json:\n{content}")

    # List key files
    key_patterns = ["*.py", "*.ts", "*.js", "*.go", "*.rs"]
    key_files = []
    for pattern in key_patterns:
        key_files.extend(list(cwd.glob(f"src/**/{pattern}"))[:5])

    if key_files:
        file_list = "\n".join([f"  - {f.relative_to(cwd)}" for f in key_files[:10]])
        context_parts.append(f"# Key project files:\n{file_list}")

    return "\n\n".join(context_parts) if context_parts else ""


def _list_sessions() -> list[dict]:
    """List all saved sessions."""
    sessions = []
    for history_file in HISTORY_DIR.glob("*.json"):
        try:
            history = json.loads(history_file.read_text())
            if history:
                sessions.append({
                    "id": history_file.stem,
                    "messages": len(history),
                    "last_activity": history[-1].get("timestamp", "unknown")
                })
        except (json.JSONDecodeError, IndexError):
            pass

    return sorted(sessions, key=lambda x: x.get("last_activity", ""), reverse=True)


@app.command()
def start(
    model: str = typer.Option(
        "mistral:latest",
        "--model",
        "-m",
        help="LLM model to use for chat"
    ),
    session: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Resume existing session ID"
    ),
    rag: bool = typer.Option(
        False,
        "--rag",
        help="Enable RAG (Retrieval-Augmented Generation) for knowledge-enhanced responses"
    ),
    show_metadata: bool = typer.Option(
        False,
        "--show-metadata",
        help="Show response metadata (model, timing, etc.)"
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Enable/disable real-time streaming of responses"
    ),
    context: bool = typer.Option(
        True,
        "--context/--no-context",
        help="Include automatic project context"
    )
):
    """
    Start an interactive chat session with the AI assistant

    The assistant can help you with:
    - Understanding Tawiza commands
    - Model management and fine-tuning
    - Troubleshooting issues
    - Best practices and guidance

    Examples:
        # Start a chat session
        tawiza chat start

        # Use a specific model
        tawiza chat start --model mistral:latest

        # Enable RAG for knowledge-enhanced responses
        tawiza chat start --rag

        # Resume an existing session
        tawiza chat start --session abc-123-def
    """
    global current_session_id

    # Welcome message
    console.print()
    console.print(Panel.fit(
        "[bold cyan]Tawiza AI Assistant[/bold cyan]\n\n"
        "Ask me anything about the Tawiza platform!\n"
        "Type [bold]'help'[/bold] for guidance, [bold]'exit'[/bold] to quit.",
        border_style="cyan"
    ))
    console.print()

    # Initialize session
    if session:
        current_session_id = session
        console.print(f"[dim]Resuming session: {session}[/dim]\n")
    else:
        current_session_id = str(uuid.uuid4())
        console.print(f"[dim]New session: {current_session_id}[/dim]\n")

    # Run chat loop
    asyncio.run(_chat_loop(
        session_id=current_session_id,
        model=model,
        use_rag=rag,
        show_metadata=show_metadata,
        use_stream=stream,
        use_context=context
    ))


async def _chat_loop(
    session_id: str,
    model: str,
    use_rag: bool,
    show_metadata: bool,
    use_stream: bool = True,
    use_context: bool = True
):
    """Main chat loop with streaming and persistent history."""

    from src.infrastructure.config.settings import get_settings
    from src.infrastructure.llm.ollama_client import OllamaClient

    settings = get_settings()

    # Initialize Ollama client
    console.print(Panel(
        "[dim]Initializing AI assistant...[/dim]",
        border_style=SUNSET_THEME.accent_color,
        padding=(0, 1)
    ))

    try:
        ollama = OllamaClient(
            base_url=settings.ollama.base_url,
            model=model
        )

        # Health check
        if not await ollama.health_check():
            console.print(f"[yellow]Warning: Model '{model}' may not be available[/yellow]")

        console.print(f"[green]✓[/green] Assistant ready! (model: {model})")

        # Display GPU status
        from src.cli.ui.gpu_monitor import get_gpu_status
        gpu_status = get_gpu_status()
        if gpu_status.available:
            location = "Host" if gpu_status.location.value == "host" else "VM 400"
            console.print(f"[dim]🎮 GPU: {location} | {gpu_status.memory_percent:.0f}% mémoire[/dim]")

        # Get project context if enabled
        project_context = ""
        if use_context:
            project_context = _get_project_context()
            if project_context:
                console.print("[green]✓[/green] Project context loaded")

        # Load previous history if resuming
        history = _load_history(session_id, limit=10)
        if history:
            console.print(f"[green]✓[/green] Loaded {len(history)} previous messages")

        console.print()

        # Welcome mascot
        chat_welcome_mascot(console)

    except Exception as e:
        console.print(f"[red]Error initializing assistant: {e}[/red]")
        console.print("\nPlease check that:")
        console.print("  1. Ollama is running (http://localhost:11434)")
        console.print(f"  2. Model '{model}' is available (tawiza models list)")
        return

    # Build messages for context
    messages = []

    # System prompt with optional project context
    system_prompt = """You are Tawiza AI Assistant, an expert in the Tawiza platform.
You help users with:
- CLI commands and usage
- Model management and fine-tuning
- Browser automation with Playwright/Skyvern
- GPU optimization (AMD ROCm)
- Troubleshooting and best practices

Be concise, helpful, and provide code examples when relevant."""

    if project_context:
        system_prompt += f"\n\n# Current Project Context:\n{project_context}"

    messages.append({"role": "system", "content": system_prompt})

    # Add history
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Chat loop
    while True:
        try:
            # Get user input
            user_input = Prompt.ask(f"\n[bold {SUNSET_THEME.accent_color}]You[/bold {SUNSET_THEME.accent_color}]")

            # Check for exit
            if user_input.lower().strip() in ["exit", "quit", "bye", "q"]:
                console.print("\n[cyan]Assistant:[/cyan] Goodbye! Feel free to come back anytime.")
                console.print(f"\n[dim]Session saved: {session_id}[/dim]")
                console.print(f"[dim]Resume with: tawiza chat start --session {session_id}[/dim]\n")
                break

            # Check for special commands
            if user_input.lower().strip() == "/clear":
                messages = [messages[0]]  # Keep only system prompt
                console.print("[yellow]Context cleared[/yellow]")
                continue

            if user_input.lower().strip() == "/context":
                console.print("\n[dim]Project context:[/dim]")
                console.print(project_context if project_context else "[yellow]No context loaded[/yellow]")
                continue

            # Add user message
            messages.append({"role": "user", "content": user_input})
            _save_message(session_id, "user", user_input)

            # Display assistant header with mascot
            mascot_anim = AnimatedMascot(console)
            console.print(f"\n{mini_mascot('working')} [cyan]Assistant:[/cyan]")

            # Get response with streaming or sync
            if use_stream:
                # Streaming response with animated mascot
                full_response = ""
                stream_gen = await ollama.chat(messages=messages, stream=True)

                # Use Live for real-time display with mascot
                response_text = Text()
                with Live(response_text, console=console, refresh_per_second=15, transient=False) as live:
                    async for chunk in stream_gen:
                        if chunk:
                            full_response += chunk
                            # Animated mascot prefix during streaming
                            mascot_frame = mascot_anim.get_streaming_frame()
                            response_text = Text(f"{mascot_frame}\n{full_response}")
                            live.update(response_text)

                # Final render without mascot animation
                console.print()  # New line after streaming

                # Reaction mascot based on content
                if "```" in full_response:
                    chat_response_mascot("code", console)
                elif "error" in full_response.lower() or "erreur" in full_response.lower():
                    chat_response_mascot("error", console)
                else:
                    chat_response_mascot("success", console)

            else:
                # Non-streaming response with thinking mascot
                thinking_text = f"{mini_mascot('working')} Réflexion..."
                with Live(Spinner("dots", text=thinking_text), console=console, transient=True):
                    full_response = await ollama.chat(messages=messages, stream=False)

                console.print(Markdown(full_response))
                chat_response_mascot("success", console)

            # Save assistant response
            messages.append({"role": "assistant", "content": full_response})
            _save_message(session_id, "assistant", full_response)

            # Show metadata if requested
            if show_metadata:
                console.print(f"\n[dim]Model: {model} | Messages: {len(messages)} | Stream: {use_stream}[/dim]")

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Chat interrupted.[/yellow]")
            console.print(f"\n[dim]Session saved: {session_id}[/dim]")
            console.print(f"[dim]Resume with: tawiza chat start --session {session_id}[/dim]\n")
            break

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            console.print("[dim]Please try again or type 'exit' to quit.[/dim]")

    # Cleanup
    await ollama.close()


@app.command()
def history(
    session: str = typer.Argument(..., help="Session ID to view"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of messages to show")
):
    """
    View conversation history for a session

    Examples:
        # View last 10 messages
        tawiza chat history abc-123-def

        # View last 20 messages
        tawiza chat history abc-123-def --limit 20
    """
    history_data = _load_history(session, limit=limit)

    if not history_data:
        console.print(f"[yellow]No history found for session: {session}[/yellow]")
        console.print(f"[dim]History files are stored in: {HISTORY_DIR}[/dim]")
        return

    console.print(f"\n[bold]Conversation History[/bold] (last {len(history_data)} messages)\n")

    for msg in history_data:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")[:19].replace("T", " ")

        if role == "user":
            console.print(f"[bold {SUNSET_THEME.accent_color}]You[/bold {SUNSET_THEME.accent_color}] [dim]({timestamp})[/dim]")
        else:
            console.print(f"[cyan]Assistant[/cyan] [dim]({timestamp})[/dim]")

        # Truncate long messages
        if len(content) > 500:
            content = content[:500] + "..."
        console.print(f"{content}\n")


@app.command()
def sessions():
    """
    List saved chat sessions

    Examples:
        tawiza chat sessions
    """
    saved_sessions = _list_sessions()

    if not saved_sessions:
        console.print("[yellow]No saved sessions[/yellow]")
        console.print("[dim]Start a new session with: tawiza chat start[/dim]")
        return

    from rich.table import Table

    table = Table(
        title="Saved Chat Sessions",
        border_style=SUNSET_THEME.accent_color,
        show_header=True
    )
    table.add_column("Session ID", style="cyan")
    table.add_column("Messages", justify="right")
    table.add_column("Last Activity")

    for session in saved_sessions[:20]:  # Limit to 20 sessions
        last_activity = session.get("last_activity", "")[:19].replace("T", " ")
        table.add_row(
            session["id"][:36] + "..." if len(session["id"]) > 36 else session["id"],
            str(session["messages"]),
            last_activity
        )

    console.print()
    console.print(table)
    console.print("\n[dim]Resume with: tawiza chat start --session <SESSION_ID>[/dim]")


@app.command()
def clear(
    session: str = typer.Argument(..., help="Session ID to clear"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """
    Clear a chat session

    Examples:
        # Clear with confirmation
        tawiza chat clear abc-123-def

        # Force clear without confirmation
        tawiza chat clear abc-123-def --force
    """
    history_file = HISTORY_DIR / f"{session}.json"

    if not history_file.exists():
        console.print(f"[yellow]Session not found: {session}[/yellow]")
        return

    if not force:
        confirm = Prompt.ask(
            f"Are you sure you want to clear session {session}?",
            choices=["y", "n"],
            default="n"
        )
        if confirm != "y":
            console.print("[yellow]Cancelled[/yellow]")
            return

    try:
        history_file.unlink()
        console.print(f"[green]✓[/green] Session cleared: {session}")
    except Exception as e:
        console.print(f"[red]Error clearing session: {e}[/red]")


@app.command()
def export(
    session: str = typer.Argument(..., help="Session ID to export"),
    output: str = typer.Option(
        "conversation.json",
        "--output",
        "-o",
        help="Output file path"
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json, markdown, txt"
    )
):
    """
    Export conversation to file

    Examples:
        # Export to default file
        tawiza chat export abc-123-def

        # Export to specific file
        tawiza chat export abc-123-def --output my-chat.json

        # Export as markdown
        tawiza chat export abc-123-def --format markdown --output chat.md
    """
    history_data = _load_history(session, limit=0)  # Get all messages

    if not history_data:
        console.print(f"[yellow]No history found for session: {session}[/yellow]")
        return

    try:
        output_path = Path(output)

        if format.lower() == "json":
            output_path.write_text(json.dumps(history_data, indent=2, ensure_ascii=False))

        elif format.lower() == "markdown":
            lines = [f"# Chat Session: {session}\n"]
            for msg in history_data:
                role = "**You**" if msg.get("role") == "user" else "**Assistant**"
                timestamp = msg.get("timestamp", "")[:19].replace("T", " ")
                lines.append(f"\n## {role} ({timestamp})\n")
                lines.append(msg.get("content", "") + "\n")
            output_path.write_text("\n".join(lines))

        else:  # txt
            lines = []
            for msg in history_data:
                role = "You" if msg.get("role") == "user" else "Assistant"
                lines.append(f"[{role}]")
                lines.append(msg.get("content", ""))
                lines.append("")
            output_path.write_text("\n".join(lines))

        console.print(f"[green]✓[/green] Conversation exported to: {output}")
        console.print(f"[dim]Format: {format}, Messages: {len(history_data)}[/dim]")

    except Exception as e:
        console.print(f"[red]Error exporting conversation: {e}[/red]")


@app.command()
def suggest(
    query: str = typer.Argument(..., help="Natural language query")
):
    """
    Get command suggestion from natural language

    Examples:
        tawiza chat suggest "show me all models"
        tawiza chat suggest "start training a model"
        tawiza chat suggest "check system health"
    """
    from src.application.services.assistant_service import get_assistant

    assistant = get_assistant()
    suggestion = asyncio.run(assistant.suggest_command(query))

    if suggestion:
        console.print(get_sunset_banner("\n[bold]Suggested command:[/bold]"))
        console.print(f"[green]{suggestion}[/green]\n")
        console.print(get_sunset_banner("[dim]Run this command with:[/dim]"))
        console.print(f"[dim]$ {suggestion}[/dim]\n")
    else:
        console.print(f"[yellow]Could not parse command from: {query}[/yellow]")
        console.print(get_sunset_banner("[dim]Try being more specific or use 'tawiza chat start' for interactive help[/dim]"))


if __name__ == "__main__":
    app()
