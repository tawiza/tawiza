"""Prototype: France Map with textual-image + GeoPandas.

This prototype validates the TUI v6 technical approach:
1. Load GeoJSON data for France departments
2. Generate choropleth map with matplotlib (to PNG buffer)
3. Display in Textual using textual-image widget

Run: python -m src.cli.v3.tui.prototypes.france_map_prototype
"""

import io
import random
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Label, Static
from textual_image.widget import Image

# Cache directory for GeoJSON files
GEO_CACHE = Path.home() / ".cache" / "tawiza" / "geo"


class FranceMapWidget(Static):
    """Widget displaying France choropleth map using textual-image."""

    DEFAULT_CSS = """
    FranceMapWidget {
        width: 1fr;
        height: auto;
        min-height: 30;
        padding: 1;
        border: solid $primary;
        background: $surface;
    }

    FranceMapWidget > .map-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    FranceMapWidget > Image {
        width: auto;
        height: auto;
    }
    """

    selected_department = reactive("")

    def __init__(self, data: dict[str, float] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._data = data or {}
        self._gdf: gpd.GeoDataFrame | None = None
        self._png_buffer: io.BytesIO | None = None

    def compose(self) -> ComposeResult:
        """Compose the map widget."""
        yield Label("[bold]🇫🇷 CARTE FRANCE - PROTOTYPE[/]", classes="map-title")
        # Image widget will be mounted after PNG generation
        yield Static("Chargement de la carte...", id="loading-placeholder")

    async def on_mount(self) -> None:
        """Load GeoJSON and generate initial map."""
        await self._load_and_render()

    async def _load_and_render(self) -> None:
        """Load GeoJSON data and render map."""
        # Load GeoJSON
        geojson_path = GEO_CACHE / "departements.geojson"
        if not geojson_path.exists():
            self.query_one("#loading-placeholder").update(
                "[red]GeoJSON not found![/]\n"
                f"Expected at: {geojson_path}"
            )
            return

        self._gdf = gpd.read_file(geojson_path)

        # Generate mock data if none provided
        if not self._data:
            self._data = {
                row["code"]: random.uniform(-0.3, 0.4)
                for _, row in self._gdf.iterrows()
            }

        # Generate PNG
        self._generate_map_png()

        # Replace placeholder with image
        placeholder = self.query_one("#loading-placeholder")
        await placeholder.remove()

        if self._png_buffer:
            image_widget = Image(self._png_buffer)
            await self.mount(image_widget)

    def _generate_map_png(self) -> None:
        """Generate choropleth map PNG to memory buffer."""
        if self._gdf is None:
            return

        # Create copy with data column
        gdf = self._gdf.copy()
        gdf["growth"] = gdf["code"].map(self._data).fillna(0)

        # Custom colormap: red (negative) -> yellow (zero) -> green (positive)
        colors = ["#8B0000", "#FF4444", "#FFFF00", "#44FF44", "#006400"]
        cmap = LinearSegmentedColormap.from_list("growth", colors)

        # Create figure with dark background
        fig, ax = plt.subplots(1, 1, figsize=(8, 8), facecolor="#1e1e1e")
        ax.set_facecolor("#1e1e1e")

        # Filter to metropolitan France (exclude overseas)
        metro_codes = [f"{i:02d}" for i in range(1, 96) if i != 20]  # No 20 (Corse split)
        metro_codes.extend(["2A", "2B"])  # Corse
        gdf_metro = gdf[gdf["code"].isin(metro_codes)]

        # Plot choropleth
        gdf_metro.plot(
            column="growth",
            ax=ax,
            cmap=cmap,
            vmin=-0.3,
            vmax=0.4,
            edgecolor="white",
            linewidth=0.3,
            legend=True,
            legend_kwds={
                "label": "Croissance (%)",
                "shrink": 0.6,
                "orientation": "horizontal",
                "pad": 0.02,
            },
        )

        # Style legend for dark mode
        cbar = ax.get_figure().axes[-1]
        cbar.tick_params(colors="white")
        cbar.set_xlabel("Croissance (%)", color="white")

        # Remove axes
        ax.axis("off")

        # Title
        ax.set_title(
            "Croissance Entreprises par Département",
            color="white",
            fontsize=12,
            fontweight="bold",
            pad=10,
        )

        # Save to buffer
        self._png_buffer = io.BytesIO()
        plt.savefig(
            self._png_buffer,
            format="png",
            dpi=100,
            bbox_inches="tight",
            facecolor="#1e1e1e",
            edgecolor="none",
        )
        self._png_buffer.seek(0)
        plt.close(fig)

    def update_data(self, data: dict[str, float]) -> None:
        """Update map data and re-render."""
        self._data = data
        self._generate_map_png()
        # Refresh image widget
        image_widget = self.query_one(Image, Image)
        if image_widget and self._png_buffer:
            image_widget.image = self._png_buffer


class MetricsPanel(Static):
    """Side panel showing department metrics."""

    DEFAULT_CSS = """
    MetricsPanel {
        width: 30;
        height: auto;
        padding: 1;
        border: solid $primary;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose metrics panel."""
        yield Label("[bold]📊 MÉTRIQUES[/]")
        yield Static("─" * 28)
        yield Static(
            "[dim]Cliquez sur un département[/]\n"
            "[dim]pour voir les détails...[/]",
            id="metrics-content"
        )

    def show_metrics(self, dept_code: str, growth: float) -> None:
        """Display metrics for a department."""
        sign = "+" if growth > 0 else ""
        color = "green" if growth > 0 else "red" if growth < 0 else "yellow"

        content = self.query_one("#metrics-content")
        content.update(
            f"[bold]Département {dept_code}[/]\n\n"
            f"Croissance: [{color}]{sign}{growth*100:.1f}%[/]\n"
            f"Entreprises: [cyan]{random.randint(500, 5000):,}[/]\n"
            f"Confiance: [yellow]{random.uniform(0.7, 0.95)*100:.0f}%[/]"
        )


class LegendPanel(Static):
    """Legend explaining color codes."""

    DEFAULT_CSS = """
    LegendPanel {
        width: 100%;
        height: auto;
        padding: 1;
        background: $surface-darken-1;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose legend."""
        yield Static(
            "[bold]Légende:[/] "
            "[on #006400] [/] >30% "
            "[on #44FF44] [/] 10-30% "
            "[on #FFFF00] [/] ±10% "
            "[on #FF4444] [/] -10 à -20% "
            "[on #8B0000] [/] <-20%"
        )


class FranceMapPrototypeApp(App):
    """Prototype TUI app for France map visualization."""

    TITLE = "TUI v6 Prototype - France Map"

    CSS = """
    Screen {
        background: $background;
    }

    #main-container {
        width: 100%;
        height: 1fr;
        padding: 1;
    }

    #controls {
        width: 100%;
        height: auto;
        padding: 1;
        align: center middle;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quitter"),
        ("r", "regenerate", "Régénérer données"),
        ("d", "toggle_dark", "Theme"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header()
        with Horizontal(id="main-container"):
            yield FranceMapWidget(id="france-map")
            yield MetricsPanel(id="metrics")
        yield LegendPanel()
        with Horizontal(id="controls"):
            yield Button("🔄 Régénérer", id="btn-regen", variant="primary")
            yield Button("📊 Stats", id="btn-stats")
            yield Button("❌ Quitter", id="btn-quit", variant="error")
        yield Footer()

    def action_regenerate(self) -> None:
        """Regenerate random data."""
        self._regenerate_data()

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-regen":
            self._regenerate_data()
        elif event.button.id == "btn-quit":
            self.exit()
        elif event.button.id == "btn-stats":
            self.notify("Stats: 96 départements, données simulées", timeout=3)

    def _regenerate_data(self) -> None:
        """Regenerate random department data."""
        france_map = self.query_one("#france-map", FranceMapWidget)
        if france_map._gdf is not None:
            new_data = {
                row["code"]: random.uniform(-0.3, 0.4)
                for _, row in france_map._gdf.iterrows()
            }
            france_map.update_data(new_data)
            self.notify("Données régénérées!", timeout=2)


def main():
    """Run the prototype app."""
    app = FranceMapPrototypeApp()
    app.run()


if __name__ == "__main__":
    main()
