"""Widget mascotte avec affichage GPU temps réel."""
import threading
import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from .gpu_monitor import GPULocation, GPUMonitor, GPUStatus
from .mascot_config import MascotConfig
from .mascot_library import get_mascot_for_style


class MascotGPUWidget:
    """Widget combinant mascotte et statut GPU."""

    def __init__(self, config: MascotConfig | None = None):
        self.config = config or MascotConfig.load()
        self.gpu_monitor = GPUMonitor()
        self.faces = get_mascot_for_style(self.config.style)
        self.console = Console()
        self._stop_event = threading.Event()

    def get_gpu_bar(self, status: GPUStatus) -> str:
        """Crée une barre de progression GPU ASCII."""
        if not status.available:
            return "GPU: [dim]Non disponible[/dim]"

        percent = status.memory_percent
        bar_width = 20
        filled = int(bar_width * percent / 100)
        empty = bar_width - filled

        # Couleur selon utilisation
        if percent < 50:
            color = "green"
        elif percent < 80:
            color = "yellow"
        else:
            color = "red"

        bar = f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"
        location = "🖥️" if status.location == GPULocation.HOST else "🖧 VM"

        return f"{location} GPU: {bar} {percent:.1f}% | {status.temperature}°C"

    def render(self, message: str = "", emotion: str = "happy") -> Panel:
        """Rend le widget mascotte + GPU."""
        status = self.gpu_monitor.get_status()

        # Choisir expression selon statut GPU
        if not status.available:
            face = self.faces.sad
        elif status.memory_percent > 90:
            face = self.faces.working
        elif status.utilization > 80:
            face = self.faces.excited
        else:
            face = getattr(self.faces, emotion, self.faces.happy)

        # Construire le contenu
        content = Text()
        content.append(f"\n  {face}\n\n", style=f"bold {self.config.color}")

        if message:
            content.append(f"  {message}\n\n", style="italic")

        content.append(f"  {self.get_gpu_bar(status)}\n", style="")

        return Panel(
            content,
            title=f"[bold]{self.config.name}[/bold]",
            border_style=self.config.color,
        )

    def live_display(self, duration: int = 10, message: str = "Surveillance GPU..."):
        """Affichage live avec mise à jour GPU."""
        with Live(self.render(message), refresh_per_second=1, console=self.console) as live:
            for _ in range(duration):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
                live.update(self.render(message))

    def stop(self):
        """Arrête l'affichage live."""
        self._stop_event.set()
