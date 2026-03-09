"""Service Status widget."""


from textual.widgets import Static


class ServiceStatusWidget(Static):
    """Widget showing service status list."""

    DEFAULT_CSS = """
    ServiceStatusWidget {
        height: auto;
        padding: 1;
    }
    """

    def __init__(self, services: dict[str, str] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._services = services or {}

    def render(self) -> str:
        """Render service status list."""
        if not self._services:
            return "[dim]No services configured[/]"

        lines = []
        for name, status in self._services.items():
            if status in ("ok", "running", "online", "active"):
                icon = "[green]●[/]"
            elif status in ("starting", "loading", "connecting"):
                icon = "[yellow]◐[/]"
            elif status in ("ready", "standby"):
                icon = "[cyan]○[/]"
            else:
                icon = "[red]○[/]"

            lines.append(f"{icon} {name}")

        return "\n".join(lines)

    def update_services(self, services: dict[str, str]) -> None:
        """Update service statuses."""
        self._services = services
        self.refresh()

    def set_service_status(self, name: str, status: str) -> None:
        """Update a single service status."""
        self._services[name] = status
        self.refresh()

    def get_services(self) -> dict[str, str]:
        """Get current services dict."""
        return self._services.copy()


class ServiceStatusCompact(Static):
    """Compact single-line service status."""

    DEFAULT_CSS = """
    ServiceStatusCompact {
        height: 1;
        padding: 0 1;
    }
    """

    def __init__(self, name: str, status: str = "unknown", **kwargs):
        super().__init__(**kwargs)
        self.service_name = name
        self.status = status

    def render(self) -> str:
        """Render single service status."""
        if self.status in ("ok", "running", "online", "active"):
            icon = "[green]●[/]"
            status_text = f"[green]{self.status}[/]"
        elif self.status in ("starting", "loading", "connecting"):
            icon = "[yellow]◐[/]"
            status_text = f"[yellow]{self.status}[/]"
        elif self.status in ("ready", "standby"):
            icon = "[cyan]○[/]"
            status_text = f"[cyan]{self.status}[/]"
        else:
            icon = "[red]○[/]"
            status_text = f"[red]{self.status}[/]"

        return f"{icon} {self.service_name}: {status_text}"

    def set_status(self, status: str) -> None:
        """Update the status."""
        self.status = status
        self.refresh()
