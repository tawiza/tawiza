"""Agent command - Run the unified AI agent with animated display."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from src.cli.v2.ui.agent_display import AgentDisplay, AgentMood
from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.theme import footer, header

console = Console()


def agent_command(
    task: str = typer.Argument(None, help="Task to accomplish in natural language"),
    data: str | None = typer.Option(None, "--data", "-d", help="Input data file"),
    output: str = typer.Option("./output", "--output", "-o", help="Output directory"),
    model: str = typer.Option("qwen3.5:27b", "--model", "-m", help="Ollama model to use"),
    max_steps: int = typer.Option(20, "--max-steps", help="Maximum ReAct steps"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show agent reasoning"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan without executing"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactive conversation mode"
    ),
):
    """Run the unified AI agent to accomplish a task.

    The agent autonomously uses all available tools (browser, analyst, coder, ml,
    files, api, carto) to complete your request.

    Examples:
        tawiza agent "What time is it in Tokyo?"
        tawiza agent "Analyze this CSV and create a summary" -d data.csv
        tawiza agent "Scrape HN and find AI trends" --verbose
        tawiza agent --interactive  # Start conversation mode
    """
    if interactive:
        asyncio.run(
            _run_interactive(
                model=model,
                output=output,
                max_steps=max_steps,
                verbose=verbose,
                initial_task=task,
                initial_data=data,
            )
        )
    else:
        if not task:
            console.print("[yellow]No task provided. Use --interactive for conversation mode.[/]")
            return
        asyncio.run(
            _run_agent(
                task=task,
                data=data,
                output=output,
                model=model,
                max_steps=max_steps,
                verbose=verbose,
                dry_run=dry_run,
            )
        )


async def _run_agent(
    task: str,
    data: str | None,
    output: str,
    model: str,
    max_steps: int,
    verbose: bool,
    dry_run: bool,
):
    """Run the agent asynchronously with animated display."""
    from src.cli.v2.agents.tools import register_all_tools
    from src.cli.v2.agents.unified import AgentCallback, AgentEvent, UnifiedAgent
    from src.cli.v2.agents.unified.planner import ReActPlanner
    from src.cli.v2.agents.unified.tools import ToolRegistry

    msg = MessageBox()

    if dry_run:
        console.print(header("tawiza agent", 40))
        console.print()
        console.print(f"  [bold]Task:[/] {task[:60]}{'...' if len(task) > 60 else ''}")
        console.print("  [yellow]Dry run mode - planning only[/]")
        console.print(footer(40))
        return

    # Initialize components
    try:
        from src.infrastructure.llm.ollama_client import OllamaClient

        # Real Ollama client with GPU support
        ollama = OllamaClient(model=model)

        # Health check (quick, no display yet)
        healthy = await ollama.health_check()
        if not healthy:
            console.print(
                msg.error(
                    "Ollama not available",
                    ["Start with: ollama serve", "Or: tawiza pro ollama-start"],
                )
            )
            return

        planner = ReActPlanner(ollama_client=ollama, model=model)
        tools = ToolRegistry()
        register_all_tools(tools)

    except Exception as e:
        console.print(msg.error("Failed to initialize agent", [str(e)]))
        return

    # Create animated display
    display = AgentDisplay(console)
    display.state.model = model
    display.state.total_steps = max_steps
    display.update(thought=f"Task: {task[:50]}...")

    # Event handler to update display
    def on_agent_event(cb: AgentCallback):
        """Handle agent events and update display."""
        event_to_mood = {
            AgentEvent.THINKING: AgentMood.THINKING,
            AgentEvent.ACTING: AgentMood.WORKING,
            AgentEvent.OBSERVING: AgentMood.WORKING,
            AgentEvent.FINISHED: AgentMood.SUCCESS,
            AgentEvent.ERROR: AgentMood.ERROR,
        }

        mood = event_to_mood.get(cb.event, AgentMood.WORKING)

        # Build thought text based on event
        if cb.event == AgentEvent.THINKING:
            thought = "Planning next action..."
        elif cb.event == AgentEvent.ACTING:
            thought = cb.thought[:60] if cb.thought else "Executing..."
        elif cb.event == AgentEvent.OBSERVING:
            thought = f"Result: {cb.result[:50]}..." if cb.result else "Processing..."
        elif cb.event == AgentEvent.FINISHED:
            thought = "Task completed!"
        else:
            thought = cb.thought[:60] if cb.thought else ""

        # Action text
        action = None
        if cb.event == AgentEvent.ACTING and cb.action:
            # Clean up action display
            action = cb.action.split("(")[0] if "(" in cb.action else cb.action

        display.update(
            mood=mood,
            thought=thought,
            action=action,
            progress=cb.progress,
            step=cb.step,
            total_steps=cb.total_steps,
            elapsed=cb.elapsed,
        )

    # Create agent with callback
    agent = UnifiedAgent(
        planner=planner,
        tools=tools,
        max_steps=max_steps,
        verbose=verbose,
        on_event=on_agent_event,
    )

    # Run with animated display
    try:
        await display.start()
        result = await agent.run(task=task, data=data)
    finally:
        await display.stop()

    # Display result
    console.print()
    if result.success:
        answer = result.answer or ""

        # Smart display threshold: show more for terminal-friendly lengths
        DISPLAY_THRESHOLD = 1500  # Characters to show in terminal
        FILE_THRESHOLD = 500  # Save to file if longer than this

        # Show result panel with more content
        display_answer = answer[:DISPLAY_THRESHOLD]
        if len(answer) > DISPLAY_THRESHOLD:
            display_answer += "..."

        display.show_result(display_answer, success=True)

        # Save to file if result is long
        if len(answer) > FILE_THRESHOLD:
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"agent_result_{int(result.duration_seconds)}.md"
            output_file.write_text(answer)
            console.print()
            console.print(f"  [dim]Full output saved to:[/] {output_file}")

        # Stats
        console.print()
        console.print(
            f"  [dim]{len(result.steps)} steps • {result.duration_seconds:.1f}s • {model}[/dim]"
        )
    else:
        display.show_result(result.error or "Unknown error", success=False)

        if verbose and result.steps:
            console.print()
            console.print("  [dim]Last steps:[/]")
            for i, step in enumerate(result.steps[-3:], 1):
                console.print(f"    {i}. {step.tool_call.name}: {step.thought[:40]}...")


async def _run_interactive(
    model: str,
    output: str,
    max_steps: int,
    verbose: bool,
    initial_task: str | None = None,
    initial_data: str | None = None,
):
    """Run the agent in interactive conversation mode."""

    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.styles import Style

    from src.cli.v2.agents.tools import register_all_tools
    from src.cli.v2.agents.unified.planner import ReActPlanner
    from src.cli.v2.agents.unified.tools import ToolRegistry

    msg = MessageBox()

    # Display header
    console.print(header("agent interactive", 50))
    console.print()
    console.print("  [bold cyan]Intelligence Territoriale[/] - Mode Conversation")
    console.print("  [dim]Tapez 'exit' pour quitter, 'help' pour l'aide[/]")
    console.print(footer(50))
    console.print()

    # Initialize components
    try:
        from src.infrastructure.llm.ollama_client import OllamaClient

        ollama = OllamaClient(model=model)

        healthy = await ollama.health_check()
        if not healthy:
            console.print(
                msg.error(
                    "Ollama not available",
                    ["Start with: ollama serve", "Or: tawiza pro ollama-start"],
                )
            )
            return

        planner = ReActPlanner(ollama_client=ollama, model=model)
        tools = ToolRegistry()
        register_all_tools(tools)

    except Exception as e:
        console.print(msg.error("Failed to initialize agent", [str(e)]))
        return

    # Session context for conversation continuity
    session_context = {
        "history": [],  # Previous Q&A pairs
        "files": [],  # Generated files
        "data": {},  # Collected data (enterprises, locations, etc.)
    }

    # Prompt session with history
    history_file = Path.home() / ".tawiza" / "agent_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    prompt_style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
        }
    )
    session = PromptSession(
        history=FileHistory(str(history_file)),
        style=prompt_style,
    )

    # Process initial task if provided
    if initial_task:
        console.print(f"  [cyan]►[/] {initial_task}")
        await _process_interactive_query(
            query=initial_task,
            data=initial_data,
            planner=planner,
            tools=tools,
            max_steps=max_steps,
            verbose=verbose,
            output=output,
            model=model,
            session_context=session_context,
        )

    # Interactive loop
    while True:
        try:
            user_input = await asyncio.to_thread(session.prompt, [("class:prompt", "agent ► ")])
            user_input = user_input.strip()

            if not user_input:
                continue

            # Commands
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("\n  [dim]Session terminée. À bientôt ![/]")
                break

            if user_input.lower() == "help":
                _show_interactive_help()
                continue

            if user_input.lower() == "context":
                _show_context(session_context)
                continue

            if user_input.lower() == "clear":
                session_context = {"history": [], "files": [], "data": {}}
                console.print("  [dim]Contexte effacé.[/]")
                continue

            if user_input.lower() == "files":
                _show_files(session_context)
                continue

            # Process query
            await _process_interactive_query(
                query=user_input,
                data=None,
                planner=planner,
                tools=tools,
                max_steps=max_steps,
                verbose=verbose,
                output=output,
                model=model,
                session_context=session_context,
            )

        except KeyboardInterrupt:
            console.print("\n  [dim]Ctrl+C - tapez 'exit' pour quitter[/]")
            continue
        except EOFError:
            console.print("\n  [dim]Session terminée.[/]")
            break


async def _process_interactive_query(
    query: str,
    data: str | None,
    planner,
    tools,
    max_steps: int,
    verbose: bool,
    output: str,
    model: str,
    session_context: dict,
):
    """Process a single query in interactive mode."""
    from src.cli.v2.agents.unified import AgentCallback, AgentEvent, UnifiedAgent

    display = AgentDisplay(console)
    display.state.model = model
    display.state.total_steps = max_steps
    display.update(thought=f"Processing: {query[:40]}...")

    # Event handler
    def on_agent_event(cb: AgentCallback):
        event_to_mood = {
            AgentEvent.THINKING: AgentMood.THINKING,
            AgentEvent.ACTING: AgentMood.WORKING,
            AgentEvent.OBSERVING: AgentMood.WORKING,
            AgentEvent.FINISHED: AgentMood.SUCCESS,
            AgentEvent.ERROR: AgentMood.ERROR,
        }
        mood = event_to_mood.get(cb.event, AgentMood.WORKING)

        if cb.event == AgentEvent.THINKING:
            thought = "Réflexion..."
        elif cb.event == AgentEvent.ACTING:
            thought = cb.thought[:60] if cb.thought else "Exécution..."
        elif cb.event == AgentEvent.OBSERVING:
            thought = f"Résultat: {cb.result[:50]}..." if cb.result else "Traitement..."
        elif cb.event == AgentEvent.FINISHED:
            thought = "Terminé !"
        else:
            thought = cb.thought[:60] if cb.thought else ""

        action = None
        if cb.event == AgentEvent.ACTING and cb.action:
            action = cb.action.split("(")[0] if "(" in cb.action else cb.action

        display.update(
            mood=mood,
            thought=thought,
            action=action,
            progress=cb.progress,
            step=cb.step,
            total_steps=cb.total_steps,
            elapsed=cb.elapsed,
        )

    # Build context-aware prompt
    context_prompt = _build_context_prompt(query, session_context)

    agent = UnifiedAgent(
        planner=planner,
        tools=tools,
        max_steps=max_steps,
        verbose=verbose,
        on_event=on_agent_event,
    )

    try:
        await display.start()
        result = await agent.run(task=context_prompt, data=data)
    finally:
        await display.stop()

    # Display result
    console.print()
    if result.success:
        answer = result.answer or ""

        # Update session context
        session_context["history"].append(
            {
                "query": query,
                "answer": answer[:500],  # Truncate for context
                "steps": len(result.steps),
            }
        )

        # Track generated files
        for step in result.steps:
            if step.result and "file_path" in str(step.result):
                # Extract file paths from results
                import re

                paths = re.findall(r"['\"]([^'\"]+\.(html|csv|json|md))['\"]", str(step.result))
                for path, _ in paths:
                    if path not in session_context["files"]:
                        session_context["files"].append(path)

        # Display
        DISPLAY_THRESHOLD = 1500
        display_answer = answer[:DISPLAY_THRESHOLD]
        if len(answer) > DISPLAY_THRESHOLD:
            display_answer += "..."

        display.show_result(display_answer, success=True)

        # Stats
        console.print()
        console.print(f"  [dim]{len(result.steps)} steps • {result.duration_seconds:.1f}s[/]")
    else:
        display.show_result(result.error or "Erreur inconnue", success=False)

    console.print()


def _build_context_prompt(query: str, session_context: dict) -> str:
    """Build a prompt with conversation context."""
    if not session_context["history"]:
        return query

    # Include last 3 exchanges for context
    recent = session_context["history"][-3:]
    context_parts = ["[Contexte de conversation précédent:]"]

    for exchange in recent:
        context_parts.append(f"- Q: {exchange['query'][:100]}")
        context_parts.append(f"  R: {exchange['answer'][:200]}...")

    context_parts.append("")
    context_parts.append(f"[Nouvelle question:] {query}")

    return "\n".join(context_parts)


def _show_interactive_help():
    """Display help for interactive mode."""
    console.print()
    console.print("  [bold cyan]Commandes disponibles:[/]")
    console.print("  [dim]─────────────────────────────────────[/]")
    console.print("  [cyan]exit[/]     Quitter le mode interactif")
    console.print("  [cyan]help[/]     Afficher cette aide")
    console.print("  [cyan]context[/]  Voir le contexte de conversation")
    console.print("  [cyan]files[/]    Voir les fichiers générés")
    console.print("  [cyan]clear[/]    Effacer le contexte")
    console.print()
    console.print("  [bold cyan]Exemples de requêtes:[/]")
    console.print("  [dim]─────────────────────────────────────[/]")
    console.print("  • Trouve les entreprises tech à Lille")
    console.print("  • Génère une carte des startups")
    console.print("  • Quelles subventions pour l'IA ?")
    console.print("  • Analyse le réseau d'acteurs")
    console.print()


def _show_context(session_context: dict):
    """Display current session context."""
    console.print()
    console.print("  [bold cyan]Contexte de session:[/]")
    console.print("  [dim]─────────────────────────────────────[/]")

    history = session_context.get("history", [])
    if history:
        console.print(f"  Échanges: {len(history)}")
        for i, h in enumerate(history[-5:], 1):
            console.print(f"    {i}. {h['query'][:50]}...")
    else:
        console.print("  [dim]Aucun échange encore.[/]")

    files = session_context.get("files", [])
    if files:
        console.print(f"\n  Fichiers générés: {len(files)}")
        for f in files[-5:]:
            console.print(f"    • {f}")

    console.print()


def _show_files(session_context: dict):
    """Display generated files."""
    console.print()
    files = session_context.get("files", [])
    if files:
        console.print(f"  [bold cyan]Fichiers générés ({len(files)}):[/]")
        console.print("  [dim]─────────────────────────────────────[/]")
        for f in files:
            console.print(f"    • {f}")
    else:
        console.print("  [dim]Aucun fichier généré.[/]")
    console.print()
