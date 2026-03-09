"""Unified Adaptive Agent CLI commands.

Provides commands for the self-improving UAA:
- status: Show agent status (autonomy level, trust score)
- execute: Execute a task through the agent
- approve: Approve a pending task
- reject: Reject a pending task
- feedback: Record feedback for learning
- stats: Show detailed statistics
- learn: Trigger learning cycle
- config: View/modify configuration
- pending: List pending tasks
"""

import uuid

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.cli.utils.async_runner import run_async

console = Console()
app = typer.Typer(
    name="uaa",
    help="Unified Adaptive Agent - Self-improving multi-tool agent",
    no_args_is_help=True,
)

# Global agent instance (singleton pattern)
_agent_instance = None


def get_agent():
    """Get or create the global agent instance."""
    global _agent_instance
    if _agent_instance is None:
        from src.infrastructure.agents.unified import UnifiedAdaptiveAgent
        _agent_instance = UnifiedAdaptiveAgent()
    return _agent_instance


def _format_autonomy_level(level: str, value: int) -> str:
    """Format autonomy level with color."""
    colors = {
        "SUPERVISED": "red",
        "ASSISTED": "yellow",
        "SEMI_AUTONOMOUS": "blue",
        "AUTONOMOUS": "green",
        "FULL_AUTONOMOUS": "bright_green",
    }
    color = colors.get(level, "white")
    return f"[{color}]{level}[/{color}] ({value}/4)"


def _format_trust_score(score: float) -> str:
    """Format trust score with color based on value."""
    if score >= 0.8:
        color = "bright_green"
    elif score >= 0.6:
        color = "green"
    elif score >= 0.4:
        color = "yellow"
    elif score >= 0.2:
        color = "orange1"
    else:
        color = "red"
    percentage = int(score * 100)
    return f"[{color}]{percentage}%[/{color}]"


@app.command("status")
def status():
    """Show agent status (autonomy level, trust score, etc)."""
    agent = get_agent()
    status_data = agent.get_status()

    table = Table(title="UAA Status", box=None, show_header=False)
    table.add_column("Property", style="bold cyan")
    table.add_column("Value")

    table.add_row(
        "Autonomy Level",
        _format_autonomy_level(
            status_data["autonomy_level"],
            status_data.get("autonomy_level_value", 0),
        ),
    )
    table.add_row("Trust Score", _format_trust_score(status_data["trust_score"]))
    table.add_row(
        "Learning",
        "[green]Enabled[/green]" if status_data["learning_enabled"] else "[dim]Disabled[/dim]",
    )
    table.add_row(
        "Pending Tasks",
        f"[yellow]{status_data['pending_tasks']}[/yellow]" if status_data["pending_tasks"] > 0 else "0",
    )
    table.add_row(
        "Cooldown",
        "[red]Yes[/red]" if status_data.get("in_cooldown") else "[green]No[/green]",
    )

    console.print(Panel(table, border_style="blue"))


@app.command("execute")
def execute(
    task: str = typer.Argument(..., help="Natural language task description"),
    task_type: str | None = typer.Option(
        None, "--type", "-t", help="Task type for routing (e.g., web_scraping, code_execution)"
    ),
    context: str | None = typer.Option(
        None, "--context", "-c", help="Additional context as JSON"
    ),
    priority: int = typer.Option(0, "--priority", "-p", help="Task priority (higher = more urgent)"),
):
    """Execute a task through the agent."""
    import json

    from src.infrastructure.agents.unified import TaskRequest, TaskStatus

    agent = get_agent()
    task_id = str(uuid.uuid4())[:8]

    # Parse context if provided
    ctx = {}
    if context:
        try:
            ctx = json.loads(context)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON in context[/red]")
            raise typer.Exit(1)

    request = TaskRequest(
        task_id=task_id,
        description=task,
        task_type=task_type,
        context=ctx,
        priority=priority,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Executing task...", total=None)
        result = run_async(agent.execute(request))

    # Display result
    if result.status == TaskStatus.AWAITING_APPROVAL:
        console.print(Panel(
            f"[yellow]Task requires approval[/yellow]\n\n"
            f"Task ID: [bold]{result.task_id}[/bold]\n"
            f"Use [cyan]tawiza uaa approve {result.task_id}[/cyan] to approve\n"
            f"Use [cyan]tawiza uaa reject {result.task_id}[/cyan] to reject",
            title="Awaiting Approval",
            border_style="yellow",
        ))
    elif result.status == TaskStatus.COMPLETED:
        output_str = str(result.output) if result.output else "No output"
        console.print(Panel(
            f"[green]Task completed successfully[/green]\n\n"
            f"Task ID: [bold]{result.task_id}[/bold]\n"
            f"Tool Used: {result.tool_used or 'N/A'}\n"
            f"Execution Time: {result.execution_time:.2f}s\n\n"
            f"Output: {output_str[:200]}{'...' if len(output_str) > 200 else ''}",
            title="Completed",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red]Task failed[/red]\n\n"
            f"Task ID: [bold]{result.task_id}[/bold]\n"
            f"Error: {result.error or 'Unknown error'}",
            title="Failed",
            border_style="red",
        ))


@app.command("approve")
def approve(
    task_id: str = typer.Argument(..., help="Task ID to approve"),
):
    """Approve a pending task."""
    from src.infrastructure.agents.unified import TaskStatus

    agent = get_agent()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Approving and executing task...", total=None)
        result = run_async(agent.approve(task_id))

    if result.status == TaskStatus.COMPLETED:
        console.print(f"[green]Task {task_id} approved and completed successfully[/green]")
    elif result.status == TaskStatus.FAILED:
        if "not found" in (result.error or "").lower():
            console.print(f"[red]Task {task_id} not found in pending tasks[/red]")
        else:
            console.print(f"[red]Task {task_id} failed: {result.error}[/red]")


@app.command("reject")
def reject(
    task_id: str = typer.Argument(..., help="Task ID to reject"),
    reason: str = typer.Option("", "--reason", "-r", help="Rejection reason"),
):
    """Reject a pending task."""
    agent = get_agent()

    result = run_async(agent.reject(task_id, reason))

    if "not found" in (result.error or "").lower():
        console.print(f"[red]Task {task_id} not found in pending tasks[/red]")
    else:
        console.print(f"[yellow]Task {task_id} rejected[/yellow]")
        if reason:
            console.print(f"Reason: {reason}")


@app.command("feedback")
def feedback(
    task_id: str = typer.Argument(..., help="Task ID to provide feedback for"),
    feedback_type: str = typer.Argument(..., help="Feedback type: positive or negative"),
    correction: str | None = typer.Option(
        None, "--correction", "-c", help="Corrected output (for negative feedback)"
    ),
):
    """Record feedback for a task (affects trust score)."""
    if feedback_type not in ("positive", "negative"):
        console.print("[red]Feedback must be 'positive' or 'negative'[/red]")
        raise typer.Exit(1)

    agent = get_agent()
    agent.record_feedback(
        task_id=task_id,
        feedback=feedback_type,
        correction=correction,
    )

    if feedback_type == "positive":
        console.print(f"[green]Recorded positive feedback for {task_id}[/green]")
        console.print(f"Trust score: {_format_trust_score(agent.trust_score)}")
    else:
        console.print(f"[yellow]Recorded negative feedback for {task_id}[/yellow]")
        if correction:
            console.print("Correction saved for learning")
        console.print(f"Trust score: {_format_trust_score(agent.trust_score)}")


@app.command("stats")
def stats():
    """Show detailed agent statistics."""
    agent = get_agent()
    stats_data = agent.get_stats()

    # Task stats table
    task_table = Table(title="Task Statistics", box=None)
    task_table.add_column("Metric", style="bold")
    task_table.add_column("Value", justify="right")

    task_table.add_row("Completed", f"[green]{stats_data['tasks_completed']}[/green]")
    task_table.add_row("Failed", f"[red]{stats_data['tasks_failed']}[/red]")
    task_table.add_row("Pending", f"[yellow]{stats_data['tasks_pending']}[/yellow]")
    task_table.add_row(
        "Success Rate",
        f"{stats_data['success_rate']*100:.1f}%",
    )

    console.print(Panel(task_table, border_style="blue"))

    # Trust stats
    trust_stats = stats_data.get("trust_stats", {})
    trust_table = Table(title="Trust Statistics", box=None)
    trust_table.add_column("Metric", style="bold")
    trust_table.add_column("Value", justify="right")

    trust_table.add_row("Score", _format_trust_score(trust_stats.get("score", 0)))
    trust_table.add_row("Level", trust_stats.get("level", "UNKNOWN"))

    console.print(Panel(trust_table, border_style="cyan"))

    # Learning stats
    learning_stats = stats_data.get("learning_stats", {})
    learning_table = Table(title="Learning Statistics", box=None)
    learning_table.add_column("Metric", style="bold")
    learning_table.add_column("Value", justify="right")

    learning_table.add_row(
        "Examples Collected",
        str(learning_stats.get("examples_collected", 0)),
    )
    learning_table.add_row(
        "Cycles Completed",
        str(learning_stats.get("cycles_completed", 0)),
    )

    console.print(Panel(learning_table, border_style="magenta"))


@app.command("learn")
def learn(
    force: bool = typer.Option(False, "--force", "-f", help="Force learning even if not ready"),
):
    """Trigger a learning cycle."""
    agent = get_agent()

    if not agent.learning_engine.should_trigger_learning() and not force:
        stats = agent.learning_engine.get_stats()
        console.print(Panel(
            f"[yellow]Not ready for learning[/yellow]\n\n"
            f"Examples collected: {stats.get('examples_collected', 0)}\n"
            f"Minimum required: {stats.get('min_examples', 50)}\n\n"
            f"Use --force to trigger anyway",
            title="Learning Status",
            border_style="yellow",
        ))
        return

    console.print("[cyan]Starting learning cycle...[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Running learning cycle...", total=None)
        try:
            cycle = run_async(agent.learning_engine.run_full_cycle())

            if cycle:
                console.print(Panel(
                    f"[green]Learning cycle completed[/green]\n\n"
                    f"State: {cycle.state}\n"
                    f"Accuracy before: {cycle.metrics.accuracy_before:.1%}\n"
                    f"Accuracy after: {cycle.metrics.accuracy_after:.1%}\n"
                    f"Improvement: {cycle.metrics.accuracy_improvement:.1%}",
                    title="Learning Complete",
                    border_style="green",
                ))
            else:
                console.print("[yellow]Learning cycle returned no results[/yellow]")
        except Exception as e:
            console.print(f"[red]Learning failed: {e}[/red]")


@app.command("config")
def config(
    set_level: str | None = typer.Option(
        None, "--set-level", help="Set autonomy level (SUPERVISED, ASSISTED, SEMI_AUTONOMOUS, AUTONOMOUS, FULL_AUTONOMOUS)"
    ),
    enable_learning: bool | None = typer.Option(None, "--learning/--no-learning", help="Enable/disable auto-learning"),
):
    """View or modify agent configuration."""
    from src.infrastructure.agents.unified import AutonomyLevel

    agent = get_agent()

    # Apply changes if requested
    if set_level:
        try:
            level = AutonomyLevel[set_level.upper()]
            agent.trust_manager._level = level
            console.print(f"[green]Autonomy level set to {level.name}[/green]")
        except KeyError:
            valid = ", ".join(l.name for l in AutonomyLevel)
            console.print(f"[red]Invalid level. Valid options: {valid}[/red]")
            raise typer.Exit(1)

    if enable_learning is not None:
        agent.config.learning.auto_learning_enabled = enable_learning
        state = "enabled" if enable_learning else "disabled"
        console.print(f"[green]Auto-learning {state}[/green]")

    # Show current config
    table = Table(title="Agent Configuration", box=None)
    table.add_column("Setting", style="bold")
    table.add_column("Value")

    table.add_row("LLM Model", agent.config.llm_model)
    table.add_row("Max Concurrent", str(agent.config.max_concurrent_tasks))
    table.add_row("Default Timeout", f"{agent.config.default_timeout}s")

    console.print(Panel(table, border_style="blue", title="General"))

    # Trust config
    trust_table = Table(box=None)
    trust_table.add_column("Setting", style="bold")
    trust_table.add_column("Value")

    trust_table.add_row("Metric Weight", f"{agent.config.trust.metric_weight:.0%}")
    trust_table.add_row("Feedback Weight", f"{agent.config.trust.feedback_weight:.0%}")
    trust_table.add_row("History Weight", f"{agent.config.trust.history_weight:.0%}")
    trust_table.add_row("Error Cooldown", f"{agent.config.trust.error_cooldown}s")

    console.print(Panel(trust_table, border_style="cyan", title="Trust"))

    # Learning config
    learning_table = Table(box=None)
    learning_table.add_column("Setting", style="bold")
    learning_table.add_column("Value")

    learning_table.add_row(
        "Auto Learning",
        "[green]Enabled[/green]" if agent.config.learning.auto_learning_enabled else "[dim]Disabled[/dim]",
    )
    learning_table.add_row("Min Examples", str(agent.config.learning.min_examples_for_training))
    learning_table.add_row("Fine-tune Threshold", f"{agent.config.learning.finetune_threshold:.0%}")

    console.print(Panel(learning_table, border_style="magenta", title="Learning"))


@app.command("pending")
def pending():
    """List pending tasks awaiting approval."""
    agent = get_agent()
    pending_tasks = agent._pending_tasks

    if not pending_tasks:
        console.print("[dim]No pending tasks[/dim]")
        return

    table = Table(title="Pending Tasks", box=None)
    table.add_column("Task ID", style="bold cyan")
    table.add_column("Description")
    table.add_column("Type")
    table.add_column("Priority")
    table.add_column("Created")

    for task_id, request in pending_tasks.items():
        table.add_row(
            task_id,
            request.description[:50] + "..." if len(request.description) > 50 else request.description,
            request.task_type or "N/A",
            str(request.priority),
            request.created_at.strftime("%H:%M:%S"),
        )

    console.print(table)
    console.print("\nUse [cyan]tawiza uaa approve <task_id>[/cyan] or [cyan]tawiza uaa reject <task_id>[/cyan]")
