"""Live interactive browser automation with Ollama + GPU."""

import asyncio
import re
from typing import Any

import typer
from loguru import logger
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.ui.mascot_hooks import (
    AnimatedMascot,
    live_mascot_status,
    on_long_task_end,
    show_agent_mascot,
)
from src.cli.ui.theme import get_animated_status, get_sunset_banner
from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter
from src.infrastructure.agents.skyvern.skyvern_adapter import SkyvernAdapter
from src.infrastructure.llm.ollama_client import OllamaClient

console = Console()
app = typer.Typer(help="🔴 Live interactive browser automation with AI")


class LiveAutomationSession:
    """
    Live interactive automation session with real-time streaming.

    Features:
    - Real-time UI updates
    - Streaming LLM responses
    - Live screenshot display
    - Action-by-action execution with AI guidance
    """

    def __init__(
        self,
        agent_type: str = "openmanus",
        model: str = "qwen3-coder:30b",
        vision_model: str = "llava:13b",
        headless: bool = True,
    ):
        """Initialize live session."""
        self.agent_type = agent_type
        self.model = model
        self.vision_model = vision_model
        self.headless = headless

        # Initialize components
        self.ollama = OllamaClient(model=model, vision_model=vision_model)

        if agent_type == "skyvern":
            self.agent = SkyvernAdapter(
                headless=self.headless,
                llm_client=self.ollama
            )
        else:
            self.agent = OpenManusAdapter(
                headless=self.headless,
                llm_client=self.ollama
            )

        # Session state
        self.actions_taken = []
        self.current_url = None
        self.current_screenshot = None

        # Animated mascot for live feedback
        self.mascot_anim = AnimatedMascot(console)

    def create_live_layout(self) -> Layout:
        """Create rich layout for live display."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=5),
        )

        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )

        return layout

    async def run_task(self, task: str, starting_url: str | None = None):
        """
        Run browser automation task with live updates.

        Args:
            task: Natural language task description
            starting_url: Optional starting URL
        """
        layout = self.create_live_layout()

        # Update header with mascot
        header_text = Text()
        header_text.append("🔴 LIVE ", style="bold red")
        header_text.append(f"Browser Automation with {self.agent_type.upper()} ", style="bold cyan")
        header_text.append("(=^･ω･^=)🌐", style="bold magenta")  # Browser mascot inline
        layout["header"].update(
            Panel(header_text, border_style="red")
        )

        with Live(layout, console=console, refresh_per_second=4):
            try:
                # Health check with mascot
                mascot_wait = live_mascot_status("wait")
                layout["footer"].update(
                    Panel(f"{mascot_wait} Initializing Ollama...", border_style="yellow")
                )
                await asyncio.sleep(0.5)

                healthy = await self.ollama.health_check()
                if not healthy:
                    mascot_err = live_mascot_status("error")
                    layout["footer"].update(
                        Panel(f"{mascot_err} Ollama not available! Start with: ollama serve", border_style="red")
                    )
                    return

                # Start task with success mascot
                mascot_success = live_mascot_status("success")
                layout["footer"].update(
                    Panel(f"{mascot_success} Ollama ready | 🎯 Task: {task}", border_style="green")
                )

                # Execute automation with live updates
                await self._execute_with_live_updates(task, starting_url, layout)

                # Complete with happy mascot
                mascot_done = live_mascot_status("success")
                layout["footer"].update(
                    Panel(f"{mascot_done} Task completed! Actions taken: {len(self.actions_taken)}", border_style="green")
                )

                await asyncio.sleep(2)  # Let user see final state

            except KeyboardInterrupt:
                mascot_cancelled = "(=^-ω-^=)💤"  # Sleepy mascot
                layout["footer"].update(
                    Panel(f"{mascot_cancelled} Task cancelled by user", border_style="yellow")
                )
            except Exception as e:
                mascot_err = live_mascot_status("error")
                layout["footer"].update(
                    Panel(f"{mascot_err} Error: {str(e)}", border_style="red")
                )
                raise

    async def _execute_with_live_updates(
        self,
        task: str,
        starting_url: str | None,
        layout: Layout
    ):
        """Execute task with live UI updates."""
        max_actions = 10
        action_count = 0

        # Navigate to starting URL if provided
        if starting_url:
            mascot_nav = live_mascot_status("navigate")
            layout["left"].update(
                Panel(f"{mascot_nav} Navigating to {starting_url}...", title="Current Action")
            )

            await self.agent.execute_task({
                "url": starting_url,
                "action": "navigate"
            })

            self.current_url = starting_url
            action_count += 1
            self.actions_taken.append(f"Navigate to {starting_url}")

        # Main automation loop
        while action_count < max_actions:
            # Update status
            self._update_progress_panel(layout, action_count, max_actions)

            # Show AI thinking with mascot
            mascot_thinking = live_mascot_status("thinking")
            layout["right"].update(
                Panel(f"{mascot_thinking} Analyzing page with AI...", title="LLM Guidance", border_style="cyan")
            )

            try:
                # Get current page state from agent
                page_info = await self._get_page_info()
                self.current_url = page_info.get("url", self.current_url)

                # Build prompt for AI
                prompt = self._build_ai_prompt(task, page_info, action_count)

                # Get AI guidance with streaming and animated mascot
                self.mascot_anim.reset()
                guidance_text = f"{self.mascot_anim.get_thinking_frame()} AI is thinking...\n\n"
                layout["right"].update(
                    Panel(guidance_text, title="LLM Guidance (Streaming)", border_style="cyan")
                )

                # Stream AI response with animated mascot
                async for chunk in await self.ollama.generate(prompt, stream=True):
                    guidance_text += chunk
                    mascot_frame = self.mascot_anim.get_streaming_frame()
                    display_text = f"{mascot_frame}\n{guidance_text}"
                    layout["right"].update(
                        Panel(display_text, title="LLM Guidance (Streaming)", border_style="cyan")
                    )

                # Parse AI response to extract action
                action_to_take = self._parse_ai_response(guidance_text)

                if action_to_take:
                    # Add URL to action if not present
                    if "url" not in action_to_take and self.current_url:
                        action_to_take["url"] = self.current_url

                    # Determine mascot based on action type
                    action_lower = action_to_take.get("action", "").lower()
                    if "click" in action_lower:
                        mascot_action = live_mascot_status("click")
                    elif "type" in action_lower or "input" in action_lower:
                        mascot_action = live_mascot_status("type")
                    elif "extract" in action_lower or "scrape" in action_lower:
                        mascot_action = live_mascot_status("extract")
                    elif "screenshot" in action_lower:
                        mascot_action = live_mascot_status("screenshot")
                    else:
                        mascot_action = self.mascot_anim.get_working_frame()

                    # Execute the action with mascot
                    layout["left"].update(
                        Panel(f"{mascot_action} Executing: {action_to_take['description']}", title="Current Action", border_style="yellow")
                    )

                    await self.agent.execute_task(action_to_take)

                    # Record action
                    self.actions_taken.append(action_to_take["description"])
                    action_count += 1

                    # Check if task is complete
                    if "complete" in guidance_text.lower() or "done" in guidance_text.lower():
                        logger.info("AI indicates task is complete")
                        break

                else:
                    # No clear action, ask AI to continue or stop
                    logger.warning("AI did not provide clear action")
                    break

                # Update actions table
                self._update_actions_table(layout)

                # Small delay
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error in automation loop: {e}")
                mascot_err = live_mascot_status("error")
                layout["footer"].update(
                    Panel(f"{mascot_err} Error: {str(e)}", border_style="red")
                )
                break

        # Update final actions list
        self._update_actions_table(layout)

    def _update_progress_panel(self, layout: Layout, current: int, total: int):
        """Update progress panel with mascot."""
        mascot_working = self.mascot_anim.get_working_frame()

        progress_table = Table(show_header=False, box=None)
        progress_table.add_column("Key", style="cyan")
        progress_table.add_column("Value")

        progress_table.add_row("Mascot", mascot_working)
        progress_table.add_row("Actions", f"{current}/{total}")
        progress_table.add_row("URL", self.current_url or "Not set")
        progress_table.add_row("Agent", self.agent_type.upper())
        progress_table.add_row("Model", self.model)

        layout["left"].update(
            Panel(progress_table, title="📊 Status", border_style="green")
        )

    def _update_actions_table(self, layout: Layout):
        """Update actions history table."""
        table = Table(title="Actions History", show_header=True)
        table.add_column("#", style="cyan", width=4)
        table.add_column("Action", style="magenta")

        for i, action in enumerate(self.actions_taken, 1):
            table.add_row(str(i), action)

        layout["left"].update(
            Panel(table, border_style="green")
        )

    async def _get_page_info(self) -> dict[str, Any]:
        """Get current page information from agent."""
        try:
            # Get page info from agent
            page_info = await self.agent.get_page_info()
            return page_info
        except AttributeError:
            # Agent doesn't have get_page_info method, return minimal info
            return {
                "url": self.current_url or "unknown",
                "title": "Unknown",
                "content": "Page content not available"
            }
        except Exception as e:
            logger.error(f"Error getting page info: {e}")
            return {
                "url": self.current_url or "unknown",
                "title": "Error",
                "content": str(e)
            }

    def _build_ai_prompt(self, task: str, page_info: dict[str, Any], action_count: int) -> str:
        """Build prompt for AI to determine next action."""
        prompt = f"""You are an intelligent web automation agent. Your task is to: {task}

Current page information:
- URL: {page_info.get('url', 'unknown')}
- Title: {page_info.get('title', 'unknown')}
- Content preview: {page_info.get('content', 'No content')[:500]}...

Actions taken so far ({action_count}):
{chr(10).join(f"- {action}" for action in self.actions_taken[-3:])}

Based on the current page and the task, what should be the next action?

Please respond in the following format:
ACTION: [describe the action to take]
ELEMENT: [CSS selector or description of element to interact with, if applicable]
VALUE: [value to enter, if applicable]
REASON: [why this action helps complete the task]

If the task is complete, respond with:
ACTION: COMPLETE
REASON: [why the task is complete]
"""
        return prompt

    def _parse_ai_response(self, response: str) -> dict[str, Any] | None:
        """Parse AI response to extract action."""
        try:
            # Simple parsing - look for ACTION, ELEMENT, VALUE
            action_match = re.search(r'ACTION:\s*(.+)', response)
            element_match = re.search(r'ELEMENT:\s*(.+)', response)
            value_match = re.search(r'VALUE:\s*(.+)', response)
            reason_match = re.search(r'REASON:\s*(.+)', response)

            if action_match:
                action = action_match.group(1).strip()

                if action.upper() == "COMPLETE":
                    return None  # Task is complete

                result = {
                    "action": action,
                    "description": action,
                }

                if element_match:
                    result["element"] = element_match.group(1).strip()

                if value_match:
                    result["value"] = value_match.group(1).strip()

                if reason_match:
                    result["reason"] = reason_match.group(1).strip()

                return result

            return None

        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return None


@app.command()
def openmanus(
    task: str = typer.Argument(..., help="Task to accomplish"),
    url: str | None = typer.Option(None, help="Starting URL"),
    model: str = typer.Option("qwen3-coder:30b", help="Ollama model"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Run browser in headless mode (no GUI)"),
    vnc: bool = typer.Option(False, "--vnc", help="Start VNC server for remote browser viewing"),
):
    """
    🔴 LIVE: Run OpenManus automation with real-time AI guidance.

    This command shows a live interactive interface with:
    - Real-time browser actions
    - Streaming LLM responses
    - Live progress updates
    - Screenshot analysis

    BROWSER VISIBILITY (for captchas):
        --headed    : Show browser window (requires X display)
        --vnc       : Start VNC server for remote viewing

    Examples:
        tawiza live openmanus "Find cheapest iPhone on Amazon" --url https://amazon.com
        tawiza live openmanus "Extract top 10 HackerNews articles"
        tawiza live openmanus "Navigate to GitHub" --url https://github.com --headed
        tawiza live openmanus "Solve captcha" --vnc  # View via VNC at :5900
    """
    # Welcome mascot for browser automation
    show_agent_mascot("browser", "Démarrage session OpenManus...", console)
    console.print(get_sunset_banner("\n[bold cyan]🔴 Starting LIVE OpenManus session...[/bold cyan]\n"))

    import os

    # VNC mode for remote browser viewing
    if vnc:
        console.print(Panel(
            "[cyan]🖥️ Mode VNC activé pour voir le navigateur à distance[/cyan]\n\n"
            "[yellow]Configuration:[/yellow]\n"
            "  1. Installer: [green]apt install x11vnc xvfb[/green]\n"
            "  2. Démarrer Xvfb: [green]Xvfb :99 -screen 0 1920x1080x24 &[/green]\n"
            "  3. Démarrer VNC: [green]x11vnc -display :99 -forever -nopw &[/green]\n"
            "  4. Connecter: [green]vnc://localhost:5900[/green]\n\n"
            "[dim]Le navigateur sera visible via le client VNC[/dim]",
            title="📺 VNC Remote Display",
            border_style="cyan"
        ))
        # Set display for VNC
        if not os.environ.get('DISPLAY'):
            os.environ['DISPLAY'] = ':99'
        headless = False

    # Auto-detect if running on server without display
    if not headless and not os.environ.get('DISPLAY'):
        console.print(Panel(
            "[yellow]⚠️ Pas d'affichage détecté (DISPLAY non défini)[/yellow]\n\n"
            "[cyan]Options pour voir le navigateur:[/cyan]\n"
            "  • [green]--vnc[/green] : Démarrer un serveur VNC\n"
            "  • [green]ssh -X user@server[/green] : X11 forwarding\n"
            "  • [green]export DISPLAY=:0[/green] : Si X est disponible\n\n"
            "[dim]Mode headless activé par défaut[/dim]",
            title="🖥️ Mode Headless",
            border_style="yellow"
        ))
        headless = True

    session = LiveAutomationSession(
        agent_type="openmanus",
        model=model,
        headless=headless,
    )

    try:
        asyncio.run(session.run_task(task, url))
        on_long_task_end("OpenManus automation", success=True)
    except KeyboardInterrupt:
        console.print(get_sunset_banner("\n[yellow]⚠️ Session cancelled by user[/yellow]"))
    except Exception:
        on_long_task_end("OpenManus automation", success=False)
    finally:
        console.print(get_sunset_banner("\n[dim]Session ended[/dim]\n"))


@app.command()
def skyvern(
    task: str = typer.Argument(..., help="Task to accomplish"),
    url: str | None = typer.Option(None, help="Starting URL"),
    model: str = typer.Option("qwen3-coder:30b", help="Ollama model"),
    vision: bool = typer.Option(True, help="Use vision model"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Run browser in headless mode (no GUI)"),
    vnc: bool = typer.Option(False, "--vnc", help="Start VNC server for remote browser viewing"),
):
    """
    🔴 LIVE: Run Skyvern automation with vision-guided AI.

    Skyvern uses computer vision + LLM for robust automation:
    - Vision-based element detection (no fragile selectors)
    - Multi-agent architecture
    - Advanced error recovery

    BROWSER VISIBILITY (for captchas):
        --headed    : Show browser window (requires X display)
        --vnc       : Start VNC server for remote viewing

    Examples:
        tawiza live skyvern "Book a hotel in Paris" --url https://booking.com
        tawiza live skyvern "Fill contact form" --url https://example.com/contact
        tawiza live skyvern "Solve captcha manually" --vnc
    """
    # Welcome mascot for browser/scraper automation
    show_agent_mascot("scraper", "Démarrage session Skyvern (Vision-AI)...", console)
    console.print(get_sunset_banner("\n[bold magenta]🔴 Starting LIVE Skyvern session (Vision-powered)...[/bold magenta]\n"))

    import os

    # VNC mode for remote browser viewing
    if vnc:
        console.print(Panel(
            "[cyan]🖥️ Mode VNC activé pour voir le navigateur à distance[/cyan]\n\n"
            "[yellow]Connectez-vous via VNC pour voir le navigateur[/yellow]\n"
            "[dim]Adresse: vnc://localhost:5900 (ou votre IP)[/dim]",
            title="📺 VNC Remote Display",
            border_style="cyan"
        ))
        if not os.environ.get('DISPLAY'):
            os.environ['DISPLAY'] = ':99'
        headless = False

    # Auto-detect if running on server without display
    if not headless and not os.environ.get('DISPLAY'):
        console.print(Panel(
            "[yellow]⚠️ Pas d'affichage détecté[/yellow]\n\n"
            "[cyan]Utilisez --vnc pour activer le mode VNC[/cyan]",
            title="🖥️ Mode Headless",
            border_style="yellow"
        ))
        headless = True

    session = LiveAutomationSession(
        agent_type="skyvern",
        model=model,
        vision_model="llava:13b" if vision else None,
        headless=headless,
    )

    try:
        asyncio.run(session.run_task(task, url))
        on_long_task_end("Skyvern automation", success=True)
    except KeyboardInterrupt:
        console.print(get_sunset_banner("\n[yellow]⚠️ Session cancelled by user[/yellow]"))
    except Exception:
        on_long_task_end("Skyvern automation", success=False)
    finally:
        console.print(get_sunset_banner("\n[dim]Session ended[/dim]\n"))


@app.command()
def stream_test(
    prompt: str = typer.Argument("What is web automation?", help="Test prompt"),
    model: str = typer.Option("qwen3-coder:30b", help="Model to use"),
):
    """
    Test Ollama streaming with live display.

    Example:
        tawiza live stream-test "Explain Playwright vs Selenium"
    """
    async def run_stream():
        console.print(f"\n[cyan]🤖 Model: {model}[/cyan]")
        console.print(f"[dim]Prompt: {prompt}[/dim]\n")

        ollama = OllamaClient(model=model)

        # Check health
        healthy = await ollama.health_check()
        if not healthy:
            console.print(get_sunset_banner("[red]❌ Ollama not available[/red]"))
            return

        console.print(get_sunset_banner("[yellow]Streaming response:[/yellow]\n"))

        # Stream response
        full_response = ""
        async for chunk in await ollama.generate(prompt, stream=True):
            full_response += chunk
            console.print(chunk, end="")

        console.print(get_sunset_banner("\n\n[green]✅ Streaming complete![/green]"))

        await ollama.close()

    try:
        asyncio.run(run_stream())
    except KeyboardInterrupt:
        console.print(get_sunset_banner("\n[yellow]⚠️ Streaming cancelled[/yellow]"))


@app.command("vnc-setup")
def vnc_setup(
    start: bool = typer.Option(False, "--start", "-s", help="Start VNC server after setup"),
    port: int = typer.Option(5900, "--port", "-p", help="VNC port"),
    resolution: str = typer.Option("1920x1080x24", "--resolution", "-r", help="Screen resolution"),
):
    """
    🖥️ Configure VNC for remote browser viewing.

    This sets up Xvfb (virtual framebuffer) and x11vnc so you can
    view the browser remotely when running automation tasks.

    After setup, connect with any VNC client:
        vnc://your-server:5900

    Examples:
        tawiza live vnc-setup           # Show setup instructions
        tawiza live vnc-setup --start   # Setup and start VNC server
    """
    import os
    import subprocess

    console.print(Panel(
        "[bold cyan]🖥️ Configuration VNC pour Tawiza Browser Automation[/bold cyan]",
        border_style="cyan"
    ))

    # Check if packages are installed
    packages_ok = True
    for pkg in ["xvfb", "x11vnc"]:
        result = subprocess.run(["which", pkg], capture_output=True)
        if result.returncode != 0:
            console.print(f"[red]❌ {pkg} non installé[/red]")
            packages_ok = False
        else:
            console.print(f"[green]✅ {pkg} installé[/green]")

    if not packages_ok:
        console.print(Panel(
            "[yellow]Installation requise:[/yellow]\n\n"
            "[green]apt update && apt install -y xvfb x11vnc[/green]",
            title="📦 Packages manquants",
            border_style="yellow"
        ))
        if not start:
            return

    if start:
        console.print("\n[cyan]🚀 Démarrage du serveur VNC...[/cyan]")

        # Kill any existing Xvfb on :99
        subprocess.run(["pkill", "-f", "Xvfb :99"], capture_output=True)

        # Start Xvfb
        console.print("  ▸ Démarrage Xvfb...")
        xvfb_cmd = f"Xvfb :99 -screen 0 {resolution} &"
        subprocess.run(xvfb_cmd, shell=True)

        # Wait for Xvfb
        import time
        time.sleep(1)

        # Start x11vnc
        console.print("  ▸ Démarrage x11vnc...")
        vnc_cmd = f"x11vnc -display :99 -forever -nopw -rfbport {port} &"
        subprocess.run(vnc_cmd, shell=True)

        # Set DISPLAY
        os.environ['DISPLAY'] = ':99'

        console.print(Panel(
            f"[green]✅ Serveur VNC démarré![/green]\n\n"
            f"[cyan]Connexion:[/cyan] vnc://localhost:{port}\n"
            f"[cyan]Display:[/cyan] :99\n"
            f"[cyan]Résolution:[/cyan] {resolution}\n\n"
            "[yellow]Pour utiliser avec le navigateur:[/yellow]\n"
            "  tawiza live openmanus 'task' --headed\n"
            "  tawiza live skyvern 'task' --headed",
            title="📺 VNC Actif",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[yellow]Instructions de démarrage manuel:[/yellow]\n\n"
            f"[dim]# Démarrer le framebuffer virtuel[/dim]\n"
            f"[green]Xvfb :99 -screen 0 {resolution} &[/green]\n\n"
            f"[dim]# Démarrer le serveur VNC[/dim]\n"
            f"[green]x11vnc -display :99 -forever -nopw -rfbport {port} &[/green]\n\n"
            f"[dim]# Définir DISPLAY pour le navigateur[/dim]\n"
            f"[green]export DISPLAY=:99[/green]\n\n"
            f"[dim]# Lancer l'automatisation en mode headed[/dim]\n"
            f"[green]tawiza live openmanus 'task' --headed[/green]\n\n"
            f"[cyan]Ou utilisez: tawiza live vnc-setup --start[/cyan]",
            title="📖 Setup Manuel",
            border_style="cyan"
        ))


@app.command()
def gpu_check():
    """
    Check GPU status and Ollama configuration.

    Verifies:
    - ROCm installation
    - GPU visibility
    - Ollama models
    - GPU acceleration status
    """
    import subprocess

    # Utiliser le theme unifie
    from src.cli.ui.theme import DARK_THEME, get_sunset_banner

    console.print(get_sunset_banner(
        "Tawiza-V2 GPU Status Check",
        "Comprehensive GPU and Ollama Analysis"
    ))

    # Utiliser les couleurs du theme dark
    SUNSET_YELLOW = DARK_THEME.warning_color
    SUNSET_ORANGE = DARK_THEME.accent_color

    # Check ROCm
    console.print(get_animated_status("loading", "🔍 Vérification ROCm..."))
    try:
        result = subprocess.run(["rocm-smi"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            console.print(get_animated_status("success", "✅ ROCm détecté"))
            # Show first few lines
            lines = result.stdout.split("\n")[:5]
            for line in lines:
                console.print(f"  [{SUNSET_ORANGE}]{line}[/{SUNSET_ORANGE}]")
        else:
            console.print(get_animated_status("error", "❌ ROCm non trouvé"))
    except Exception as e:
        console.print(get_animated_status("error", f"❌ Échec de la vérification ROCm: {e}"))

    # Check Ollama
    console.print(get_animated_status("loading", "🔍 Vérification Ollama..."))
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            console.print(get_animated_status("success", "✅ Ollama disponible"))
            console.print(f"[{SUNSET_ORANGE}]{result.stdout}[/{SUNSET_ORANGE}]")
        else:
            console.print(get_animated_status("error", "❌ Ollama non disponible"))
    except Exception as e:
        console.print(get_animated_status("error", f"❌ Échec de la vérification Ollama: {e}"))

    # Check environment
    console.print(get_animated_status("loading", "🔍 Variables d'environnement..."))
    import os
    rocm_vars = ["ROCM_PATH", "HIP_PLATFORM", "HSA_OVERRIDE_GFX_VERSION"]
    for var in rocm_vars:
        value = os.environ.get(var, "Non définie")
        console.print(f"  [{SUNSET_YELLOW}]{var}: [{SUNSET_ORANGE}]{value}[/{SUNSET_ORANGE}][/{SUNSET_YELLOW}]")

    console.print(get_animated_status("success", "✅ Vérification GPU terminée!"))


if __name__ == "__main__":
    app()
