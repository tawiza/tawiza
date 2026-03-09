"""API client for Tawiza CLI."""

import os
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel

console = Console()


class APIConnectionError(Exception):
    """Raised when the API backend is not reachable."""
    pass


class APIClient:
    """HTTP client for Tawiza API."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        """Initialize API client.

        Args:
            base_url: Base URL for API (default: http://localhost:8000)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("TAWIZA_API_URL", "http://localhost:8000")
        self.timeout = httpx.Timeout(timeout, connect=10.0)
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    def _handle_connection_error(self, e: Exception, endpoint: str):
        """Handle connection errors with helpful message."""
        console.print()
        console.print(Panel(
            f"[red]❌ Impossible de se connecter au backend API[/red]\n\n"
            f"[yellow]URL:[/yellow] {self.base_url}{endpoint}\n\n"
            f"[cyan]Solutions:[/cyan]\n"
            f"  1. Démarrer le backend: [green]tawiza system start[/green]\n"
            f"  2. Vérifier le statut: [green]tawiza system status[/green]\n"
            f"  3. Définir une URL personnalisée: [dim]export TAWIZA_API_URL=http://...[/dim]",
            title="🔌 Backend Non Disponible",
            border_style="red"
        ))
        raise APIConnectionError(f"Backend not reachable at {self.base_url}")

    def _handle_404_error(self, endpoint: str):
        """Handle 404 errors with helpful message."""
        console.print()
        console.print(Panel(
            f"[yellow]⚠️ Endpoint non disponible[/yellow]\n\n"
            f"[dim]URL:[/dim] {self.base_url}{endpoint}\n\n"
            f"[cyan]Cette fonctionnalité nécessite:[/cyan]\n"
            f"  • Le backend FastAPI complet\n"
            f"  • Les routes API correspondantes\n\n"
            f"[green]Alternatives disponibles:[/green]\n"
            f"  • [dim]tawiza models list[/dim] - Modèles Ollama\n"
            f"  • [dim]tawiza system status[/dim] - Statut système\n"
            f"  • [dim]tawiza finetune list[/dim] - Jobs de fine-tuning",
            title="📡 Endpoint Non Trouvé",
            border_style="yellow"
        ))

    def get(self, endpoint: str, **kwargs) -> dict[str, Any]:
        """GET request.

        Args:
            endpoint: API endpoint path
            **kwargs: Additional request parameters

        Returns:
            Response JSON data

        Raises:
            httpx.HTTPError: On request failure
            APIConnectionError: When backend is not reachable
        """
        try:
            response = self.client.get(endpoint, **kwargs)
            if response.status_code == 404:
                self._handle_404_error(endpoint)
                return {"items": [], "total": 0}
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            self._handle_connection_error(e, endpoint)
        except httpx.ConnectTimeout as e:
            self._handle_connection_error(e, endpoint)

    def post(self, endpoint: str, **kwargs) -> dict[str, Any]:
        """POST request.

        Args:
            endpoint: API endpoint path
            **kwargs: Additional request parameters

        Returns:
            Response JSON data

        Raises:
            httpx.HTTPError: On request failure
            APIConnectionError: When backend is not reachable
        """
        try:
            response = self.client.post(endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            self._handle_connection_error(e, endpoint)
        except httpx.ConnectTimeout as e:
            self._handle_connection_error(e, endpoint)

    def delete(self, endpoint: str, **kwargs) -> dict[str, Any]:
        """DELETE request.

        Args:
            endpoint: API endpoint path
            **kwargs: Additional request parameters

        Returns:
            Response JSON data

        Raises:
            httpx.HTTPError: On request failure
            APIConnectionError: When backend is not reachable
        """
        try:
            response = self.client.delete(endpoint, **kwargs)
            response.raise_for_status()
            if response.text:
                return response.json()
            return {"success": True}
        except httpx.ConnectError as e:
            self._handle_connection_error(e, endpoint)
        except httpx.ConnectTimeout as e:
            self._handle_connection_error(e, endpoint)

    def health_check(self) -> bool:
        """Check if API is reachable.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            response = self.client.get("/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    def close(self):
        """Close HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit."""
        self.close()


# Global API client instance
api = APIClient()
