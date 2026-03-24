"""Autonomous agent CLI commands.

Provides commands for LLM-guided browser automation:
- run: Execute autonomous task with AI planning
- plan: Generate and show execution plan
- status: Show execution status
- cancel: Cancel running task
- resume: Resume paused task
"""

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.commands.agent.live_ui import AgentLiveUI, show_execution_summary
from src.cli.ui.mascot_hooks import mascot_says, on_long_task_end, show_agent_mascot
from src.cli.ui.theme import get_sunset_banner
from src.cli.utils.async_runner import run_async

console = Console()
app = typer.Typer(
    name="agent",
    help="Autonomous browser automation agent with AI planning",
    no_args_is_help=True,
)


def _get_service(model: str, headless: bool):
    """Get or create autonomous agent service."""
    from src.application.services.autonomous_agent_service import (
        create_autonomous_agent_service,
    )

    return run_async(create_autonomous_agent_service(model=model, headless=headless))


@app.command("run")
def run_task(
    task: str = typer.Argument(..., help="Natural language task description"),
    url: str | None = typer.Option(None, "--url", "-u", help="Starting URL (optional)"),
    model: str = typer.Option("qwen3-coder:30b", "--model", "-m", help="LLM model for planning"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Run browser in headless mode"),
    auto_approve: bool = typer.Option(False, "--auto", "-a", help="Skip plan approval"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Simulate execution without browser"
    ),
    max_steps: int = typer.Option(20, "--max-steps", help="Maximum steps allowed"),
    timeout: int = typer.Option(300, "--timeout", "-t", help="Total timeout in seconds"),
    output: str | None = typer.Option(None, "--output", "-o", help="Save results to JSON file"),
):
    """Execute autonomous browser task with AI planning.

    The agent will:
    1. Analyze your task and create an execution plan
    2. Show you the plan for approval (unless --auto)
    3. Execute each step with real-time feedback
    4. Return extracted data and screenshots

    Examples:
        # Extract data from a website
        tawiza agent run "Go to news.ycombinator.com and get the top 5 articles"

        # Start from specific URL
        tawiza agent run "Find the pricing page" --url https://example.com

        # Dry-run to test the plan without browser
        tawiza agent run "Fill contact form" --url https://example.com/contact --dry-run

        # Auto-approve for scripting
        tawiza agent run "Extract product prices" --url https://shop.com --auto

        # Use different model
        tawiza agent run "Complex task" --model qwen3.5:27b
    """
    # Welcome
    if dry_run:
        show_agent_mascot("thinking", "Mode simulation activé!", console)
    else:
        show_agent_mascot("browser", "Agent autonome prêt!", console)

    console.print(
        get_sunset_banner(
            f"\n[bold cyan]🤖 Autonomous Agent[/bold cyan] "
            f"{'[yellow][DRY-RUN][/yellow]' if dry_run else ''}\n"
        )
    )

    try:
        # Create service
        service = _get_service(model=model, headless=headless)

        # Create UI
        ui = AgentLiveUI(console)

        async def execute():
            # Generate plan
            console.print("[cyan]Planning task...[/cyan]")

            plan = await service.plan_task(
                task=task,
                starting_url=url,
            )

            # Show plan and get approval
            approved = ui.show_plan_approval(plan, auto_approve=auto_approve)

            if not approved:
                return {"status": "cancelled", "message": "Plan not approved"}

            # Execute with live UI
            result = await ui.run_with_live_updates(
                plan=plan,
                execute_callback=service.execute_plan,
                dry_run=dry_run,
            )

            return result

        # Run
        result = run_async(execute())

        # Show summary
        show_execution_summary(console, result)

        # Save output if requested
        if output and result:
            with open(output, "w") as f:
                json.dump(result, f, indent=2, default=str)
            console.print(f"[dim]Results saved to: {output}[/dim]")

        # Exit code
        status = result.get("status", "unknown")
        if status == "completed":
            on_long_task_end("Agent task", success=True)
        elif status == "cancelled":
            pass  # User cancelled, no error
        else:
            on_long_task_end("Agent task", success=False)
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        raise typer.Exit(130)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("plan")
def show_plan(
    task: str = typer.Argument(..., help="Natural language task description"),
    url: str | None = typer.Option(None, "--url", "-u", help="Starting URL"),
    model: str = typer.Option("qwen3-coder:30b", "--model", "-m", help="LLM model for planning"),
    output: str | None = typer.Option(None, "--output", "-o", help="Save plan to JSON file"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON only"),
):
    """Generate and display execution plan without running.

    Useful for:
    - Previewing what the agent would do
    - Saving plans for later execution
    - Debugging task decomposition

    Examples:
        tawiza agent plan "Search for flights from Paris to Tokyo"
        tawiza agent plan "Book hotel" --url https://booking.com --output plan.json
    """
    if not json_output:
        show_agent_mascot("thinking", "Analyzing task...", console)

    try:
        service = _get_service(model=model, headless=True)

        async def generate_plan():
            return await service.plan_task(
                task=task,
                starting_url=url,
            )

        plan = run_async(generate_plan())

        if json_output:
            # JSON output only
            console.print_json(data=plan.to_dict())
        else:
            # Pretty display
            ui = AgentLiveUI(console)
            ui.show_plan_approval(plan, auto_approve=True)  # Just display, don't ask

        # Save if requested
        if output:
            with open(output, "w") as f:
                json.dump(plan.to_dict(), f, indent=2)

            if not json_output:
                console.print(f"[dim]Plan saved to: {output}[/dim]")

    except Exception as e:
        console.print(f"[red]Error generating plan: {e}[/red]")
        raise typer.Exit(1)


@app.command("status")
def show_status(
    plan_id: str | None = typer.Argument(None, help="Specific plan ID to check"),
    all_tasks: bool = typer.Option(False, "--all", "-a", help="Show all recent tasks"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of tasks to show"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show status of agent tasks.

    Without arguments, shows recent tasks.
    With plan_id, shows detailed status of that task.

    Examples:
        tawiza agent status                    # Recent tasks
        tawiza agent status plan-abc123        # Specific task
        tawiza agent status --all --limit 20   # More history
    """
    try:
        from src.infrastructure.agents.autonomous.execution_state import (
            ExecutionStateManager,
        )

        state_manager = ExecutionStateManager()

        async def get_status():
            if plan_id:
                # Get specific task status
                return await state_manager.get_execution_status(plan_id)
            else:
                # Get recent tasks
                records = await state_manager.get_recent_executions(limit=limit)
                return {"tasks": [r.to_dict() for r in records]}

        result = run_async(get_status())

        if not result:
            console.print(f"[yellow]No status found for: {plan_id}[/yellow]")
            return

        if json_output:
            console.print_json(data=result)
            return

        if plan_id:
            # Detailed status for single task
            _show_task_details(result)
        else:
            # Table of recent tasks
            _show_tasks_table(result.get("tasks", []))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def _show_task_details(status: dict):
    """Show detailed status of a single task."""
    console.print(
        Panel(
            f"[cyan]Plan ID:[/cyan] {status.get('plan_id', 'N/A')}\n"
            f"[cyan]Status:[/cyan] {status.get('status', 'unknown')}\n"
            f"[cyan]Active:[/cyan] {status.get('is_active', False)}",
            title="Task Status",
            border_style="cyan",
        )
    )

    if status.get("context"):
        ctx = status["context"]
        console.print("\n[bold]Context:[/bold]")
        console.print(f"  Steps completed: {len(ctx.get('completed_steps', []))}")
        console.print(f"  Steps failed: {len(ctx.get('failed_steps', []))}")
        console.print(f"  Current URL: {ctx.get('current_url', 'N/A')}")

    if status.get("record"):
        rec = status["record"]
        console.print("\n[bold]Execution Record:[/bold]")
        console.print(f"  Task: {rec.get('original_task', 'N/A')[:50]}...")
        console.print(f"  Duration: {rec.get('duration_seconds', 0):.1f}s")
        console.print(f"  Steps: {rec.get('steps_completed', 0)}/{rec.get('steps_total', 0)}")


def _show_tasks_table(tasks: list):
    """Show table of recent tasks."""
    if not tasks:
        console.print("[yellow]No recent tasks found[/yellow]")
        return

    table = Table(
        title="Recent Agent Tasks",
        border_style="cyan",
    )

    table.add_column("Plan ID", style="cyan")
    table.add_column("Task", max_width=40)
    table.add_column("Status")
    table.add_column("Steps")
    table.add_column("Duration")
    table.add_column("Started")

    for task in tasks:
        status = task.get("status", "unknown")
        if status == "completed":
            status_style = "[green]✓ completed[/green]"
        elif status == "failed":
            status_style = "[red]✗ failed[/red]"
        elif status == "executing":
            status_style = "[yellow]● running[/yellow]"
        else:
            status_style = f"[dim]{status}[/dim]"

        table.add_row(
            task.get("plan_id", "N/A")[:16],
            (
                task.get("original_task", "N/A")[:37] + "..."
                if len(task.get("original_task", "")) > 40
                else task.get("original_task", "N/A")
            ),
            status_style,
            f"{task.get('steps_completed', 0)}/{task.get('steps_total', 0)}",
            f"{task.get('duration_seconds', 0):.1f}s",
            task.get("started_at", "N/A")[:19],
        )

    console.print(table)


@app.command("cancel")
def cancel_task(
    plan_id: str = typer.Argument(..., help="Plan ID to cancel"),
):
    """Cancel a running agent task.

    Example:
        tawiza agent cancel plan-abc123
    """
    try:
        service = _get_service(model="qwen3-coder:30b", headless=True)

        cancelled = run_async(service.cancel_execution(plan_id))

        if cancelled:
            mascot_says(f"Task {plan_id} cancelled!", "neutral")
        else:
            console.print(f"[yellow]Could not cancel {plan_id} (not running?)[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("resume")
def resume_task(
    plan_id: str = typer.Argument(..., help="Plan ID to resume"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Resume in dry-run mode"),
):
    """Resume a paused or failed task from checkpoint.

    Example:
        tawiza agent resume plan-abc123
        tawiza agent resume plan-abc123 --dry-run
    """
    show_agent_mascot("thinking", f"Resuming {plan_id}...", console)

    try:
        service = _get_service(model="qwen3-coder:30b", headless=True)
        AgentLiveUI(console)

        async def do_resume():
            return await service.resume_execution(
                plan_id=plan_id,
                dry_run=dry_run,
            )

        result = run_async(do_resume())

        show_execution_summary(console, result)

    except ValueError as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
