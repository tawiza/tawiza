"""Completion installation and management commands."""

import os
import subprocess

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from ..ui import ColorGradient, Icons, TextStyling, icon

console = Console()
app = typer.Typer(help="Shell completion management")


def detect_shell() -> str:
    """Detect the user's shell."""
    shell = os.environ.get("SHELL", "")
    if "bash" in shell:
        return "bash"
    elif "zsh" in shell:
        return "zsh"
    elif "fish" in shell:
        return "fish"
    return "unknown"


@app.command()
def install(shell: str = typer.Option(None, "--shell", "-s", help="Shell type (bash, zsh, fish)")):
    """
    🚀 Install shell completion for Tawiza CLI.

    Auto-detects your shell if not specified.

    Examples:
        tawiza completion install
        tawiza completion install --shell bash
        tawiza completion install --shell zsh
    """
    # Header
    header = ColorGradient.create_gradient("Shell Completion Installer", "#00D9FF", "#7B68EE")
    console.print()
    console.print(header, justify="center")
    console.print("=" * 70, style="dim cyan")
    console.print()

    # Detect shell if not provided
    if not shell:
        shell = detect_shell()
        console.print(f"[cyan]Detected shell:[/cyan] [bold]{shell}[/bold]\n")

    if shell == "unknown":
        console.print("[red]❌ Could not detect shell automatically.[/red]")
        console.print("[yellow]Please specify shell with --shell option[/yellow]")
        console.print("[dim]Supported: bash, zsh, fish[/dim]\n")
        raise typer.Exit(1)

    # Install completion
    console.print(f"[cyan]Installing completion for {shell}...[/cyan]\n")

    try:
        # Run the install-completion command
        result = subprocess.run(
            ["tawiza", "--install-completion", shell], capture_output=True, text=True
        )

        if result.returncode == 0:
            console.print(f"[green]✅ Completion installed for {shell}![/green]\n")

            # Show instructions
            table = Table(title=f"{shell.upper()} Setup", border_style="green")
            table.add_column("Step", style="cyan", width=8)
            table.add_column("Action", style="white")

            if shell == "bash":
                table.add_row("1", "Completion added to ~/.bashrc")
                table.add_row("2", "Run: source ~/.bashrc")
                table.add_row("3", "Or restart your terminal")
            elif shell == "zsh":
                table.add_row("1", "Completion added to ~/.zshrc")
                table.add_row("2", "Run: source ~/.zshrc")
                table.add_row("3", "Or restart your terminal")
            elif shell == "fish":
                table.add_row("1", "Completion added to ~/.config/fish/completions/")
                table.add_row("2", "Restart your terminal")

            console.print(table)
            console.print()

            # Show test command
            badge = TextStyling.create_badge("Test with: tawiza <TAB>", color="green", symbol="✨")
            console.print(badge, justify="center")
            console.print()

        else:
            console.print(f"[red]❌ Installation failed: {result.stderr}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def show(shell: str = typer.Option(None, "--shell", "-s", help="Shell type (bash, zsh, fish)")):
    """
    📄 Show completion script for manual installation.

    Examples:
        tawiza completion show
        tawiza completion show --shell bash
    """
    if not shell:
        shell = detect_shell()

    if shell == "unknown":
        console.print("[red]❌ Could not detect shell. Please specify with --shell[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Completion script for {shell}:[/bold cyan]\n")

    try:
        result = subprocess.run(
            ["tawiza", "--show-completion", shell], capture_output=True, text=True
        )

        if result.returncode == 0:
            syntax = Syntax(result.stdout, shell, theme="monokai", line_numbers=False)
            console.print(syntax)
            console.print()
        else:
            console.print(f"[red]❌ Error: {result.stderr}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status():
    """
    ℹ️  Show completion installation status.

    Examples:
        tawiza completion status
    """
    shell = detect_shell()

    # Header
    header = ColorGradient.create_gradient("Completion Status", "#FF6B6B", "#4ECDC4")
    console.print()
    console.print(header, justify="center")
    console.print("=" * 70, style="dim cyan")
    console.print()

    # System info
    table = Table(show_header=False, border_style="cyan", box=None)
    table.add_column("Property", style="dim cyan", width=25)
    table.add_column("Value", style="bold green")

    table.add_row(icon(Icons.SYSTEM, "Detected Shell"), shell)
    table.add_row(icon(Icons.INFO, "Shell Path"), os.environ.get("SHELL", "unknown"))

    # Check completion files
    home = os.path.expanduser("~")
    completion_files = {
        "bash": f"{home}/.bashrc",
        "zsh": f"{home}/.zshrc",
        "fish": f"{home}/.config/fish/completions/tawiza.fish",
    }

    completion_file = completion_files.get(shell)
    if completion_file and os.path.exists(completion_file):
        # Check if tawiza completion is in the file
        try:
            with open(completion_file) as f:
                content = f.read()
                if "tawiza" in content:
                    table.add_row(icon(Icons.SUCCESS, "Status"), "[green]Installed ✅[/green]")
                else:
                    table.add_row(icon(Icons.WARNING, "Status"), "[yellow]Not installed[/yellow]")
        except Exception:
            table.add_row(icon(Icons.ERROR, "Status"), "[red]Unknown[/red]")
    else:
        table.add_row(icon(Icons.WARNING, "Status"), "[yellow]Not installed[/yellow]")

    console.print(table)
    console.print()

    # Installation tip
    console.print(
        "[dim]💡 Tip: Run [bold]tawiza completion install[/bold] to enable tab completion[/dim]\n"
    )


@app.command()
def guide():
    """
    📖 Show complete guide for shell completion.

    Examples:
        tawiza completion guide
    """
    # Header
    header = ColorGradient.rainbow_gradient("✨ Shell Completion Guide ✨")
    console.print()
    console.print(header, justify="center")
    console.print()

    guide_text = """[bold cyan]What is Shell Completion?[/bold cyan]

Shell completion allows you to press [bold]TAB[/bold] to auto-complete commands, options,
and arguments in your terminal.

[bold cyan]Quick Installation:[/bold cyan]

    [green]tawiza completion install[/green]

[bold cyan]Features:[/bold cyan]

  • Auto-complete commands: [dim]tawiza mo<TAB> → models[/dim]
  • Auto-complete options: [dim]tawiza models --<TAB> → --help, --format, etc.[/dim]
  • Context-aware suggestions
  • File path completion

[bold cyan]Supported Shells:[/bold cyan]

  • Bash (Linux/macOS/WSL)
  • Zsh (macOS default)
  • Fish (Modern shell)

[bold cyan]Manual Installation:[/bold cyan]

    [dim]# View the completion script[/dim]
    [green]tawiza completion show[/green]

    [dim]# Or use Typer's built-in command[/dim]
    [green]tawiza --install-completion[/green]

[bold cyan]Testing:[/bold cyan]

After installation, restart your terminal and try:
    [green]tawiza <TAB><TAB>[/green]

[bold cyan]Troubleshooting:[/bold cyan]

If completion doesn't work:
  1. Check installation: [green]tawiza completion status[/green]
  2. Reload shell config: [green]source ~/.bashrc[/green] (or ~/.zshrc)
  3. Restart terminal
"""

    panel = Panel(guide_text, border_style="cyan", padding=(1, 2))
    console.print(panel)
    console.print()


if __name__ == "__main__":
    app()
