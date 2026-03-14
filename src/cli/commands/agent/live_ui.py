"""Live UI components for autonomous agent CLI.

Provides Rich-based live displays for:
- Plan approval interface
- Step-by-step execution progress
- Real-time status updates
"""

import asyncio
import contextlib
from collections.abc import Callable
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from src.cli.ui.mascot_hooks import (
    AnimatedMascot,
    mascot_says,
)
from src.cli.ui.theme import get_sunset_banner
from src.infrastructure.agents.autonomous.execution_state import PlanStatus
from src.infrastructure.agents.autonomous.step_executor import StepResult
from src.infrastructure.agents.autonomous.task_planner import PlannedStep, TaskPlan

# Status indicators
STATUS_ICONS = {
    "pending": "[dim]○[/dim]",
    "in_progress": "[yellow]●[/yellow]",
    "completed": "[green]✓[/green]",
    "failed": "[red]✗[/red]",
    "skipped": "[dim]⊘[/dim]",
}

# Action icons
ACTION_ICONS = {
    "navigate": "[cyan]🌐[/cyan]",
    "extract": "[magenta]📊[/magenta]",
    "fill_form": "[yellow]📝[/yellow]",
    "click": "[green]👆[/green]",
    "scroll": "[blue]↕[/blue]",
    "wait": "[dim]⏳[/dim]",
    "screenshot": "[cyan]📷[/cyan]",
}


class AgentLiveUI:
    """Live UI for autonomous agent execution.

    Provides:
    - Plan approval interface
    - Real-time step progress
    - Status panels with mascot
    """

    def __init__(self, console: Console):
        """Initialize live UI.

        Args:
            console: Rich console instance
        """
        self.console = console
        self.mascot = AnimatedMascot(console)

        # Track step statuses
        self.step_statuses: dict[str, str] = {}
        self.current_step_id: str | None = None
        self.step_results: dict[str, StepResult] = {}

    def create_layout(self) -> Layout:
        """Create Rich layout for agent display.

        Returns:
            Layout with header, main (left/right), and footer
        """
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=4),
        )

        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=3),
        )

        return layout

    def render_header(self, task: str, plan_id: str, dry_run: bool = False) -> Panel:
        """Render header panel.

        Args:
            task: Task description
            plan_id: Plan ID
            dry_run: Dry run mode

        Returns:
            Header Panel
        """
        header_text = Text()
        header_text.append("🤖 ", style="bold")
        header_text.append("AUTONOMOUS AGENT ", style="bold cyan")

        if dry_run:
            header_text.append("[DRY-RUN] ", style="bold yellow")

        header_text.append(f"| Plan: {plan_id}", style="dim")

        return Panel(
            header_text,
            title="Tawiza Agent",
            border_style="cyan",
        )

    def render_plan_table(
        self,
        plan: TaskPlan,
        step_statuses: dict[str, str] | None = None,
    ) -> Table:
        """Render plan steps as table.

        Args:
            plan: Task plan
            step_statuses: Optional status overrides

        Returns:
            Rich Table
        """
        statuses = step_statuses or self.step_statuses

        table = Table(
            title="Execution Plan",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
        )

        table.add_column("", width=3)  # Status icon
        table.add_column("Step", width=8, style="cyan")
        table.add_column("Action", width=10)
        table.add_column("Description", ratio=1)
        table.add_column("Est.", width=5, justify="right")

        for step in plan.steps:
            status = statuses.get(step.step_id, "pending")
            icon = STATUS_ICONS.get(status, STATUS_ICONS["pending"])
            action_icon = ACTION_ICONS.get(step.action, "")

            # Highlight current step
            style = "bold yellow" if step.step_id == self.current_step_id else None

            table.add_row(
                icon,
                step.step_id,
                f"{action_icon} {step.action}",
                step.description[:50] + "..." if len(step.description) > 50 else step.description,
                f"{step.estimated_duration_seconds}s",
                style=style,
            )

        return table

    def render_step_details(
        self,
        step: PlannedStep | None,
        result: StepResult | None = None,
    ) -> Panel:
        """Render current step details panel.

        Args:
            step: Current step
            result: Step result if available

        Returns:
            Details Panel
        """
        if not step:
            return Panel(
                "[dim]Waiting for execution...[/dim]",
                title="Current Step",
                border_style="dim",
            )

        content = Text()

        # Step info
        action_icon = ACTION_ICONS.get(step.action, "")
        content.append(f"{action_icon} {step.action.upper()}\n", style="bold cyan")
        content.append(f"{step.description}\n\n", style="white")

        # Details
        if step.url:
            content.append("URL: ", style="dim")
            content.append(f"{step.url}\n", style="blue")

        if step.selector:
            content.append("Selector: ", style="dim")
            content.append(f"{step.selector}\n", style="green")

        if step.data:
            content.append("Data: ", style="dim")
            content.append(f"{step.data}\n", style="yellow")

        # Result if available
        if result:
            content.append("\n")
            if result.is_success:
                content.append("✓ Completed ", style="bold green")
                content.append(f"({result.execution_time_seconds:.1f}s)\n", style="dim")

                if result.result_data:
                    # Show snippet of result
                    result_str = str(result.result_data)[:200]
                    content.append(f"Result: {result_str}...\n", style="dim")
            else:
                content.append("✗ Failed\n", style="bold red")
                content.append(f"Error: {result.error_message}\n", style="red")

        return Panel(
            content,
            title=f"Step: {step.step_id}",
            border_style="cyan" if not result else ("green" if result.is_success else "red"),
        )

    def render_footer(
        self,
        status: str,
        progress: int,
        total: int,
        elapsed: float,
    ) -> Panel:
        """Render footer with progress.

        Args:
            status: Current status message
            progress: Steps completed
            total: Total steps
            elapsed: Elapsed time in seconds

        Returns:
            Footer Panel
        """
        mascot_frame = self.mascot.get_working_frame()

        footer_text = Text()
        footer_text.append(f"{mascot_frame} ", style="bold")
        footer_text.append(f"Progress: {progress}/{total} steps ", style="cyan")
        footer_text.append(f"| {status} ", style="yellow")
        footer_text.append(f"| Elapsed: {elapsed:.1f}s", style="dim")

        return Panel(
            footer_text,
            border_style="cyan",
        )

    def show_plan_approval(
        self,
        plan: TaskPlan,
        auto_approve: bool = False,
    ) -> bool:
        """Display plan and get user approval.

        Args:
            plan: Plan to display
            auto_approve: Skip approval if True

        Returns:
            True if approved
        """
        self.console.print()
        self.console.print(get_sunset_banner(f"[bold cyan]Task:[/bold cyan] {plan.original_task}"))
        self.console.print()

        # Show plan table
        table = self.render_plan_table(plan)
        self.console.print(table)
        self.console.print()

        # Show summary
        total_time = sum(s.estimated_duration_seconds for s in plan.steps)
        self.console.print(
            f"[dim]Estimated duration: {total_time}s | "
            f"Confidence: {plan.confidence_score:.0%} | "
            f"Steps: {len(plan.steps)}[/dim]"
        )
        self.console.print()

        if auto_approve:
            mascot_says("Auto-approved! Let's go!", "happy")
            return True

        # Ask for approval
        try:
            response = (
                self.console.input("[bold yellow]Execute this plan? [Y/n/edit]: [/bold yellow]")
                .strip()
                .lower()
            )

            if response in ("", "y", "yes", "oui"):
                mascot_says("C'est parti!", "happy")
                return True
            elif response in ("n", "no", "non"):
                mascot_says("Plan cancelled.", "sad")
                return False
            elif response in ("e", "edit"):
                # TODO: Implement plan editing
                mascot_says("Edit mode not yet implemented. Running as-is.", "thinking")
                return True
            else:
                mascot_says("Invalid response, assuming no.", "confused")
                return False

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Cancelled by user[/yellow]")
            return False

    async def run_with_live_updates(
        self,
        plan: TaskPlan,
        execute_callback: Callable,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run execution with live UI updates.

        Args:
            plan: Plan to execute
            execute_callback: Async callback that executes the plan
            dry_run: Dry run mode

        Returns:
            Execution result
        """
        layout = self.create_layout()
        start_time = datetime.utcnow()
        current_step: PlannedStep | None = None
        current_result: StepResult | None = None
        status_message = "Initializing..."
        progress_count = 0

        # Initialize step statuses
        for step in plan.steps:
            self.step_statuses[step.step_id] = "pending"

        # Callbacks for the execution
        def on_step_start(step: PlannedStep):
            nonlocal current_step, status_message
            current_step = step
            self.current_step_id = step.step_id
            self.step_statuses[step.step_id] = "in_progress"
            status_message = f"Executing: {step.description[:40]}..."

        def on_step_complete(step: PlannedStep, result: StepResult):
            nonlocal current_result, progress_count, status_message
            current_result = result
            self.step_results[step.step_id] = result

            if result.is_success:
                self.step_statuses[step.step_id] = "completed"
                progress_count += 1
                status_message = f"Completed: {step.step_id}"
            else:
                self.step_statuses[step.step_id] = "failed"
                status_message = f"Failed: {step.step_id}"

        def on_error(step: PlannedStep, error: str):
            nonlocal status_message
            status_message = f"Error at {step.step_id}: {error[:30]}..."

        def on_progress(current: int, total: int, step: PlannedStep):
            nonlocal status_message
            status_message = f"Step {current}/{total}: {step.action}"

        # Run with live display
        with Live(layout, console=self.console, refresh_per_second=4):
            # Update task
            async def update_display():
                while True:
                    elapsed = (datetime.utcnow() - start_time).total_seconds()

                    # Update layout
                    layout["header"].update(
                        self.render_header(plan.original_task, plan.plan_id, dry_run)
                    )
                    layout["left"].update(self.render_plan_table(plan))
                    layout["right"].update(self.render_step_details(current_step, current_result))
                    layout["footer"].update(
                        self.render_footer(
                            status_message,
                            progress_count,
                            len(plan.steps),
                            elapsed,
                        )
                    )

                    await asyncio.sleep(0.25)

            # Start display updater
            display_task = asyncio.create_task(update_display())

            try:
                # Execute with callbacks
                result = await execute_callback(
                    plan=plan,
                    callbacks={
                        "on_step_start": on_step_start,
                        "on_step_complete": on_step_complete,
                        "on_error": on_error,
                        "on_progress": on_progress,
                    },
                    dry_run=dry_run,
                )

                # Final update
                (datetime.utcnow() - start_time).total_seconds()
                status = result.get("status", "completed")

                if status == PlanStatus.COMPLETED.value:
                    status_message = "✓ Execution completed successfully!"
                elif status == PlanStatus.FAILED.value:
                    status_message = "✗ Execution failed"
                elif status == PlanStatus.CANCELLED.value:
                    status_message = "⊘ Execution cancelled"

                # Let user see final state
                await asyncio.sleep(1.0)

                return result

            finally:
                display_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await display_task


def show_execution_summary(console: Console, result: dict[str, Any]):
    """Show execution summary after completion.

    Args:
        console: Rich console
        result: Execution result dict
    """
    console.print()

    status = result.get("status", "unknown")

    if status == PlanStatus.COMPLETED.value:
        style = "green"
        icon = "✓"
    elif status == PlanStatus.FAILED.value:
        style = "red"
        icon = "✗"
    else:
        style = "yellow"
        icon = "○"

    # Summary table
    table = Table(
        title=f"{icon} Execution Summary",
        border_style=style,
        show_header=False,
    )

    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("Plan ID", result.get("plan_id", "N/A"))
    table.add_row("Status", f"[{style}]{status}[/{style}]")
    table.add_row(
        "Steps", f"{result.get('steps_completed', 0)}/{result.get('steps_total', 0)} completed"
    )
    table.add_row("Duration", f"{result.get('duration_seconds', 0):.1f}s")

    if result.get("error"):
        table.add_row("Error", f"[red]{result['error']}[/red]")

    console.print(table)

    # Show extracted data if any
    extracted = result.get("extracted_data", {})
    if extracted:
        console.print()
        console.print("[cyan bold]Extracted Data:[/cyan bold]")

        import json

        json_str = json.dumps(extracted, indent=2, default=str)[:1000]
        syntax = Syntax(json_str, "json", theme="monokai")
        console.print(syntax)

    # Show screenshots if any
    screenshots = result.get("screenshots", [])
    if screenshots:
        console.print()
        console.print(f"[dim]Screenshots saved: {len(screenshots)} files[/dim]")
        for ss in screenshots[-3:]:  # Show last 3
            console.print(f"  [dim]• {ss}[/dim]")

    console.print()
