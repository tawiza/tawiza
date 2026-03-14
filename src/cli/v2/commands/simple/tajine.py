"""TAJINE command - Run the strategic meta-agent with PPDSL cycle display."""

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.theme import footer, header
from src.infrastructure.agents.tajine import create_tajine_agent
from src.infrastructure.config.tajine_config import get_tajine_config

console = Console()

# Create Typer app for subcommands
app = typer.Typer(help="TAJINE strategic meta-agent for territorial intelligence")


@app.command("status")
def status_command() -> None:
    """Show TAJINE system status and configuration."""
    console.print(header("tajine system status", 60))
    console.print()

    # Get configuration
    config = get_tajine_config()

    # Display configuration
    table = Table(title="Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="dim")
    table.add_column("Value")

    table.add_row("Ollama Host", config.ollama_host)
    table.add_row("Ollama Model", config.ollama_model)
    table.add_row("Ollama Timeout", f"{config.ollama_timeout}s")
    table.add_row("Neo4j URI", config.neo4j_uri)
    table.add_row("Neo4j User", config.neo4j_user)
    table.add_row("Cache Path", config.sqlite_cache_path)
    table.add_row("Trust Path", config.trust_persistence_path)
    table.add_row("Log Level", config.log_level)

    console.print(table)
    console.print()

    # Check connectivity
    console.print("[bold]Connectivity Status:[/]")
    console.print()

    # Ollama check
    try:
        import httpx

        response = httpx.get(f"{config.ollama_host}/api/tags", timeout=5)
        if response.status_code == 200:
            console.print("  [green]✓[/] Ollama: Connected")
            models = response.json().get("models", [])
            if any(m.get("name", "").startswith(config.ollama_model.split(":")[0]) for m in models):
                console.print(f"    [green]✓[/] Model '{config.ollama_model}' available")
            else:
                console.print(f"    [yellow]![/] Model '{config.ollama_model}' not found")
        else:
            console.print(f"  [yellow]![/] Ollama: HTTP {response.status_code}")
    except Exception as e:
        console.print(f"  [red]✗[/] Ollama: Not reachable ({str(e)[:50]})")

    # Neo4j check (basic - just check if we can create URI)
    try:
        from neo4j import GraphDatabase

        console.print("  [green]✓[/] Neo4j: Client library available")
        console.print(f"    [dim]Configured URI: {config.neo4j_uri}[/]")
    except ImportError:
        console.print("  [yellow]![/] Neo4j: Client library not installed")

    console.print()
    console.print(footer(60))


@app.command("analyze")
def analyze_command(
    query: str = typer.Argument(None, help="Query for territorial intelligence analysis"),
    territory: str | None = typer.Option(
        None, "--territory", "-t", help="Territory code (e.g., 34, 75)"
    ),
    sector: str | None = typer.Option(
        None, "--sector", "-s", help="Sector (tech, biotech, commerce, industrie)"
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="LLM model for reasoning (overrides config)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    real_api: bool = typer.Option(
        False, "--real-api", help="Use real SIRENE API instead of simulation"
    ),
    output: str = typer.Option("./output", "--output", "-o", help="Output directory for results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output results as JSON"),
) -> None:
    """Run territorial intelligence analysis.

    TAJINE executes the PPDSL cycle:
    - Perceive: Analyze query intent and context
    - Plan: Decompose into executable subtasks
    - Delegate: Execute via ManusAgent or tool registry
    - Synthesize: Aggregate results through cognitive layers
    - Learn: Update trust metrics

    Examples:
        tawiza tajine analyze "Analyse tech sector in 34"
        tawiza tajine analyze "Compare enterprises in 75 vs 13" --verbose
        tawiza tajine analyze "Prospect biotech in Occitanie" --real-api
        tawiza tajine analyze --territory 34 --sector tech
    """
    if not query and not territory:
        console.print("[yellow]Provide a query or use --territory[/]")
        console.print('[dim]Example: tawiza tajine analyze "Analyse tech sector in 34"[/]')
        return

    # Build query from options if not provided
    if not query:
        parts = ["Analyse"]
        if sector:
            parts.append(f"sector {sector}")
        if territory:
            parts.append(f"in territory {territory}")
        query = " ".join(parts)

    # Get configuration
    config = get_tajine_config()

    # Use model from CLI option or config
    model_to_use = model or config.ollama_model

    asyncio.run(
        _run_tajine(
            query=query,
            territory=territory,
            sector=sector,
            model=model_to_use,
            verbose=verbose,
            real_api=real_api,
            output=output,
            json_output=json_output,
        )
    )


# Legacy function for backwards compatibility (if called directly from other code)
def tajine_command(
    query: str = typer.Argument(None, help="Query for territorial intelligence analysis"),
    territory: str | None = typer.Option(
        None, "--territory", "-t", help="Territory code (e.g., 34, 75)"
    ),
    sector: str | None = typer.Option(
        None, "--sector", "-s", help="Sector (tech, biotech, commerce, industrie)"
    ),
    model: str = typer.Option("qwen3.5:27b", "--model", "-m", help="LLM model for reasoning"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    real_api: bool = typer.Option(
        False, "--real-api", help="Use real SIRENE API instead of simulation"
    ),
    output: str = typer.Option("./output", "--output", "-o", help="Output directory for results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output results as JSON"),
) -> None:
    """Legacy wrapper for backwards compatibility - delegates to analyze_command."""
    analyze_command(query, territory, sector, model, verbose, real_api, output, json_output)


async def _run_tajine(
    query: str,
    territory: str | None,
    sector: str | None,
    model: str,
    verbose: bool,
    real_api: bool,
    output: str,
    json_output: bool,
):
    """Run TAJINE agent with animated progress display."""
    from src.infrastructure.agents.tajine.events import (
        TAJINECallback,
        TAJINEEvent,
    )

    msg = MessageBox()

    # Header
    if not json_output:
        console.print(header("tajine meta-agent", 50))
        console.print()
        console.print(f"  [bold]Query:[/] {query[:60]}{'...' if len(query) > 60 else ''}")
        if territory:
            console.print(f"  [dim]Territory:[/] {territory}")
        if sector:
            console.print(f"  [dim]Sector:[/] {sector}")
        console.print(f"  [dim]Model:[/] {model}")
        console.print(footer(50))
        console.print()

    # Get configuration
    config = get_tajine_config()

    # Create agent using factory function
    try:
        agent = create_tajine_agent(
            name="tajine_cli",
            local_model=model,
            powerful_model=model,
            ollama_host=config.ollama_host,
        )

        # Register event handler for progress display
        phase_state = {"current": "", "progress": 0, "message": ""}
        events_log = []

        def on_event(cb: TAJINECallback):
            """Handle TAJINE events for display."""
            phase_state["current"] = cb.phase or phase_state["current"]
            phase_state["progress"] = cb.progress
            phase_state["message"] = cb.message

            if verbose:
                events_log.append(cb)

        agent.on_event(on_event)

    except Exception as e:
        console.print(msg.error("Failed to create TAJINE agent", [str(e)]))
        return

    # Build task config
    task_config = {
        "prompt": query,
        "use_real_api": real_api,
    }

    # Run with progress display
    result = None

    if json_output:
        # Silent execution for JSON output
        result = await agent.execute_task(task_config)
    else:
        # Progress display
        phase_icons = {
            "perceive": "👁️",
            "plan": "📋",
            "delegate": "🔧",
            "synthesize": "🧠",
            "learn": "📚",
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("[cyan]PPDSL Cycle", total=100)

            # Custom event handler for progress bar
            def progress_handler(cb: TAJINECallback) -> None:
                """Update progress bar with PPDSL phase information."""
                icon = phase_icons.get(cb.phase, "⚙️")
                desc = f"[cyan]{icon} {cb.phase or 'starting'}[/]: {cb.message[:40]}"
                progress.update(task, completed=cb.progress, description=desc)

                if verbose and cb.event == TAJINEEvent.DELEGATE_TOOL:
                    tool = cb.data.get("tool", "unknown")
                    console.print(f"    [dim]🔧 Executing: {tool}[/]")

            agent.on_event(progress_handler)

            result = await agent.execute_task(task_config)

    # Display results
    if json_output:
        console.print(json.dumps(result, indent=2, default=str))
        return

    console.print()

    if result.get("status") == "completed":
        # Success panel
        confidence = result.get("confidence", 0)
        confidence_color = "green" if confidence > 0.7 else "yellow" if confidence > 0.4 else "red"

        console.print(
            Panel(
                _format_result(result),
                title="[bold green]Analysis Complete[/]",
                border_style="green",
            )
        )

        # Metadata table
        console.print()
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim")
        table.add_column("Value")

        table.add_row("Task ID", result.get("task_id", "unknown"))
        table.add_row("Confidence", f"[{confidence_color}]{confidence:.1%}[/]")
        table.add_row("Subtasks", str(result.get("metadata", {}).get("subtask_count", 0)))
        table.add_row("Trust Score", f"{result.get('metadata', {}).get('trust_score', 0):.2f}")

        if perception := result.get("metadata", {}).get("perception"):
            table.add_row("Intent", perception.get("intent", "unknown"))
            if perception.get("territory"):
                table.add_row("Territory", perception.get("territory"))
            if perception.get("sector"):
                table.add_row("Sector", perception.get("sector"))

        console.print(table)

        # Save result
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"tajine_{result.get('task_id', 'result')}.json"
        output_file.write_text(json.dumps(result, indent=2, default=str))
        console.print()
        console.print(f"  [dim]Full result saved to:[/] {output_file}")

        # Verbose event log
        if verbose and events_log:
            console.print()
            console.print("[bold]Event Log:[/]")
            for ev in events_log[-10:]:
                icon = phase_icons.get(ev.phase, "⚙️")
                console.print(f"  {icon} [{ev.phase or 'init'}] {ev.message[:60]}")

    else:
        # Error panel
        console.print(
            Panel(
                f"[red]{result.get('error', 'Unknown error')}[/]",
                title="[bold red]Task Failed[/]",
                border_style="red",
            )
        )


def _format_result(result: dict) -> str:
    """Format result analysis for display."""
    analysis = result.get("result", {})

    if isinstance(analysis, dict):
        lines = []

        # Summary
        if summary := analysis.get("summary"):
            lines.append(f"[bold]Summary:[/] {summary}")
            lines.append("")

        # Key findings
        if findings := analysis.get("findings"):
            lines.append("[bold]Findings:[/]")
            for finding in findings[:5]:
                if isinstance(finding, dict):
                    lines.append(f"  • {finding.get('title', finding)}")
                else:
                    lines.append(f"  • {finding}")
            lines.append("")

        # Recommendations
        if recommendations := analysis.get("recommendations"):
            lines.append("[bold]Recommendations:[/]")
            for rec in recommendations[:3]:
                lines.append(f"  → {rec}")

        # Cognitive levels
        if levels := result.get("cognitive_levels"):
            lines.append("")
            lines.append("[bold]Cognitive Analysis:[/]")
            for level, data in levels.items():
                if isinstance(data, dict) and data.get("summary"):
                    summary = data["summary"]
                    if isinstance(summary, str):
                        lines.append(f"  [{level}] {summary[:60]}...")
                    elif isinstance(summary, dict):
                        # Handle structured summaries (e.g., theoretical level)
                        strategy = summary.get("primary_strategy", "")
                        if strategy:
                            lines.append(f"  [{level}] Strategy: {strategy}")
                        else:
                            # Fallback: show first key-value pair
                            first_key = next(iter(summary.keys()), None)
                            if first_key:
                                lines.append(f"  [{level}] {first_key}: {summary[first_key]}")

        return "\n".join(lines) if lines else str(analysis)

    return str(analysis)[:500]
