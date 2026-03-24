"""Chat command - Interactive AI chat."""

import typer
from rich.console import Console

from src.cli.v2.ui.spinners import create_spinner
from src.cli.v2.ui.theme import THEME, footer, header

console = Console()


def chat_command(
    message: str | None = typer.Argument(None, help="Message to send"),
    model: str = typer.Option("qwen3.5:27b", "--model", "-m", help="Model to use"),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Interactive mode"
    ),
):
    """Chat with the AI assistant."""
    console.print(header("tawiza chat", 40))
    console.print()

    if message:
        # Single message mode
        _send_message(message, model)
    elif interactive:
        # Interactive loop
        _interactive_chat(model)
    else:
        console.print("  [dim]No message provided. Use --interactive for chat mode.[/]")

    console.print()
    console.print(footer(40))


def _send_message(message: str, model: str) -> None:
    """Send a single message and display response."""
    console.print(f"  [dim]You:[/] {message}")
    console.print()

    try:
        import httpx

        with create_spinner("Thinking...", "dots"):
            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": message, "stream": False},
                timeout=60.0,
            )

        if response.status_code == 200:
            data = response.json()
            reply = data.get("response", "No response")
            console.print(f"  [cyan]AI:[/] {reply}")
        else:
            console.print(f"  [red]●[/] Failed to get response (status {response.status_code})")

    except Exception as e:
        console.print(f"  [red]●[/] Error: {e}")
        console.print()
        console.print("  [dim]→ Is Ollama running? Try: tawiza pro ollama-start[/]")


def _interactive_chat(model: str) -> None:
    """Run interactive chat loop."""
    console.print(f"  [dim]Model: {model}[/]")
    console.print("  [dim]Type 'exit' or Ctrl+C to quit[/]")
    console.print()

    while True:
        try:
            message = console.input(f"  [{THEME['accent']}]You:[/] ")
            if message.lower() in ("exit", "quit", "q"):
                break
            if message.strip():
                _send_message(message, model)
                console.print()
        except (KeyboardInterrupt, EOFError):
            break

    console.print()
    console.print("  [dim]Goodbye![/]")
