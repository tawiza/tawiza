#!/usr/bin/env python3
"""
Advanced Animations for CLI - Phase 7
Transitions, loading animations, effects visuels
"""

import itertools
import random
import time

from rich import box
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.text import Text

console = Console()


# ===== CUSTOM SPINNERS =====


class CustomSpinners:
    """Collection de spinners personnalisés"""

    DOTS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    BOUNCE = ["⠁", "⠂", "⠄", "⡀", "⢀", "⠠", "⠐", "⠈"]
    ARROW = ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"]
    SQUARE = ["◰", "◳", "◲", "◱"]
    CIRCLE = ["◐", "◓", "◑", "◒"]
    PULSE = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    GROWING = ["▁", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃"]
    ROCKET = ["🚀", "🚀 ", "🚀  ", "🚀   ", "    🚀", "   🚀", "  🚀", " 🚀"]
    FIRE = ["🔥", "🔥 ", "🔥  ", "   🔥", "  🔥", " 🔥"]
    STARS = ["✦", "✧", "✦", "✧"]
    LOADING = ["[    ]", "[=   ]", "[==  ]", "[=== ]", "[====]", "[ ===]", "[  ==]", "[   =]"]

    @staticmethod
    def animate_spinner(
        spinner: list[str], message: str, duration: float = 3.0, color: str = "cyan"
    ):
        """Animer un spinner avec message"""
        frames = itertools.cycle(spinner)
        end_time = time.time() + duration

        try:
            with Live(console=console, refresh_per_second=10) as live:
                while time.time() < end_time:
                    frame = next(frames)
                    text = Text(f"{frame} {message}", style=color)
                    live.update(text)
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass


# ===== TRANSITIONS =====


class Transitions:
    """Effets de transition entre écrans"""

    @staticmethod
    def fade_in(content: str, duration: float = 1.0, steps: int = 20):
        """Fade in effect"""
        console.clear()

        for i in range(steps + 1):
            opacity = i / steps
            color_value = int(255 * opacity)

            # Créer un texte avec opacité simulée
            styled_text = Text(content)
            styled_text.stylize(f"rgb({color_value},{color_value},{color_value})")

            console.clear()
            console.print(styled_text)
            time.sleep(duration / steps)

    @staticmethod
    def fade_out(content: str, duration: float = 1.0, steps: int = 20):
        """Fade out effect"""
        for i in range(steps, -1, -1):
            opacity = i / steps
            color_value = int(255 * opacity)

            styled_text = Text(content)
            styled_text.stylize(f"rgb({color_value},{color_value},{color_value})")

            console.clear()
            console.print(styled_text)
            time.sleep(duration / steps)

        console.clear()

    @staticmethod
    def slide_in(content: str, direction: str = "left", duration: float = 1.0, steps: int = 20):
        """Slide in effect"""
        console.clear()
        lines = content.split("\n")
        width = console.width

        for i in range(steps + 1):
            console.clear()
            progress = i / steps

            if direction == "left":
                offset = int(width * (1 - progress))
                for line in lines:
                    console.print(" " * offset + line)
            elif direction == "right":
                offset = int(width * progress)
                for line in lines:
                    console.print(" " * offset + line)
            elif direction == "top":
                visible_lines = int(len(lines) * progress)
                for line in lines[:visible_lines]:
                    console.print(line)
            elif direction == "bottom":
                visible_lines = int(len(lines) * progress)
                start_line = len(lines) - visible_lines
                for line in lines[start_line:]:
                    console.print(line)

            time.sleep(duration / steps)

    @staticmethod
    def wipe(content: str, duration: float = 1.0, steps: int = 20):
        """Wipe effect (left to right)"""
        console.clear()
        lines = content.split("\n")
        max_length = max(len(line) for line in lines)

        for i in range(steps + 1):
            console.clear()
            visible_chars = int(max_length * (i / steps))

            for line in lines:
                visible_part = line[:visible_chars]
                console.print(visible_part)

            time.sleep(duration / steps)


# ===== LOADING ANIMATIONS =====


class LoadingAnimations:
    """Animations de chargement avancées"""

    @staticmethod
    def dots_loading(message: str = "Loading", duration: float = 3.0):
        """Animation avec points qui s'accumulent"""
        end_time = time.time() + duration

        try:
            with Live(console=console, refresh_per_second=4) as live:
                dots = 0
                while time.time() < end_time:
                    dots_str = "." * (dots % 4)
                    text = Text(f"{message}{dots_str}", style="cyan")
                    live.update(text)
                    dots += 1
                    time.sleep(0.25)
        except KeyboardInterrupt:
            pass

    @staticmethod
    def progress_bar_smooth(message: str = "Processing", total: int = 100, duration: float = 5.0):
        """Progress bar avec animation smooth"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(message, total=total)

            steps = 50
            for _i in range(steps):
                progress.update(task, advance=total / steps)
                time.sleep(duration / steps)

    @staticmethod
    def wave_loading(message: str = "Loading", duration: float = 3.0):
        """Animation de vague"""
        wave_chars = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        end_time = time.time() + duration

        try:
            with Live(console=console, refresh_per_second=10) as live:
                offset = 0
                while time.time() < end_time:
                    wave = ""
                    for i in range(10):
                        char_index = (i + offset) % len(wave_chars)
                        wave += wave_chars[char_index]

                    text = Text(f"{message} {wave}", style="cyan")
                    live.update(text)

                    offset = (offset + 1) % len(wave_chars)
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass

    @staticmethod
    def matrix_loading(duration: float = 3.0):
        """Animation style Matrix"""
        chars = "01"
        width = 20
        height = 5
        end_time = time.time() + duration

        try:
            with Live(console=console, refresh_per_second=10) as live:
                while time.time() < end_time:
                    lines = []
                    for _ in range(height):
                        line = "".join(random.choice(chars) for _ in range(width))
                        lines.append(Text(line, style="green"))

                    live.update(Panel("\n".join(str(line) for line in lines)))
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass


# ===== EFFECTS VISUELS =====


class VisualEffects:
    """Effets visuels pour success/error/info"""

    @staticmethod
    def success_effect(message: str, duration: float = 2.0):
        """Effet de succès avec animation"""
        # Animation: ✓ qui apparaît avec flash vert
        frames = [
            Text("   ", style="green"),
            Text(" ✓ ", style="bold green"),
            Text("✓✓✓", style="bold bright_green"),
            Text(" ✓ ", style="bold green"),
            Text(" ✓ ", style="green"),
        ]

        try:
            with Live(console=console, refresh_per_second=5) as live:
                for frame in frames:
                    content = Text.assemble(frame, " ", Text(message, style="green"))
                    panel = Panel(Align.center(content), border_style="green", box=box.DOUBLE)
                    live.update(panel)
                    time.sleep(duration / len(frames))
        except KeyboardInterrupt:
            pass

    @staticmethod
    def error_effect(message: str, duration: float = 2.0):
        """Effet d'erreur avec animation"""
        # Animation: ✗ qui clignote en rouge
        frames = [
            Text("   ", style="red"),
            Text(" ✗ ", style="bold red"),
            Text("✗✗✗", style="bold bright_red"),
            Text(" ✗ ", style="bold red"),
            Text(" ✗ ", style="red"),
        ]

        try:
            with Live(console=console, refresh_per_second=5) as live:
                for frame in frames:
                    content = Text.assemble(frame, " ", Text(message, style="red"))
                    panel = Panel(Align.center(content), border_style="red", box=box.DOUBLE)
                    live.update(panel)
                    time.sleep(duration / len(frames))
        except KeyboardInterrupt:
            pass

    @staticmethod
    def info_effect(message: str, duration: float = 2.0):
        """Effet d'information avec animation"""
        # Animation: ℹ qui pulse en bleu
        frames = [
            Text("   ", style="blue"),
            Text(" ℹ ", style="bold blue"),
            Text("ℹℹℹ", style="bold bright_blue"),
            Text(" ℹ ", style="bold blue"),
            Text(" ℹ ", style="blue"),
        ]

        try:
            with Live(console=console, refresh_per_second=5) as live:
                for frame in frames:
                    content = Text.assemble(frame, " ", Text(message, style="blue"))
                    panel = Panel(Align.center(content), border_style="blue", box=box.ROUNDED)
                    live.update(panel)
                    time.sleep(duration / len(frames))
        except KeyboardInterrupt:
            pass

    @staticmethod
    def warning_effect(message: str, duration: float = 2.0):
        """Effet d'avertissement avec animation"""
        # Animation: ⚠ qui clignote en jaune
        frames = [
            Text("   ", style="yellow"),
            Text(" ⚠ ", style="bold yellow"),
            Text("⚠⚠⚠", style="bold bright_yellow"),
            Text(" ⚠ ", style="bold yellow"),
            Text(" ⚠ ", style="yellow"),
        ]

        try:
            with Live(console=console, refresh_per_second=5) as live:
                for frame in frames:
                    content = Text.assemble(frame, " ", Text(message, style="yellow"))
                    panel = Panel(Align.center(content), border_style="yellow", box=box.ROUNDED)
                    live.update(panel)
                    time.sleep(duration / len(frames))
        except KeyboardInterrupt:
            pass


# ===== ANIMATED PROGRESS =====


class AnimatedProgress:
    """Progress bars avec animations personnalisées"""

    @staticmethod
    def fire_progress(total: int = 100, duration: float = 5.0):
        """Progress bar avec effet de feu"""
        fire_chars = ["🔥", "🔥🔥", "🔥🔥🔥"]

        with Progress(console=console) as progress:
            task = progress.add_task("[red]Heating up...", total=total)

            steps = 50
            for i in range(steps):
                # Ajouter un effet de feu qui grandit
                fire = fire_chars[min(i // (steps // 3), len(fire_chars) - 1)]
                progress.update(
                    task, advance=total / steps, description=f"[red]Heating up... {fire}"
                )
                time.sleep(duration / steps)

    @staticmethod
    def rocket_progress(total: int = 100, duration: float = 5.0):
        """Progress bar avec fusée"""
        with Progress(console=console) as progress:
            task = progress.add_task("[cyan]Launching 🚀", total=total)

            steps = 50
            for _i in range(steps):
                progress.update(task, advance=total / steps)
                time.sleep(duration / steps)

    @staticmethod
    def rainbow_progress(total: int = 100, duration: float = 5.0):
        """Progress bar avec effet arc-en-ciel"""
        colors = ["red", "yellow", "green", "cyan", "blue", "magenta"]

        with Progress(console=console) as progress:
            task = progress.add_task("Processing", total=total)

            steps = 50
            for i in range(steps):
                color = colors[i % len(colors)]
                progress.update(
                    task, advance=total / steps, description=f"[{color}]Processing... ✨"
                )
                time.sleep(duration / steps)


# ===== CELEBRATION EFFECTS =====


class CelebrationEffects:
    """Effets de célébration pour les accomplissements"""

    @staticmethod
    def confetti(duration: float = 3.0):
        """Effet confetti"""
        confetti_chars = ["✦", "✧", "⭐", "🎉", "🎊", "✨"]
        width = console.width
        height = 10

        end_time = time.time() + duration

        try:
            with Live(console=console, refresh_per_second=10) as live:
                while time.time() < end_time:
                    lines = []
                    for _ in range(height):
                        line = ""
                        for _ in range(width):
                            if random.random() < 0.1:
                                char = random.choice(confetti_chars)
                                color = random.choice(["red", "yellow", "green", "cyan", "magenta"])
                                line += f"[{color}]{char}[/]"
                            else:
                                line += " "
                        lines.append(line)

                    live.update("\n".join(lines))
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass

    @staticmethod
    def fireworks(duration: float = 3.0):
        """Effet feux d'artifice"""
        firework_chars = ["✦", "✧", "*", "·"]
        colors = ["red", "yellow", "green", "cyan", "blue", "magenta", "white"]

        end_time = time.time() + duration

        try:
            with Live(console=console, refresh_per_second=10) as live:
                while time.time() < end_time:
                    # Create random fireworks
                    lines = [" " * console.width for _ in range(10)]

                    for _ in range(random.randint(3, 8)):
                        x = random.randint(0, console.width - 1)
                        y = random.randint(0, 9)
                        char = random.choice(firework_chars)
                        color = random.choice(colors)

                        line_list = list(lines[y])
                        line_list[x] = char
                        lines[y] = "".join(line_list)

                    # Apply colors
                    colored_lines = []
                    for line in lines:
                        colored_line = ""
                        for char in line:
                            if char != " ":
                                color = random.choice(colors)
                                colored_line += f"[{color}]{char}[/]"
                            else:
                                colored_line += char
                        colored_lines.append(colored_line)

                    live.update("\n".join(colored_lines))
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass

    @staticmethod
    def celebration_message(message: str, duration: float = 3.0):
        """Message de célébration avec animation"""
        emojis = ["🎉", "🎊", "✨", "🌟", "⭐", "💫"]

        try:
            with Live(console=console, refresh_per_second=10) as live:
                end_time = time.time() + duration

                while time.time() < end_time:
                    emoji_left = random.choice(emojis)
                    emoji_right = random.choice(emojis)
                    color = random.choice(
                        ["bright_yellow", "bright_green", "bright_cyan", "bright_magenta"]
                    )

                    content = Text.assemble(
                        Text(emoji_left + " ", style=color),
                        Text(message, style=f"bold {color}"),
                        Text(" " + emoji_right, style=color),
                    )

                    panel = Panel(Align.center(content), border_style=color, box=box.DOUBLE)

                    live.update(panel)
                    time.sleep(0.3)
        except KeyboardInterrupt:
            pass


# ===== DEMO =====

if __name__ == "__main__":
    console.clear()
    console.print(
        Panel(
            "[bold cyan]Advanced Animations Demo - Phase 7[/]\n[dim]Testing all animation types[/]",
            border_style="cyan",
        )
    )
    console.print()

    # Demo 1: Custom Spinners
    console.print("[bold]1. Custom Spinners[/]")
    console.print()

    CustomSpinners.animate_spinner(
        CustomSpinners.DOTS, "Loading with dots", duration=2, color="cyan"
    )
    console.print("[green]✓ Dots spinner complete[/]\n")

    CustomSpinners.animate_spinner(CustomSpinners.ROCKET, "Launching", duration=2, color="yellow")
    console.print("[green]✓ Rocket spinner complete[/]\n")

    time.sleep(1)

    # Demo 2: Transitions
    console.print("[bold]2. Transitions[/]")
    console.print()

    test_content = "Hello World!\nThis is a transition effect."
    console.print("[dim]Fade in...[/]")
    Transitions.fade_in(test_content, duration=1.5, steps=15)
    time.sleep(0.5)

    console.print("\n[dim]Fade out...[/]")
    Transitions.fade_out(test_content, duration=1.5, steps=15)

    console.print("[green]✓ Transitions complete[/]\n")
    time.sleep(1)

    # Demo 3: Loading Animations
    console.print("[bold]3. Loading Animations[/]")
    console.print()

    LoadingAnimations.dots_loading("Processing", duration=2)
    console.print("[green]✓ Dots loading complete[/]\n")

    LoadingAnimations.wave_loading("Loading data", duration=2)
    console.print("[green]✓ Wave loading complete[/]\n")

    time.sleep(1)

    # Demo 4: Visual Effects
    console.print("[bold]4. Visual Effects[/]")
    console.print()

    VisualEffects.success_effect("Operation completed successfully!", duration=2)
    time.sleep(0.5)

    VisualEffects.error_effect("An error occurred!", duration=2)
    time.sleep(0.5)

    VisualEffects.warning_effect("Warning: Check your configuration", duration=2)
    time.sleep(0.5)

    VisualEffects.info_effect("Information: System updated", duration=2)
    console.print("\n[green]✓ Visual effects complete[/]\n")

    time.sleep(1)

    # Demo 5: Animated Progress
    console.print("[bold]5. Animated Progress[/]")
    console.print()

    AnimatedProgress.fire_progress(total=100, duration=2)
    console.print("[green]✓ Fire progress complete[/]\n")

    AnimatedProgress.rainbow_progress(total=100, duration=2)
    console.print("[green]✓ Rainbow progress complete[/]\n")

    time.sleep(1)

    # Demo 6: Celebration
    console.print("[bold]6. Celebration Effects[/]")
    console.print()

    CelebrationEffects.celebration_message("🎉 DEMO COMPLETE! 🎉", duration=2)
    console.print()

    CelebrationEffects.confetti(duration=2)
    console.print()

    console.print(Panel("[bold green]All Animations Demo Complete![/]", border_style="green"))
