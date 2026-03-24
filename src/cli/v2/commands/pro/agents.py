"""Advanced agents commands for Tawiza CLI v2 pro.

Provides CLI commands for managing and running the Manus and S3 agents,
as well as debugging and monitoring agent execution.
"""

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.spinners import WaveSpinner
from src.cli.v2.ui.theme import THEME, footer, header

console = Console()


def register(app: typer.Typer) -> None:
    """Register agent commands."""

    @app.command("agents")
    def list_agents(
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed info"),
    ):
        """List all available AI agents with their capabilities."""
        console.print(header("agents", 50))

        table = Table(show_header=True, header_style=f"bold {THEME['accent']}", expand=True)
        table.add_column("Agent", style="cyan bold", width=15)
        table.add_column("Description", style="white")
        table.add_column("Status", justify="center", width=10)
        if verbose:
            table.add_column("Capabilities", style="dim")

        agents = [
            (
                "manus",
                "Reasoning agent with think-execute loop",
                "ready",
                "Browser, Python, Bash, MCP tools, File ops",
            ),
            (
                "s3",
                "Hybrid browser + desktop automation",
                "ready",
                "Browser, Desktop GUI, Vision, VM sandbox",
            ),
            (
                "analyst",
                "Data analysis and insights",
                "ready",
                "Data processing, CSV/JSON, Statistics",
            ),
            (
                "coder",
                "Code generation and review",
                "ready",
                "Multi-language, Testing, Refactoring",
            ),
            (
                "browser",
                "Web automation and scraping",
                "ready",
                "Playwright, Scraping, Screenshots",
            ),
            ("ml", "Machine learning tasks", "ready", "Training, Inference, Model management"),
            (
                "research",
                "Deep research with multi-source",
                "ready",
                "Web search, Summarization, Citations",
            ),
            (
                "crawler",
                "Web crawling and extraction",
                "ready",
                "Recursive crawl, Structured extraction",
            ),
        ]

        for name, desc, status, caps in agents:
            status_color = THEME["success"] if status == "ready" else THEME["warning"]
            if verbose:
                table.add_row(name, desc, f"[{status_color}]{status}[/]", caps)
            else:
                table.add_row(name, desc, f"[{status_color}]{status}[/]")

        console.print(table)
        console.print()
        console.print("  [dim]Run an agent:[/] tawiza pro agent-run <name> --task <task>")
        console.print(footer(50))

    @app.command("agent-run")
    def run_agent(
        agent_name: str = typer.Argument(..., help="Agent name (manus, s3, analyst, etc.)"),
        task: str = typer.Option(..., "--task", "-t", help="Task description"),
        model: str = typer.Option("qwen3.5:27b", "--model", "-m", help="LLM model to use"),
        max_iterations: int = typer.Option(10, "--max-iter", help="Max reasoning iterations"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
        output: Path | None = typer.Option(None, "--output", "-o", help="Save result to file"),
        mode: str | None = typer.Option(
            None, "--mode", help="Agent mode (browser/desktop/hybrid for S3)"
        ),
    ):
        """Run an AI agent with a specific task."""
        console.print(header(f"run: {agent_name}", 50))

        # Show task info
        console.print(f"  [bold]Agent:[/] {agent_name}")
        console.print(f"  [bold]Task:[/] {task}")
        console.print(f"  [bold]Model:[/] {model}")
        console.print(f"  [bold]Max iterations:[/] {max_iterations}")
        if mode:
            console.print(f"  [bold]Mode:[/] {mode}")
        console.print()

        async def execute_agent():
            """Execute the selected agent."""
            if agent_name == "manus":
                import os

                from src.infrastructure.agents.manus import create_manus_agent

                # Get Ollama host from environment (defaults to GPU server)
                ollama_host = os.getenv(
                    "OLLAMA_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                )
                console.print(f"  [dim]Ollama host:[/] {ollama_host}")

                agent = await create_manus_agent(
                    model=model,
                    ollama_host=ollama_host,
                    max_iterations=max_iterations,
                )

                console.print("  [cyan]Starting Manus reasoning loop...[/]")
                result = await agent.execute_task({"prompt": task})
                return result

            elif agent_name == "s3":
                from src.infrastructure.agents.s3 import S3Mode, create_s3_agent

                agent_mode = None
                if mode:
                    mode_map = {
                        "browser": S3Mode.BROWSER,
                        "desktop": S3Mode.DESKTOP,
                        "hybrid": S3Mode.HYBRID,
                    }
                    agent_mode = mode_map.get(mode.lower())

                agent = await create_s3_agent(
                    max_iterations=max_iterations,
                )
                if agent_mode:
                    agent.default_mode = agent_mode

                console.print("  [cyan]Starting S3 hybrid agent...[/]")
                result = await agent.execute_task({"task": task})
                return result

            elif agent_name == "research":
                from src.infrastructure.agents.advanced import ResearchQuery, create_research_agent

                agent = await create_research_agent(model=model)
                query = ResearchQuery(
                    query=task,
                    max_sources=5,
                    include_citations=True,
                )
                console.print("  [cyan]Starting deep research...[/]")
                result = await agent.research(query)
                return result

            elif agent_name == "crawler":
                from src.infrastructure.agents.advanced import CrawlConfig, create_crawler

                config = CrawlConfig(
                    max_pages=10,
                    max_depth=2,
                )
                crawler = await create_crawler(config)
                console.print("  [cyan]Starting web crawler...[/]")
                result = await crawler.crawl(task)
                return result

            else:
                # Fallback to unified agent for other agent types
                from src.cli.v2.agents.unified import UnifiedAgent

                agent = UnifiedAgent(
                    model=model,
                    agent_type=agent_name,
                    max_steps=max_iterations,
                )
                console.print(f"  [cyan]Starting {agent_name} agent...[/]")
                result = await agent.execute(task)
                return result

        # Run with spinner
        WaveSpinner()

        try:
            with console.status("[cyan]Executing agent...", spinner="dots"):
                result = asyncio.get_event_loop().run_until_complete(execute_agent())

            # Display result
            console.print()
            msg = MessageBox()
            console.print(msg.success("Agent execution complete"))

            if verbose and isinstance(result, dict):
                console.print()
                console.print(
                    Panel(
                        json.dumps(result, indent=2, default=str),
                        title="Result",
                        border_style="green",
                    )
                )
            elif result:
                console.print()
                if hasattr(result, "summary"):
                    console.print(f"  [bold]Summary:[/] {result.summary}")
                elif isinstance(result, dict) and "result" in result:
                    console.print(f"  [bold]Result:[/] {result['result']}")
                else:
                    console.print(f"  [bold]Result:[/] {str(result)[:500]}")

            # Save to file if requested
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                with open(output, "w") as f:
                    if isinstance(result, dict):
                        json.dump(result, f, indent=2, default=str)
                    else:
                        f.write(str(result))
                console.print(f"\n  [dim]Result saved to: {output}[/]")

        except Exception as e:
            msg = MessageBox()
            console.print(
                msg.error(
                    f"Agent execution failed: {str(e)[:100]}",
                    ["Check agent configuration", "Verify model is available"],
                )
            )

        console.print(footer(50))

    @app.command("agent-debug")
    def debug_agent(
        task_id: str | None = typer.Argument(None, help="Task ID to debug"),
        agent_name: str | None = typer.Option(None, "--agent", "-a", help="Filter by agent"),
        show_trace: bool = typer.Option(False, "--trace", help="Show execution trace"),
        show_memory: bool = typer.Option(False, "--memory", help="Show agent memory"),
    ):
        """Debug agent execution with detailed trace information."""
        console.print(header("agent debugger", 50))

        if task_id:
            # Show specific task details
            console.print(f"  [bold]Task ID:[/] {task_id}")
            console.print()

            # Try to load task from storage
            tasks_file = Path.home() / ".tawiza" / "agent_tasks.json"
            if tasks_file.exists():
                try:
                    tasks = json.loads(tasks_file.read_text())
                    if task_id in tasks:
                        task_data = tasks[task_id]

                        # Task info table
                        table = Table(show_header=False, box=None)
                        table.add_column("Field", style="cyan")
                        table.add_column("Value", style="white")

                        table.add_row("Agent", task_data.get("agent", "unknown"))
                        table.add_row("Status", task_data.get("status", "unknown"))
                        table.add_row("Started", task_data.get("started_at", "N/A"))
                        table.add_row("Completed", task_data.get("completed_at", "N/A"))
                        table.add_row("Iterations", str(task_data.get("iterations", 0)))

                        console.print(table)

                        if show_trace and "trace" in task_data:
                            console.print()
                            console.print("  [bold]Execution Trace:[/]")
                            for i, step in enumerate(task_data["trace"], 1):
                                console.print(
                                    f"    {i}. [{step.get('type', 'action')}] {step.get('action', 'unknown')}"
                                )
                                if step.get("result"):
                                    console.print(f"       -> {str(step['result'])[:80]}")

                        if show_memory and "memory" in task_data:
                            console.print()
                            console.print("  [bold]Agent Memory:[/]")
                            console.print(
                                Panel(json.dumps(task_data["memory"], indent=2), border_style="dim")
                            )
                    else:
                        console.print(f"  [yellow]Task not found: {task_id}[/]")
                except Exception as e:
                    console.print(f"  [red]Error loading task: {e}[/]")
            else:
                console.print("  [dim]No task history available.[/]")
        else:
            # List recent tasks
            console.print("  [bold]Recent Agent Tasks:[/]")
            console.print()

            tasks_file = Path.home() / ".tawiza" / "agent_tasks.json"
            if tasks_file.exists():
                try:
                    tasks = json.loads(tasks_file.read_text())

                    # Filter by agent if specified
                    if agent_name:
                        tasks = {k: v for k, v in tasks.items() if v.get("agent") == agent_name}

                    if tasks:
                        table = Table(show_header=True, header_style=f"bold {THEME['accent']}")
                        table.add_column("Task ID", style="cyan")
                        table.add_column("Agent")
                        table.add_column("Status")
                        table.add_column("Iterations", justify="right")
                        table.add_column("Started")

                        for tid, data in list(tasks.items())[-10:]:  # Last 10
                            status_color = (
                                THEME["success"]
                                if data.get("status") == "completed"
                                else THEME["warning"]
                            )
                            table.add_row(
                                tid[:8] + "...",
                                data.get("agent", "unknown"),
                                f"[{status_color}]{data.get('status', 'unknown')}[/]",
                                str(data.get("iterations", 0)),
                                data.get("started_at", "N/A")[:16],
                            )

                        console.print(table)
                    else:
                        console.print("  [dim]No tasks found.[/]")
                except Exception as e:
                    console.print(f"  [red]Error: {e}[/]")
            else:
                console.print("  [dim]No task history. Run an agent first.[/]")

            console.print()
            console.print("  [dim]View task details:[/] tawiza pro agent-debug <task-id>")

        console.print(footer(50))

    @app.command("agent-config")
    def configure_agent(
        agent_name: str = typer.Argument(..., help="Agent to configure"),
        model: str | None = typer.Option(None, "--model", "-m", help="Set default model"),
        max_iterations: int | None = typer.Option(None, "--max-iter", help="Set max iterations"),
        ollama_host: str | None = typer.Option(None, "--ollama-host", help="Set Ollama host"),
        vm_host: str | None = typer.Option(
            None, "--vm-host", help="Set VM sandbox host (S3 agent)"
        ),
        show: bool = typer.Option(False, "--show", "-s", help="Show current config"),
    ):
        """Configure agent settings."""
        console.print(header(f"config: {agent_name}", 50))

        config_file = Path.home() / ".tawiza" / "agent_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing config
        config = json.loads(config_file.read_text()) if config_file.exists() else {}

        if agent_name not in config:
            config[agent_name] = {}

        if show:
            # Display current config
            agent_config = config.get(agent_name, {})
            if agent_config:
                table = Table(show_header=False, box=None)
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="green")

                for key, value in agent_config.items():
                    table.add_row(key, str(value))

                console.print(table)
            else:
                console.print("  [dim]No configuration set. Using defaults.[/]")
        else:
            # Update config
            updated = False

            if model:
                config[agent_name]["model"] = model
                console.print(f"  [green]Set model:[/] {model}")
                updated = True

            if max_iterations:
                config[agent_name]["max_iterations"] = max_iterations
                console.print(f"  [green]Set max_iterations:[/] {max_iterations}")
                updated = True

            if ollama_host:
                config[agent_name]["ollama_host"] = ollama_host
                console.print(f"  [green]Set ollama_host:[/] {ollama_host}")
                updated = True

            if vm_host:
                config[agent_name]["vm_host"] = vm_host
                console.print(f"  [green]Set vm_host:[/] {vm_host}")
                updated = True

            if updated:
                config_file.write_text(json.dumps(config, indent=2))
                msg = MessageBox()
                console.print(msg.success("Configuration saved"))
            else:
                console.print("  [dim]No changes specified.[/]")
                console.print("  [dim]Use --show to view current config.[/]")

        console.print(footer(50))

    @app.command("agent-capabilities")
    def show_capabilities(
        agent_name: str = typer.Argument(..., help="Agent name"),
    ):
        """Show detailed capabilities of an agent."""
        console.print(header(f"capabilities: {agent_name}", 50))

        async def get_capabilities():
            if agent_name == "manus":
                from src.infrastructure.agents.manus import create_manus_agent

                agent = await create_manus_agent()
                return agent.get_capabilities()
            elif agent_name == "s3":
                from src.infrastructure.agents.s3 import create_s3_agent

                agent = await create_s3_agent()
                return agent.get_capabilities()
            else:
                return {
                    "error": f"Agent '{agent_name}' not found or doesn't support capabilities query"
                }

        try:
            caps = asyncio.get_event_loop().run_until_complete(get_capabilities())

            if isinstance(caps, dict):
                if "error" in caps:
                    console.print(f"  [yellow]{caps['error']}[/]")
                else:
                    # Display capabilities
                    for key, value in caps.items():
                        if isinstance(value, list):
                            console.print(f"  [bold]{key}:[/]")
                            for item in value:
                                console.print(f"    - {item}")
                        elif isinstance(value, dict):
                            console.print(f"  [bold]{key}:[/]")
                            for k, v in value.items():
                                console.print(f"    {k}: {v}")
                        else:
                            console.print(f"  [bold]{key}:[/] {value}")
            else:
                console.print(f"  {caps}")

        except Exception as e:
            msg = MessageBox()
            console.print(msg.error(str(e)))

        console.print(footer(50))
