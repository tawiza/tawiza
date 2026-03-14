"""Tawiza CLI v2 - Minimal + Pro Mode Architecture.

Main application with 5 simple commands + pro namespace.
"""

import typer
from rich.console import Console

from src.cli.v2.experience import ExperienceController
from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.theme import THEME
from src.cli.v2.utils.completers import agent_completion, model_completion
from src.cli.v2.utils.suggestions import print_suggestions

console = Console()

# Global experience controller instance for unified UX
_experience: ExperienceController | None = None


def get_experience() -> ExperienceController:
    """Get or create the global ExperienceController instance."""
    global _experience
    if _experience is None:
        _experience = ExperienceController()
    return _experience


# Main app
app = typer.Typer(
    name="tawiza",
    help="Tawiza - AI Multi-Agent Platform",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Pro namespace
pro_app = typer.Typer(
    name="pro",
    help="Advanced commands for power users",
    rich_markup_mode="rich",
)


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        try:
            from src.core.constants import APP_VERSION

            version = APP_VERSION
        except ImportError:
            version = "2.0"

        from src.cli.v2.ui.theme import footer, header

        console.print(header("tawiza", 40))
        console.print(f"  version   {version}")
        console.print(footer(40))
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, is_eager=True, help="Show version"
    ),
):
    """Tawiza - AI Multi-Agent Platform with GPU Acceleration."""
    if ctx.invoked_subcommand is None:
        # No command = show welcome screen using ExperienceController
        try:
            from src.core.constants import APP_VERSION

            ver = APP_VERSION
        except ImportError:
            ver = "2.0"

        # Use ExperienceController for unified welcome experience
        experience = get_experience()
        welcome_text = experience.get_welcome(ver)
        console.print(welcome_text, style=THEME["accent"])


# Register simple commands
@app.command("status", rich_help_panel="Core Commands")
def status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed info"),
):
    """Show system status dashboard.

    [bold]Examples:[/]
      tawiza status          Quick status overview
      tawiza status -v       Detailed system info
    """
    from src.cli.v2.commands.simple.status import status_command

    status_command(verbose=verbose)
    print_suggestions("status")


@app.command("chat", rich_help_panel="Core Commands")
def chat(
    message: str | None = typer.Argument(None, help="Message to send"),
    model: str = typer.Option(
        "qwen3.5:27b", "--model", "-m", help="Model to use", autocompletion=model_completion
    ),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Interactive mode"
    ),
):
    """Chat with the AI assistant.

    [bold]Examples:[/]
      tawiza chat                    Interactive chat session
      tawiza chat "Hello!"           Send a quick message
      tawiza chat -m llama3:8b       Use a specific model
      tawiza chat --no-interactive   Single response mode
    """
    from src.cli.v2.commands.simple.chat import chat_command

    chat_command(message=message, model=model, interactive=interactive)
    print_suggestions("chat")


@app.command("run", rich_help_panel="Core Commands")
def run(
    agent: str | None = typer.Argument(None, help="Agent to run", autocompletion=agent_completion),
    task: str | None = typer.Option(None, "--task", "-t", help="Task description"),
    data: str | None = typer.Option(None, "--data", "-d", help="Input data file"),
    url: str | None = typer.Option(None, "--url", "-u", help="Starting URL (browser agent)"),
    model: str = typer.Option(
        "qwen3.5:27b", "--model", "-m", help="Ollama model to use", autocompletion=model_completion
    ),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive"),
    output_json: bool = typer.Option(False, "--json", help="Output result as JSON"),
):
    """Run an AI agent with specified task.

    [bold]Examples:[/]
      tawiza run                              Interactive agent selection
      tawiza run analyst -d data.csv          Analyze a dataset
      tawiza run browser -t "search Google"   Web automation
      tawiza run coder -t "Create a function" Generate code
      tawiza run ml -d train.csv              Train ML model
    """
    from src.cli.v2.commands.simple.run import run_command

    run_command(
        agent=agent,
        task=task,
        data=data,
        url=url,
        model=model,
        interactive=interactive,
        output_json=output_json,
    )
    print_suggestions("run")


@app.command("agent", rich_help_panel="Core Commands")
def agent(
    task: str = typer.Argument(None, help="Task to accomplish"),
    data: str | None = typer.Option(None, "--data", "-d", help="Input data file"),
    output: str = typer.Option("./output", "--output", "-o", help="Output directory"),
    model: str = typer.Option(
        "qwen3.5:27b", "--model", "-m", help="Ollama model to use", autocompletion=model_completion
    ),
    max_steps: int = typer.Option(20, "--max-steps", help="Maximum ReAct steps"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show reasoning"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Conversation mode"),
):
    """Run the unified AI agent.

    [bold]Examples:[/]
      tawiza agent "What time is it in Tokyo?"
      tawiza agent "Analyze trends" -d data.csv
      tawiza agent "Scrape and summarize HN" -v
      tawiza agent --interactive  # Conversation mode
    """
    from src.cli.v2.commands.simple.agent import agent_command

    agent_command(
        task=task,
        data=data,
        output=output,
        model=model,
        max_steps=max_steps,
        verbose=verbose,
        dry_run=dry_run,
        interactive=interactive,
    )
    if not interactive:
        print_suggestions("agent")


@app.command("analyze", rich_help_panel="Core Commands")
def analyze(
    query: str = typer.Argument(..., help="Analysis query (e.g., 'marché conseil IT Lille')"),
    output: str = typer.Option("./outputs/analyses", "--output", "-o", help="Output directory"),
    model: str = typer.Option(
        "qwen3.5:27b", "--model", "-m", help="Ollama model to use", autocompletion=model_completion
    ),
    depth: str = typer.Option(
        "standard", "--depth", "-d", help="Analysis depth: quick, standard, full"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Max enterprises to analyze"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    use_agents: bool = typer.Option(
        False, "--use-agents", "-a", help="Use Camel AI multi-agent orchestration"
    ),
    multi_source: bool = typer.Option(
        False, "--multi-source", "-M", help="Use parallel 8-source orchestration with validation"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Enter interactive mode after analysis"
    ),
):
    """Analyze a territorial market using Camel AI multi-agent system.

    Depth levels:
    - quick: Fast Sirene search + basic report (~10s)
    - standard: + Map + CSV export (~30s)
    - full: + Web enrichment + Graph + JSONL annotation format (~2-5min)

    Modes:
    - Default: Direct tool execution (faster, predictable)
    - --use-agents: Camel AI multi-agent orchestration (smarter, autonomous)
    - --multi-source: Parallel 8-source queries + multi-agent validation
    - --interactive: Continue with follow-up questions after analysis

    [bold]Examples:[/]
      tawiza analyze "conseil IT Lille"
      tawiza analyze "startups IA Hauts-de-France" --depth full
      tawiza analyze "startups IA Lille" --use-agents -v
      tawiza analyze "startup IA Lille" --multi-source  # 8 sources + validation
      tawiza analyze "conseil IT Lyon" -i  # Interactive follow-ups
    """
    from src.infrastructure.agents.camel.cli.analyze_command import analyze_command

    analyze_command(
        query=query,
        output=output,
        model=model,
        depth=depth,
        limit=limit,
        verbose=verbose,
        use_agents=use_agents,
        multi_source=multi_source,
        interactive=interactive,
    )
    if not interactive:
        print_suggestions("analyze")


@app.command("tajine", rich_help_panel="Core Commands")
def tajine(
    query: str = typer.Argument(None, help="Query for territorial intelligence"),
    territory: str | None = typer.Option(
        None, "--territory", "-t", help="Territory code (e.g., 34, 75)"
    ),
    sector: str | None = typer.Option(
        None, "--sector", "-s", help="Sector (tech, biotech, commerce)"
    ),
    model: str = typer.Option(
        "qwen3.5:27b",
        "--model",
        "-m",
        help="LLM model for reasoning",
        autocompletion=model_completion,
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    real_api: bool = typer.Option(False, "--real-api", help="Use real SIRENE API"),
    output: str = typer.Option("./output", "--output", "-o", help="Output directory"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Run TAJINE strategic meta-agent (PPDSL cycle).

    TAJINE = Territorial Analysis and Intelligence Engine
    Executes: Perceive -> Plan -> Delegate -> Synthesize -> Learn

    [bold]Examples:[/]
      tawiza tajine "Analyse tech sector in 34"
      tawiza tajine --territory 34 --sector tech -v
      tawiza tajine "Compare 75 vs 13" --real-api
    """
    from src.cli.v2.commands.simple.tajine import tajine_command

    tajine_command(
        query=query,
        territory=territory,
        sector=sector,
        model=model,
        verbose=verbose,
        real_api=real_api,
        output=output,
        json_output=json_output,
    )
    print_suggestions("tajine")


# Register pro namespace
app.add_typer(pro_app, name="pro")


# Pro commands
@pro_app.command("agent-list")
def pro_agent_list(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """List available AI agents."""
    from rich.table import Table

    from src.cli.v2.ui.theme import footer, header

    console.print(header("agents", 40))

    table = Table(show_header=True, header_style=f"bold {THEME['accent']}")
    table.add_column("Name")
    table.add_column("Description")
    if verbose:
        table.add_column("Status")

    agents = [
        ("analyst", "Data analysis and insights", "ready"),
        ("coder", "Code generation and review", "ready"),
        ("browser", "Web automation and scraping", "ready"),
        ("ml", "Machine learning tasks", "ready"),
    ]

    for name, desc, status in agents:
        if verbose:
            table.add_row(name, desc, f"[{THEME['success']}]{status}[/]")
        else:
            table.add_row(name, desc)

    console.print(table)
    console.print(footer(40))


@pro_app.command("model-list")
def pro_model_list():
    """List available models."""
    from rich.table import Table

    from src.cli.v2.ui.components import MessageBox
    from src.cli.v2.ui.theme import footer, header

    console.print(header("models", 40))

    try:
        import httpx

        response = httpx.get("http://localhost:11434/api/tags", timeout=10)

        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])

            if models:
                table = Table(show_header=True, header_style=f"bold {THEME['accent']}")
                table.add_column("Model")
                table.add_column("Size")

                for m in models:
                    name = m.get("name", "unknown")
                    size = m.get("size", 0)
                    size_gb = f"{size / 1e9:.1f}GB" if size else "?"
                    table.add_row(name, size_gb)

                console.print(table)
            else:
                console.print("  No models found. Pull one with:")
                console.print("  tawiza pro model-pull qwen3.5:27b")
        else:
            msg = MessageBox()
            console.print(msg.error("Failed to list models"))

    except Exception:
        msg = MessageBox()
        console.print(msg.error("Ollama not available", ["Start with: tawiza pro ollama-start"]))

    console.print(footer(40))


@pro_app.command("model-pull")
def pro_model_pull(
    model: str = typer.Argument(..., help="Model name to pull"),
):
    """Pull a model from Ollama registry."""
    from src.cli.v2.ui.components import MessageBox
    from src.cli.v2.ui.mascot import mascot_message
    from src.cli.v2.ui.theme import footer, header

    console.print(header(f"pull: {model}", 40))
    console.print(mascot_message(f"Pulling {model}...", "working"))

    try:
        import subprocess

        result = subprocess.run(["ollama", "pull", model], capture_output=False)

        if result.returncode == 0:
            msg = MessageBox()
            console.print(msg.success(f"Model {model} ready!"))
        else:
            msg = MessageBox()
            console.print(msg.error("Pull failed"))

    except Exception as e:
        msg = MessageBox()
        console.print(msg.error(str(e)))

    console.print(footer(40))


@pro_app.command("gpu-status")
def pro_gpu_status():
    """Show GPU status."""
    from src.cli.v2.ui.components import MessageBox, StatusBar
    from src.cli.v2.ui.theme import footer, header

    console.print(header("gpu status", 40))

    try:
        import subprocess

        result = subprocess.run(
            ["rocm-smi", "--showuse", "--showtemp", "--showmeminfo", "vram"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            bar = StatusBar()
            bar.add("gpu", "AMD detected", "ok")
            console.print(bar.render())
            console.print()
            console.print(result.stdout)
        else:
            bar = StatusBar()
            bar.add("gpu", "Not available", "warn")
            console.print(bar.render())

    except Exception:
        msg = MessageBox()
        console.print(
            msg.error("GPU not detected", ["Ensure ROCm is installed", "Check AMD drivers"])
        )

    console.print(footer(40))


@pro_app.command("ollama-start")
def pro_ollama_start():
    """Start Ollama server."""
    from src.cli.v2.ui.components import MessageBox
    from src.cli.v2.ui.theme import footer, header

    console.print(header("ollama", 40))

    try:
        import subprocess

        # Check if already running
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"], capture_output=True, timeout=5
        )

        if result.returncode == 0:
            msg = MessageBox()
            console.print(msg.info("Ollama already running"))
        else:
            console.print("  Starting Ollama...")
            subprocess.Popen(
                ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            import time

            time.sleep(2)
            msg = MessageBox()
            console.print(msg.success("Ollama started!"))

    except Exception as e:
        msg = MessageBox()
        console.print(msg.error(str(e)))

    console.print(footer(40))


@pro_app.command("ollama-stop")
def pro_ollama_stop():
    """Stop Ollama server."""
    from src.cli.v2.ui.components import MessageBox
    from src.cli.v2.ui.theme import footer, header

    console.print(header("ollama", 40))

    try:
        import subprocess

        subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
        msg = MessageBox()
        console.print(msg.success("Ollama stopped"))
    except Exception as e:
        msg = MessageBox()
        console.print(msg.error(str(e)))

    console.print(footer(40))


# Register sources command
from src.cli.v2.commands.sources import app as sources_app

app.add_typer(sources_app, name="sources")

# Register additional pro commands from modules
from src.cli.v2.commands.pro.agents import register as register_agents
from src.cli.v2.commands.pro.config import register as register_config
from src.cli.v2.commands.pro.data import register as register_data
from src.cli.v2.commands.pro.gpu import register as register_gpu
from src.cli.v2.commands.pro.metrics import register as register_metrics
from src.cli.v2.commands.pro.monitoring import register as register_monitoring
from src.cli.v2.commands.pro.services import register as register_services
from src.cli.v2.commands.pro.system import register as register_system
from src.cli.v2.commands.pro.training import register as register_training

register_data(pro_app)
register_training(pro_app)
register_monitoring(pro_app)
register_config(pro_app)
register_system(pro_app)
register_gpu(pro_app)
register_agents(pro_app)
register_services(pro_app)
register_metrics(pro_app)


# TUI Dashboard command
@app.command("tui", rich_help_panel="Core Commands")
def tui_dashboard():
    """Launch the interactive TUI dashboard.

    Opens a full-screen terminal dashboard with:
    - Real-time GPU/CPU/RAM metrics
    - Service status monitoring
    - Active agent tasks
    - Keyboard navigation

    [bold]Keys:[/]
      q - Quit
      r - Refresh
      h - Help
    """
    try:
        from src.cli.v3.tui import run_tui

        run_tui()
    except ImportError:
        msg = MessageBox()
        console.print(msg.error("TUI dependencies not installed", ["Run: pip install textual"]))
    except Exception as e:
        msg = MessageBox()
        console.print(msg.error(f"TUI error: {e}"))


if __name__ == "__main__":
    app()
