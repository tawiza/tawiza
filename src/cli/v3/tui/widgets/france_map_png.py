"""France map PNG widget with choropleth visualization.

This widget renders a France department map as a PNG using GeoPandas and matplotlib,
then displays it using textual-image. It supports choropleth coloring based on
growth rates and interactive department selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    import geopandas as gpd
from textual.containers import Container
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

# Growth rate color thresholds (as decimals: 0.20 = 20%)
GROWTH_COLORS = {
    "strong_growth": "#006400",      # > 20%
    "moderate_growth": "#44FF44",    # 5-20%
    "stable": "#FFFF00",             # -5% to 5%
    "moderate_decline": "#FF4444",   # -20% to -5%
    "strong_decline": "#8B0000",     # < -20%
}

# Metropolitan France department codes (01-95 except 20, plus 2A and 2B)
METRO_DEPT_CODES = [f"{i:02d}" for i in range(1, 96) if i != 20] + ["2A", "2B"]

# Possible column names for department codes in GeoJSON
CODE_COLUMN_CANDIDATES = ['code', 'CODE_DEPT', 'code_dept', 'CODE', 'nom']


@dataclass
class MapConfig:
    """Configuration for map rendering."""

    width: int = 800
    height: int = 600
    dpi: int = 100
    background_color: str = "#FFFFFF"
    edge_color: str = "#000000"
    edge_width: float = 0.5
    colormap_colors: list[str] = field(default_factory=lambda: list(GROWTH_COLORS.values()))
    vmin: float = -0.3  # Min growth rate for color scale (decimal)
    vmax: float = 0.4   # Max growth rate for color scale (decimal)


@dataclass
class DepartmentData:
    """Data for a single department."""

    code: str
    name: str
    growth_rate: float
    companies_count: int
    confidence: float
    top_sector: str

    @property
    def color(self) -> str:
        """Get color based on growth rate thresholds (decimals: 0.20 = 20%)."""
        if self.growth_rate > 0.20:
            return GROWTH_COLORS["strong_growth"]
        elif self.growth_rate >= 0.05:
            return GROWTH_COLORS["moderate_growth"]
        elif self.growth_rate >= -0.05:
            return GROWTH_COLORS["stable"]
        elif self.growth_rate >= -0.20:
            return GROWTH_COLORS["moderate_decline"]
        else:
            return GROWTH_COLORS["strong_decline"]


class FranceMapPNG(Container):
    """PNG-based France department map with choropleth visualization."""

    DEFAULT_CSS = """
    FranceMapPNG {
        height: 100%;
        width: 100%;
        background: $surface;
        layout: vertical;
    }

    FranceMapPNG .map-title {
        text-align: center;
        background: $primary;
        color: $text;
        padding: 0 1;
        height: 1;
    }

    FranceMapPNG .map-container {
        height: 1fr;
        width: 100%;
    }

    /* Make textual-image AutoImage expand */
    FranceMapPNG AutoImage {
        height: 1fr;
        width: 100%;
    }

    FranceMapPNG .map-legend {
        height: 2;
        background: $surface;
        padding: 0 1;
    }

    FranceMapPNG .map-loading {
        text-align: center;
        color: $text-muted;
        padding: 2;
        height: 1fr;
    }
    """

    class DepartmentClicked(Message):
        """Message sent when a department is clicked."""

        def __init__(self, department_code: str, data: DepartmentData | None = None):
            super().__init__()
            self.department_code = department_code
            self.data = data

    class MapRendered(Message):
        """Message sent when map rendering completes."""

        def __init__(self, success: bool, error: str | None = None):
            super().__init__()
            self.success = success
            self.error = error

    selected_department = reactive("")

    def __init__(
        self,
        geojson_path: Path | None = None,
        config: MapConfig | None = None,
        **kwargs
    ):
        """Initialize FranceMapPNG widget.

        Args:
            geojson_path: Path to departements GeoJSON file
            config: Map rendering configuration
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.geojson_path = geojson_path or (
            Path.home() / ".cache" / "tawiza" / "geo" / "departements.geojson"
        )
        self.config = config or MapConfig()
        self._department_data: dict[str, DepartmentData] = {}
        self._map_image_widget: Static | None = None
        self._png_path: Path | None = None

    def compose(self):
        """Compose the widget layout."""
        yield Static("France - Croissance des Entreprises", classes="map-title")
        yield Static("Chargement de la carte...", classes="map-loading", id="map-loading")
        yield Static(classes="map-legend", id="map-legend")

    def on_mount(self) -> None:
        """Initialize widget when mounted."""
        self._render_legend()

    def update_department(self, data: DepartmentData) -> None:
        """Update data for a single department.

        Args:
            data: Department data to update
        """
        self._department_data[data.code] = data
        logger.debug(f"Updated department {data.code}: {data.name}")

    def update_all_data(self, data: dict[str, DepartmentData]) -> None:
        """Update data for multiple departments.

        Args:
            data: Dictionary mapping department codes to data
        """
        self._department_data.update(data)
        logger.debug(f"Updated {len(data)} departments")

    def clear_data(self) -> None:
        """Clear all department data."""
        self._department_data.clear()
        logger.debug("Cleared all department data")

    def get_department_data(self, code: str) -> DepartmentData | None:
        """Get data for a specific department.

        Args:
            code: Department code

        Returns:
            Department data or None if not found
        """
        return self._department_data.get(code)

    async def refresh_map(self) -> None:
        """Regenerate and display the map with current data.

        This method performs the actual map rendering using GeoPandas and matplotlib.
        Output is suppressed to avoid interfering with TUI display.
        """
        import io
        from contextlib import redirect_stderr, redirect_stdout

        # Suppress all output during map rendering
        null_out = io.StringIO()
        fig = None  # Track figure for cleanup in finally block

        try:
            with redirect_stdout(null_out), redirect_stderr(null_out):
                # Suppress matplotlib warnings
                import warnings
                warnings.filterwarnings('ignore')

                # Lazy imports for heavy dependencies
                import geopandas as gpd
                import matplotlib
                matplotlib.use('Agg')  # Non-interactive backend
                import matplotlib.pyplot as plt
                from matplotlib.colors import LinearSegmentedColormap

            from textual_image.widget import Image as TextualImage

            logger.debug("Starting map rendering")

            # Check if GeoJSON exists
            if not self.geojson_path.exists():
                error_msg = f"GeoJSON file not found: {self.geojson_path}"
                logger.error(error_msg)
                self._show_error(error_msg)
                self.post_message(self.MapRendered(success=False, error=error_msg))
                return

            # Load GeoJSON
            logger.debug(f"Loading GeoJSON from {self.geojson_path}")
            gdf = gpd.read_file(self.geojson_path)

            # Filter to metropolitan France (codes 01-95 except 20, plus 2A and 2B)
            gdf = self._filter_metropolitan_france(gdf)

            # Prepare data for choropleth
            if self._department_data:
                gdf = self._prepare_choropleth_data(gdf)

            # Create figure
            fig, ax = plt.subplots(
                figsize=(self.config.width / self.config.dpi, self.config.height / self.config.dpi),
                dpi=self.config.dpi
            )

            # Set background color
            fig.patch.set_facecolor(self.config.background_color)
            ax.set_facecolor(self.config.background_color)

            # Create colormap from config colors
            if self._department_data:
                cmap = LinearSegmentedColormap.from_list(
                    "growth",
                    self.config.colormap_colors,
                    N=256
                )

                # Plot choropleth
                gdf.plot(
                    ax=ax,
                    column='growth_rate',
                    cmap=cmap,
                    vmin=self.config.vmin,
                    vmax=self.config.vmax,
                    edgecolor=self.config.edge_color,
                    linewidth=self.config.edge_width,
                    legend=False,
                    missing_kwds={'color': '#CCCCCC'}
                )
            else:
                # No data, just show borders
                gdf.plot(
                    ax=ax,
                    facecolor='#EEEEEE',
                    edgecolor=self.config.edge_color,
                    linewidth=self.config.edge_width
                )

            # Remove axes
            ax.set_axis_off()

            # Save to temporary PNG
            self._png_path = Path.home() / ".cache" / "tawiza" / "tui" / "france_map.png"
            self._png_path.parent.mkdir(parents=True, exist_ok=True)

            plt.tight_layout(pad=0)
            plt.savefig(
                self._png_path,
                dpi=self.config.dpi,
                bbox_inches='tight',
                facecolor=self.config.background_color
            )
            plt.close(fig)

            logger.debug(f"Map saved to {self._png_path}")

            # Update widget with new image
            loading_widget = self.query_one("#map-loading")
            if loading_widget:
                await loading_widget.remove()

            # Add or update image widget
            if self._map_image_widget:
                await self._map_image_widget.remove()

            self._map_image_widget = TextualImage(str(self._png_path))
            self._map_image_widget.add_class("map-container")
            await self.mount(self._map_image_widget, before="#map-legend" if self.query(".map-legend") else None)

            self.post_message(self.MapRendered(success=True))
            logger.info("Map rendered successfully")

        except ImportError as e:
            error_msg = f"Missing dependencies: {e}. Install with: pip install geopandas matplotlib textual-image"
            logger.error(error_msg)
            self._show_error(error_msg)
            self.post_message(self.MapRendered(success=False, error=error_msg))

        except Exception as e:
            error_msg = f"Failed to render map: {e}"
            logger.error(error_msg, exc_info=True)
            self._show_error(error_msg)
            self.post_message(self.MapRendered(success=False, error=error_msg))

        finally:
            # CRITICAL: Always close matplotlib figure to prevent memory leak
            if fig is not None:
                try:
                    import matplotlib.pyplot as plt
                    plt.close(fig)
                except Exception:
                    pass  # Best effort cleanup

    def _filter_metropolitan_france(self, gdf) -> gpd.GeoDataFrame:
        """Filter GeoDataFrame to metropolitan France only.

        Args:
            gdf: GeoDataFrame with department data

        Returns:
            Filtered GeoDataFrame
        """
        # Detect code column (could be 'code', 'CODE_DEPT', 'nom', etc.)
        code_col = None
        for col in CODE_COLUMN_CANDIDATES:
            if col in gdf.columns:
                code_col = col
                break

        if not code_col:
            logger.warning("Could not find department code column, using all data")
            return gdf

        # Also try uppercase variants
        valid_codes_upper = [c.upper() for c in METRO_DEPT_CODES]
        valid_codes_all = METRO_DEPT_CODES + valid_codes_upper

        filtered = gdf[gdf[code_col].isin(valid_codes_all)]
        logger.debug(f"Filtered to {len(filtered)} metropolitan departments from {len(gdf)} total")

        return filtered

    def _prepare_choropleth_data(self, gdf) -> gpd.GeoDataFrame:
        """Add growth rate data to GeoDataFrame for choropleth.

        Args:
            gdf: GeoDataFrame with department geometries

        Returns:
            GeoDataFrame with growth_rate column
        """
        # Detect code column
        code_col = None
        for col in CODE_COLUMN_CANDIDATES:
            if col in gdf.columns:
                code_col = col
                break

        if not code_col:
            logger.warning("Could not find department code column for choropleth")
            return gdf

        # Map department codes to growth rates
        def get_growth_rate(code):
            # Try both as-is and uppercase
            dept_data = self._department_data.get(code) or self._department_data.get(code.upper())
            if dept_data:
                return dept_data.growth_rate
            return None

        gdf['growth_rate'] = gdf[code_col].apply(get_growth_rate)

        return gdf

    def _render_legend(self) -> None:
        """Update legend widget with color scale."""
        legend_widget = self.query_one(".map-legend", Static)
        legend_text = (
            "[#006400]█[/] >20%  "
            "[#44FF44]█[/] 5-20%  "
            "[#FFFF00]█[/] ±5%  "
            "[#FF4444]█[/] -20 à -5%  "
            "[#8B0000]█[/] <-20%"
        )
        legend_widget.update(legend_text)

    def _show_error(self, message: str) -> None:
        """Display error message in widget.

        Args:
            message: Error message to display
        """
        try:
            loading_widget = self.query_one("#map-loading")
            loading_widget.update(f"[red]Erreur:[/] {message}")
        except Exception:
            # Widget might not exist yet
            pass
