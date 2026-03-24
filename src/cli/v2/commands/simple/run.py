"""Run command - Execute agents and tasks."""

import asyncio
import json

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table

from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.theme import THEME, footer, header

console = Console()

# Available agents - synced with AgentExecutor
AGENTS = {
    "analyst": "Data analysis and insights",
    "coder": "Code generation and review",
    "browser": "Web automation and scraping",
    "ml": "Machine learning tasks",
}


def run_command(
    agent: str | None = typer.Argument(None, help="Agent to run"),
    task: str | None = typer.Option(None, "--task", "-t", help="Task description"),
    data: str | None = typer.Option(None, "--data", "-d", help="Input data file"),
    url: str | None = typer.Option(None, "--url", "-u", help="Starting URL (browser agent)"),
    model: str = typer.Option("qwen3.5:27b", "--model", "-m", help="Ollama model to use"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive"),
    output_json: bool = typer.Option(False, "--json", help="Output result as JSON"),
):
    """Run an AI agent with specified task."""
    console.print(header("tawiza run", 40))
    console.print()

    # If no agent specified, show interactive selection
    if not agent:
        if interactive:
            agent = _select_agent()
        else:
            _show_available_agents()
            console.print(footer(40))
            return

    if agent not in AGENTS:
        msg = MessageBox()
        console.print(
            msg.error(f"Unknown agent: {agent}", [f"Available: {', '.join(AGENTS.keys())}"])
        )
        return

    # If no task, prompt for it
    if not task and interactive:
        task = Prompt.ask(f"  [{THEME['accent']}]Task[/]")

    if not task:
        console.print("  [dim]No task specified[/]")
        console.print(footer(40))
        return

    # Run the agent
    result = asyncio.run(
        _run_agent_async(
            agent=agent,
            task=task,
            data=data,
            url=url,
            model=model,
            output_json=output_json,
        )
    )

    if result and output_json:
        console.print_json(data=result)

    console.print(footer(40))


def _select_agent() -> str:
    """Interactive agent selection."""
    console.print("  [bold]Select an agent:[/]")
    console.print()

    for i, (name, desc) in enumerate(AGENTS.items(), 1):
        console.print(f"    [{THEME['accent']}]{i}[/] {name:<10} [dim]{desc}[/]")

    console.print()
    choice = Prompt.ask(
        "  Choice", choices=[str(i) for i in range(1, len(AGENTS) + 1)] + list(AGENTS.keys())
    )

    if choice.isdigit():
        return list(AGENTS.keys())[int(choice) - 1]
    return choice


def _show_available_agents() -> None:
    """Show available agents without interaction."""
    console.print("  [bold]Available agents:[/]")
    console.print()
    for name, desc in AGENTS.items():
        console.print(f"    {name:<10} [dim]{desc}[/]")
    console.print()
    console.print('  [dim]Usage: tawiza run <agent> --task "description"[/]')


async def _run_agent_async(
    agent: str,
    task: str,
    data: str | None,
    url: str | None,
    model: str,
    output_json: bool,
) -> dict | None:
    """Execute the specified agent asynchronously."""
    from src.cli.v2.agents.executor import AgentExecutor

    console.print(f"  [bold]Agent:[/] {agent}")
    console.print(f"  [bold]Task:[/] {task[:60]}{'...' if len(task) > 60 else ''}")
    if data:
        console.print(f"  [bold]Data:[/] {data}")
    if url:
        console.print(f"  [bold]URL:[/] {url}")
    console.print(f"  [bold]Model:[/] {model}")
    console.print()

    # Create executor
    executor = AgentExecutor(model=model)

    # Show spinner while running
    with console.status(f"[bold {THEME['accent']}]Running {agent} agent...[/]", spinner="dots"):
        result = await executor.run(
            agent_name=agent,
            task=task,
            data=data,
            url=url,
        )

    # Display result
    msg = MessageBox()

    if result.status == "success":
        console.print(
            msg.success(
                f"Task completed in {result.duration_seconds:.1f}s", f"Agent: {result.agent}"
            )
        )

        # Show result summary based on agent type
        if result.result:
            _display_result(agent, result.result, output_json)

        if output_json:
            return {
                "status": result.status,
                "agent": result.agent,
                "task": result.task,
                "duration_seconds": result.duration_seconds,
                "result": result.result,
            }

    else:
        console.print(msg.error("Task failed", [result.error or "Unknown error"]))

        # Show logs if available
        if result.logs:
            console.print()
            console.print("  [dim]Logs:[/]")
            for log in result.logs[-5:]:
                console.print(f"    [dim]{log}[/]")

        if output_json:
            return {
                "status": result.status,
                "agent": result.agent,
                "task": result.task,
                "error": result.error,
                "logs": result.logs,
            }

    return None


def _display_result(agent: str, result: dict, output_json: bool) -> None:
    """Display agent-specific result summary."""
    console.print()

    if agent == "analyst":
        _display_analyst_result(result)
    elif agent == "browser":
        _display_browser_result(result)
    elif agent == "coder":
        _display_coder_result(result)
    elif agent == "ml":
        _display_ml_result(result)


def _display_analyst_result(result: dict) -> None:
    """Display data analysis result."""
    summary = result.get("summary", {})

    console.print("  [bold]Analysis Summary:[/]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="dim")
    table.add_column("Value", style=THEME["accent"])

    table.add_row("Rows", str(summary.get("rows", "N/A")))
    table.add_row("Columns", str(summary.get("columns", "N/A")))
    table.add_row("Quality Score", f"{summary.get('quality_score', 0):.1f}/100")
    table.add_row("Anomalies", str(summary.get("anomalies_count", 0)))
    table.add_row("Recommendations", str(summary.get("recommendations_count", 0)))

    console.print(table)

    # Show recommendations
    report = result.get("report", {})
    recommendations = report.get("recommendations", [])
    if recommendations:
        console.print()
        console.print("  [bold]Recommendations:[/]")
        for i, rec in enumerate(recommendations[:5], 1):
            console.print(f"    {i}. {rec}")


def _display_browser_result(result: dict) -> None:
    """Display browser automation result."""
    console.print("  [bold]Browser Task Result:[/]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="dim")
    table.add_column("Value")

    table.add_row("Task ID", result.get("task_id", "N/A"))
    table.add_row("Status", f"[{THEME['success']}]{result.get('status', 'N/A')}[/]")

    console.print(table)

    # Show extracted data if available
    extracted = result.get("result", {})
    if extracted and isinstance(extracted, dict):
        console.print()
        console.print("  [bold]Extracted Data:[/]")
        json_str = json.dumps(extracted, indent=2, ensure_ascii=False)
        if len(json_str) > 500:
            json_str = json_str[:500] + "\n  ..."
        syntax = Syntax(json_str, "json", theme="monokai")
        console.print(syntax)


def _display_coder_result(result: dict) -> None:
    """Display code generation result."""
    console.print("  [bold]Generated Code:[/]")

    # Show code preview
    code = result.get("code", "")
    if code:
        # Truncate for display
        lines = code.split("\n")
        if len(lines) > 30:
            code = "\n".join(lines[:30]) + "\n# ... (truncated)"

        syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
        console.print(syntax)

    # Show quality score
    quality = result.get("quality_score", 0)
    console.print()
    console.print(f"  [bold]Quality Score:[/] [{THEME['accent']}]{quality:.1f}/100[/]")

    # Show file structure
    file_structure = result.get("file_structure", {})
    if file_structure:
        console.print()
        console.print("  [bold]Files Created:[/]")
        for filename in list(file_structure.keys())[:5]:
            console.print(f"    - {filename}")


def _display_ml_result(result: dict) -> None:
    """Display ML pipeline result."""
    console.print("  [bold]ML Pipeline Result:[/]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="dim")
    table.add_column("Value", style=THEME["accent"])

    table.add_row("Model Type", result.get("model_type", "N/A"))
    table.add_row("Best Score", f"{result.get('best_score', 0):.4f}")
    table.add_row("Training Time", f"{result.get('training_time', 0):.1f}s")
    table.add_row("Model Size", f"{result.get('model_size_mb', 0):.2f} MB")

    console.print(table)

    # Show best parameters
    best_params = result.get("best_params", {})
    if best_params:
        console.print()
        console.print("  [bold]Best Parameters:[/]")
        for key, value in list(best_params.items())[:5]:
            console.print(f"    {key}: {value}")

    # Show test scores
    test_scores = result.get("test_scores", {})
    if test_scores:
        console.print()
        console.print("  [bold]Test Scores:[/]")
        for metric, score in test_scores.items():
            console.print(f"    {metric}: {score:.4f}")
