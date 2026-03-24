"""Mini-jeux d'attente avec la mascotte."""

import random
import time
from dataclasses import dataclass, field

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


@dataclass
class CatchGame:
    """Jeu où la mascotte attrape des objets."""

    width: int = 40
    mascot_pos: int = field(default_factory=lambda: 20)
    score: int = 0
    objects: list[dict] = field(default_factory=list)

    MASCOT = "(=^◡^=)"
    OBJECTS = ["⭐", "🐟", "💎", "🎁", "❤️"]

    def spawn_object(self):
        """Fait apparaître un objet."""
        if random.random() > 0.7:
            self.objects.append(
                {
                    "x": random.randint(2, self.width - 2),
                    "y": 0,
                    "char": random.choice(self.OBJECTS),
                }
            )

    def update(self):
        """Met à jour les positions."""
        # Déplacer objets vers le bas
        for obj in self.objects:
            obj["y"] += 1

        # Vérifier captures
        for obj in self.objects[:]:
            if obj["y"] >= 4 and abs(obj["x"] - self.mascot_pos) < 4:
                self.score += 1
                self.objects.remove(obj)
            elif obj["y"] > 5:
                self.objects.remove(obj)

        # Déplacer mascotte aléatoirement
        self.mascot_pos += random.choice([-2, -1, 0, 1, 2])
        self.mascot_pos = max(4, min(self.width - 4, self.mascot_pos))

        self.spawn_object()

    def render_frame(self) -> str:
        """Rend une frame du jeu."""
        lines = []

        # Zone de jeu
        for y in range(5):
            line = [" "] * self.width
            for obj in self.objects:
                if obj["y"] == y and 0 <= obj["x"] < self.width:
                    line[obj["x"]] = obj["char"]
            lines.append("".join(line))

        # Mascotte
        mascot_line = [" "] * self.width
        pos = max(0, self.mascot_pos - 3)
        mascot_str = self.MASCOT
        for i, c in enumerate(mascot_str):
            if pos + i < self.width:
                mascot_line[pos + i] = c
        lines.append("".join(mascot_line))

        # Score
        lines.append(f"{'─' * self.width}")
        lines.append(f" Score: {self.score} ⭐")

        return "\n".join(lines)


class TypingGame:
    """Jeu de texte défilant pendant l'attente."""

    MESSAGES = [
        "Chargement des neurones... 🧠",
        "Compilation des rêves... ✨",
        "Optimisation du bonheur... 💕",
        "Calcul de l'infini... ∞",
        "Téléchargement de patience... ⏳",
    ]

    def __init__(self):
        self.current_msg = random.choice(self.MESSAGES)
        self.pos = 0

    def get_frame(self) -> str:
        """Retourne le message avec effet machine à écrire."""
        self.pos = min(self.pos + 1, len(self.current_msg))
        if self.pos == len(self.current_msg):
            self.current_msg = random.choice(self.MESSAGES)
            self.pos = 0
        return self.current_msg[: self.pos] + "▌"


class WaitingGames:
    """Gestionnaire de mini-jeux d'attente."""

    def __init__(self, console: Console = None):
        self.console = console or Console()

    def play_catch(self, duration: float = 10.0, title: str = "En attente..."):
        """Lance le jeu de catch pendant l'attente."""
        game = CatchGame()
        start = time.time()

        with Live(console=self.console, refresh_per_second=4) as live:
            while time.time() - start < duration:
                game.update()
                panel = Panel(
                    game.render_frame(),
                    title=f"[bold cyan]{title}[/bold cyan]",
                    subtitle=f"[dim]{duration - (time.time() - start):.0f}s[/dim]",
                    border_style="cyan",
                )
                live.update(panel)
                time.sleep(0.25)

        return game.score

    def typing_effect(self, duration: float = 5.0):
        """Effet machine à écrire pendant l'attente."""
        game = TypingGame()
        start = time.time()

        with Live(console=self.console, refresh_per_second=10) as live:
            while time.time() - start < duration:
                live.update(Text(f"  (=^･ω･^=) {game.get_frame()}"))
                time.sleep(0.1)
