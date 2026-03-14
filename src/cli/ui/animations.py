"""
Professional Animations - Advanced CLI animations

Provides sophisticated animations:
- Custom spinners with complex patterns
- Text transitions (fade, slide, wave, typewriter)
- Loading animations with effects
- Progress bars with visual effects
- Particle effects
"""

import math
import random
import time
from dataclasses import dataclass

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


@dataclass
class AnimationFrame:
    """Single animation frame"""

    content: str
    delay: float = 0.05


class CustomSpinners:
    """
    Collection of custom spinners with complex patterns
    """

    # Cyberpunk spinners
    CYBERPUNK = ["⡀", "⡁", "⡂", "⡃", "⡄", "⡅", "⡆", "⡇", "⡈", "⡉", "⡊", "⡋", "⡌", "⡍", "⡎", "⡏"]
    CYBER_CIRCLE = ["◜", "◝", "◞", "◟"]
    NEON_PULSE = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"]

    # Matrix-style
    MATRIX = ["ｱ", "ｲ", "ｳ", "ｴ", "ｵ", "ｶ", "ｷ", "ｸ"]
    DIGITAL = ["0", "1", "0", "1", "█", "0", "1"]

    # Geometric
    TRIANGLES = ["◢", "◣", "◤", "◥"]
    SQUARES = ["▖", "▘", "▝", "▗"]
    DIAMONDS = ["◇", "◈", "◆", "◈"]

    # Wave patterns
    WAVE = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    SINE_WAVE = ["⠁", "⠂", "⠄", "⡀", "⢀", "⠠", "⠐", "⠈"]

    # Complex patterns
    ORBITAL = ["◐", "◓", "◑", "◒"]
    GALAXY = ["✶", "✸", "✹", "✺", "✹", "✸"]
    PULSE = ["○", "◔", "◑", "◕", "●", "◕", "◑", "◔"]

    # Arrow sequences
    ARROWS = ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"]
    BOUNCE = ["⠁", "⠂", "⠄", "⠂"]

    @classmethod
    def get_spinner(cls, name: str) -> list[str]:
        """Get spinner frames by name"""
        spinners = {
            "cyberpunk": cls.CYBERPUNK,
            "cyber_circle": cls.CYBER_CIRCLE,
            "neon_pulse": cls.NEON_PULSE,
            "matrix": cls.MATRIX,
            "digital": cls.DIGITAL,
            "triangles": cls.TRIANGLES,
            "squares": cls.SQUARES,
            "diamonds": cls.DIAMONDS,
            "wave": cls.WAVE,
            "sine_wave": cls.SINE_WAVE,
            "orbital": cls.ORBITAL,
            "galaxy": cls.GALAXY,
            "pulse": cls.PULSE,
            "arrows": cls.ARROWS,
            "bounce": cls.BOUNCE,
        }
        return spinners.get(name.lower(), cls.CYBERPUNK)


class TextAnimations:
    """
    Text animation effects
    """

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def typewriter(
        self,
        text: str,
        *,
        delay: float = 0.05,
        style: str = "bold cyan",
    ) -> None:
        """
        Typewriter effect - characters appear one by one

        Args:
            text: Text to display
            delay: Delay between characters
            style: Text style
        """
        for char in text:
            self.console.print(char, end="", style=style)
            time.sleep(delay)
        self.console.print()  # New line at end

    def wave_text(
        self,
        text: str,
        *,
        duration: float = 2.0,
        fps: int = 20,
    ) -> None:
        """
        Wave effect - text moves up and down

        Args:
            text: Text to animate
            duration: Animation duration
            fps: Frames per second
        """
        frame_delay = 1.0 / fps
        frames = int(duration * fps)

        with Live(console=self.console, refresh_per_second=fps) as live:
            for frame in range(frames):
                lines = []
                for i, char in enumerate(text):
                    # Calculate vertical offset
                    offset = int(3 * math.sin((i + frame) * 0.5))
                    padding = " " * max(0, offset + 3)
                    lines.append(padding + char)

                # Display frame
                live.update(Text("".join(lines), style="bold magenta"))
                time.sleep(frame_delay)

    def fade_in(
        self,
        text: str,
        *,
        duration: float = 1.0,
        steps: int = 10,
    ) -> None:
        """
        Fade in effect using brightness

        Args:
            text: Text to fade in
            duration: Fade duration
            steps: Number of brightness steps
        """
        step_delay = duration / steps

        for i in range(steps + 1):
            # Calculate opacity (0 to 100)
            opacity = int((i / steps) * 100)

            # Use dim style for fade effect
            if opacity < 30:
                style = "dim"
            elif opacity < 70:
                style = "white"
            else:
                style = "bold white"

            self.console.clear()
            self.console.print(text, style=style)
            time.sleep(step_delay)

    def slide_in(
        self,
        text: str,
        *,
        direction: str = "right",
        duration: float = 1.0,
        fps: int = 30,
    ) -> None:
        """
        Slide in effect - text slides from edge

        Args:
            text: Text to slide
            direction: Slide direction (left, right, top, bottom)
            duration: Animation duration
            fps: Frames per second
        """
        frame_delay = 1.0 / fps
        frames = int(duration * fps)
        text_width = len(text)

        with Live(console=self.console, refresh_per_second=fps) as live:
            for frame in range(frames):
                progress = frame / frames

                if direction == "right":
                    # Slide from left to right
                    visible_chars = int(text_width * progress)
                    display_text = text[:visible_chars]
                elif direction == "left":
                    # Slide from right to left
                    visible_chars = int(text_width * progress)
                    display_text = text[-visible_chars:] if visible_chars > 0 else ""
                else:
                    display_text = text

                live.update(Text(display_text, style="bold cyan"))
                time.sleep(frame_delay)

    def glitch_effect(
        self,
        text: str,
        *,
        duration: float = 1.0,
        glitch_intensity: float = 0.3,
    ) -> None:
        """
        Glitch effect - random character replacement

        Args:
            text: Text to glitch
            duration: Effect duration
            glitch_intensity: Intensity of glitch (0-1)
        """
        glitch_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?/~`"
        start_time = time.time()

        while time.time() - start_time < duration:
            glitched = list(text)

            # Random character replacement
            for i in range(len(glitched)):
                if random.random() < glitch_intensity:
                    glitched[i] = random.choice(glitch_chars)

            self.console.clear()
            self.console.print("".join(glitched), style="bold red")
            time.sleep(0.05)

        # Show final text
        self.console.clear()
        self.console.print(text, style="bold green")


class ProgressAnimations:
    """
    Advanced progress bar animations
    """

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def neon_progress(
        self,
        total: int,
        *,
        task_name: str = "Processing",
        width: int = 40,
    ) -> "NeonProgressBar":
        """
        Create neon-style progress bar

        Args:
            total: Total iterations
            task_name: Task description
            width: Bar width

        Returns:
            NeonProgressBar context manager
        """
        return NeonProgressBar(
            total=total,
            task_name=task_name,
            width=width,
            console=self.console,
        )

    def matrix_progress(
        self,
        total: int,
        *,
        task_name: str = "Loading",
        width: int = 40,
    ) -> "MatrixProgressBar":
        """
        Create Matrix-style progress bar

        Args:
            total: Total iterations
            task_name: Task description
            width: Bar width

        Returns:
            MatrixProgressBar context manager
        """
        return MatrixProgressBar(
            total=total,
            task_name=task_name,
            width=width,
            console=self.console,
        )


class NeonProgressBar:
    """Neon-style progress bar with glow effect"""

    def __init__(
        self,
        total: int,
        task_name: str,
        width: int,
        console: Console,
    ):
        self.total = total
        self.current = 0
        self.task_name = task_name
        self.width = width
        self.console = console

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.console.print()  # Final newline

    def update(self, amount: int = 1):
        """Update progress"""
        self.current += amount
        self._render()

    def _render(self):
        """Render progress bar"""
        percentage = (self.current / self.total) * 100 if self.total > 0 else 0
        filled = int((self.current / self.total) * self.width) if self.total > 0 else 0

        # Create neon bar
        bar_filled = "█" * filled
        bar_empty = "░" * (self.width - filled)

        # Render with glow effect (using color)
        self.console.print(
            f"\r[cyan]{self.task_name}[/cyan] "
            f"[magenta bold]{bar_filled}[/magenta bold]"
            f"[dim]{bar_empty}[/dim] "
            f"[green]{percentage:5.1f}%[/green]",
            end="",
        )


class MatrixProgressBar:
    """Matrix-style progress bar with digital rain"""

    def __init__(
        self,
        total: int,
        task_name: str,
        width: int,
        console: Console,
    ):
        self.total = total
        self.current = 0
        self.task_name = task_name
        self.width = width
        self.console = console
        self.matrix_chars = "01"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.console.print()  # Final newline

    def update(self, amount: int = 1):
        """Update progress"""
        self.current += amount
        self._render()

    def _render(self):
        """Render progress bar"""
        percentage = (self.current / self.total) * 100 if self.total > 0 else 0
        filled = int((self.current / self.total) * self.width) if self.total > 0 else 0

        # Create matrix-style bar
        bar_filled = "".join(random.choice(self.matrix_chars) for _ in range(filled))
        bar_empty = " " * (self.width - filled)

        # Render
        self.console.print(
            f"\r[green]{self.task_name}[/green] "
            f"[green bold]{bar_filled}[/green bold]"
            f"{bar_empty} "
            f"[yellow]{percentage:5.1f}%[/yellow]",
            end="",
        )


class ParticleEffects:
    """
    Particle effect animations for visual flair
    """

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def explosion(
        self,
        center_x: int = 40,
        center_y: int = 12,
        *,
        duration: float = 2.0,
        fps: int = 20,
    ) -> None:
        """
        Explosion particle effect

        Args:
            center_x: X coordinate of center
            center_y: Y coordinate of center
            duration: Animation duration
            fps: Frames per second
        """
        particles = []

        # Create particles
        num_particles = 50
        for _ in range(num_particles):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.5, 2.0)
            particles.append(
                {
                    "x": float(center_x),
                    "y": float(center_y),
                    "vx": math.cos(angle) * speed,
                    "vy": math.sin(angle) * speed,
                    "char": random.choice("✦✧✶✸✹✺"),
                    "lifetime": random.uniform(0.5, duration),
                    "age": 0.0,
                }
            )

        frame_delay = 1.0 / fps
        start_time = time.time()

        with Live(console=self.console, refresh_per_second=fps) as live:
            while time.time() - start_time < duration:
                # Update particles
                for p in particles:
                    p["x"] += p["vx"]
                    p["y"] += p["vy"]
                    p["vy"] += 0.1  # Gravity
                    p["age"] += frame_delay

                # Filter alive particles
                alive_particles = [p for p in particles if p["age"] < p["lifetime"]]

                # Render
                grid = [[" " for _ in range(80)] for _ in range(24)]
                for p in alive_particles:
                    x, y = int(p["x"]), int(p["y"])
                    if 0 <= x < 80 and 0 <= y < 24:
                        grid[y][x] = p["char"]

                frame_text = "\n".join("".join(row) for row in grid)
                live.update(Text(frame_text, style="yellow"))

                time.sleep(frame_delay)


# ═══════════════════════════════════════════════════════════════════════════
# BREATHING MASCOT - Subtle animated mascot for loading/waiting
# ═══════════════════════════════════════════════════════════════════════════


class BreathingMascot:
    """
    Mascot avec animation de respiration subtile.

    Utilisation:
        with BreathingMascot("Chargement...") as mascot:
            # votre code long ici
            mascot.update_message("Progression...")

        # Ou en mode streaming:
        mascot = BreathingMascot("Réflexion...")
        mascot.start()
        # ... streaming ...
        mascot.stop()
    """

    # Frames de respiration subtils (yeux qui clignent, léger mouvement)
    BREATHING_FRAMES = [
        # Frame 1 - Normal
        """  (=^･ω･^=)  """,
        # Frame 2 - Léger clignement
        """  (=^-ω-^=)  """,
        # Frame 3 - Normal
        """  (=^･ω･^=)  """,
        # Frame 4 - Regard côté
        """  (=^･ω･^=) """,
        # Frame 5 - Normal
        """  (=^･ω･^=)  """,
        # Frame 6 - Léger clignement
        """  (=^-ω-^=)  """,
    ]

    # Mini frames pour inline
    MINI_BREATHING = [
        "(=^･ω･^=)",
        "(=^-ω-^=)",
        "(=^･ω･^=)",
        "(=^･ω･^=)",
    ]

    # Working frames (pour tâches actives)
    WORKING_FRAMES = [
        """  (=^･ｪ･^=)⚙️ """,
        """  (=^･ｪ･^=) ⚙️""",
        """  (=^･ｪ･^=)  ⚙️""",
        """  (=^･ｪ･^=) ⚙️""",
    ]

    # Thinking frames
    THINKING_FRAMES = [
        """  (=^･◔･^=)💭""",
        """  (=^◔･^=) 💭""",
        """  (=^･◔^=) 💭""",
        """  (=^◔･^=) 💭""",
    ]

    def __init__(
        self,
        message: str = "",
        *,
        mode: str = "breathing",  # breathing, working, thinking
        style: str = "mini",  # mini, full
        console: Console | None = None,
        fps: int = 4,  # Lent pour être subtil
    ):
        """
        Args:
            message: Message à afficher
            mode: Type d'animation (breathing, working, thinking)
            style: mini (inline) ou full (multiline)
            console: Rich Console
            fps: Images par seconde (4 = subtil)
        """
        self.message = message
        self.mode = mode
        self.style = style
        self.console = console or Console()
        self.fps = fps
        self.frame_index = 0
        self._live = None
        self._running = False

        # Sélectionner les frames selon le mode
        if mode == "working":
            self.frames = (
                self.WORKING_FRAMES
                if style == "full"
                else ["(=^･ｪ･^=)⚙️ ", "(=^･ｪ･^=) ⚙️", "(=^･ｪ･^=)  ⚙️", "(=^･ｪ･^=) ⚙️"]
            )
        elif mode == "thinking":
            self.frames = (
                self.THINKING_FRAMES
                if style == "full"
                else ["(=^･◔･^=)💭", "(=^◔･^=) 💭", "(=^･◔^=) 💭", "(=^◔･^=) 💭"]
            )
        else:  # breathing
            self.frames = self.BREATHING_FRAMES if style == "full" else self.MINI_BREATHING

    def _get_frame(self) -> str:
        """Obtenir le frame actuel avec message."""
        frame = self.frames[self.frame_index % len(self.frames)]
        self.frame_index += 1

        if self.message:
            return f"{frame} {self.message}"
        return frame

    def _render(self) -> Panel:
        """Rendre le frame actuel dans un Panel."""
        frame_text = self._get_frame()
        return Panel(
            Text(frame_text, style="cyan"),
            border_style="dim cyan",
            padding=(0, 1),
        )

    def update_message(self, message: str):
        """Mettre à jour le message pendant l'animation."""
        self.message = message

    def __enter__(self):
        """Démarrer l'animation."""
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=self.fps,
            transient=True,
        )
        self._live.__enter__()
        self._running = True
        return self

    def __exit__(self, *args):
        """Arrêter l'animation."""
        if self._live:
            self._live.__exit__(*args)
        self._running = False

    def start(self):
        """Démarrer manuellement (pour streaming)."""
        self.__enter__()
        return self

    def stop(self):
        """Arrêter manuellement."""
        self.__exit__(None, None, None)

    def tick(self):
        """Avancer d'un frame (pour streaming manuel)."""
        if self._live and self._running:
            self._live.update(self._render())


class MascotSpinner:
    """
    Spinner avec mascotte intégrée - version minimale.

    Utilisation:
        with MascotSpinner("Chargement du modèle...") as spinner:
            load_model()
    """

    SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(
        self,
        message: str = "Chargement...",
        *,
        console: Console | None = None,
        mascot: str = "(=^･ω･^=)",
    ):
        self.message = message
        self.console = console or Console()
        self.mascot = mascot
        self.frame_index = 0
        self._live = None

    def _render(self) -> Text:
        """Rendre le spinner avec mascotte."""
        spinner = self.SPINNER_CHARS[self.frame_index % len(self.SPINNER_CHARS)]
        self.frame_index += 1
        return Text(f"{self.mascot} {spinner} {self.message}", style="cyan")

    def __enter__(self):
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=10,
            transient=True,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        if self._live:
            self._live.__exit__(*args)

    def update(self, message: str):
        """Mettre à jour le message."""
        self.message = message
        if self._live:
            self._live.update(self._render())


class MascotProgressBar:
    """
    Barre de progression avec mascotte qui change d'expression.

    Utilisation:
        with MascotProgressBar(total=100, task="Téléchargement") as bar:
            for i in range(100):
                bar.update(1)
    """

    # Expressions selon le pourcentage
    EXPRESSIONS = {
        0: "(=^･ω･^=)",  # Début - neutre
        25: "(=^･ω･^=)✨",  # 25% - content
        50: "(=^◡^=)✨",  # 50% - souriant
        75: "(=^▽^=)🎉",  # 75% - excité
        100: "(=^◡^=)🎊",  # 100% - célébration
    }

    def __init__(
        self,
        total: int,
        *,
        task: str = "Progression",
        width: int = 30,
        console: Console | None = None,
    ):
        self.total = total
        self.current = 0
        self.task = task
        self.width = width
        self.console = console or Console()
        self._live = None

    def _get_expression(self) -> str:
        """Obtenir l'expression selon le pourcentage."""
        pct = int((self.current / self.total) * 100) if self.total > 0 else 0

        # Trouver l'expression la plus proche
        expression = self.EXPRESSIONS[0]
        for threshold, expr in self.EXPRESSIONS.items():
            if pct >= threshold:
                expression = expr
        return expression

    def _render(self) -> Panel:
        """Rendre la barre de progression."""
        pct = (self.current / self.total) * 100 if self.total > 0 else 0
        filled = int((self.current / self.total) * self.width) if self.total > 0 else 0

        bar = "█" * filled + "░" * (self.width - filled)
        expression = self._get_expression()

        content = Text()
        content.append(f"{expression}\n", style="bold")
        content.append(f"{self.task}: ", style="cyan")
        content.append(bar, style="magenta")
        content.append(f" {pct:.0f}%", style="green")

        return Panel(content, border_style="dim cyan", padding=(0, 1))

    def __enter__(self):
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=10,
            transient=True,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        if self._live:
            # Afficher état final
            self._live.update(self._render())
            self._live.__exit__(*args)

    def update(self, amount: int = 1):
        """Mettre à jour la progression."""
        self.current = min(self.current + amount, self.total)
        if self._live:
            self._live.update(self._render())


def demo_animations():
    """Demonstration of all animation effects"""
    console = Console()

    console.print("\n[bold cyan]═══ Text Animations Demo ═══[/bold cyan]\n")

    # Typewriter
    console.print("[yellow]Typewriter effect:[/yellow]")
    text_anim = TextAnimations(console)
    text_anim.typewriter("Tawiza v2.0 - Machine Learning Platform", delay=0.03)

    time.sleep(1)

    # Slide in
    console.print("\n[yellow]Slide in effect:[/yellow]")
    text_anim.slide_in("→ Welcome to the future of AI ←", duration=1.5)

    time.sleep(1)

    # Progress bars
    console.print("\n[yellow]Neon progress bar:[/yellow]")
    progress_anim = ProgressAnimations(console)
    with progress_anim.neon_progress(100, task_name="Training Model") as bar:
        for _i in range(100):
            bar.update(1)
            time.sleep(0.02)

    console.print("\n[bold green]✓ Animation demo complete![/bold green]\n")


if __name__ == "__main__":
    demo_animations()
