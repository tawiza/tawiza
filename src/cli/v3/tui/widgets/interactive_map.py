"""Interactive territory map widget with clickable regions.

Provides real-time territory visualization with:
- Mouse-clickable regions
- Live data updates from CognitiveEngine
- Color-coded growth indicators
- Zoom and detail levels
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Label, Static


class GrowthCategory(Enum):
    """Growth category for color coding."""
    STRONG_GROWTH = "strong_growth"      # > 20%
    MODERATE_GROWTH = "moderate_growth"  # 5-20%
    STABLE = "stable"                    # -5% to 5%
    MODERATE_DECLINE = "moderate_decline"  # -20% to -5%
    STRONG_DECLINE = "strong_decline"    # < -20%


@dataclass
class RegionMetrics:
    """Real metrics for a region."""
    code: str
    name: str
    companies_count: int = 0
    growth_rate: float = 0.0
    confidence: float = 0.0
    sectors: dict[str, int] = field(default_factory=dict)
    top_sector: str = ""
    cognitive_score: float = 0.0  # From TAJINE analysis

    @property
    def category(self) -> GrowthCategory:
        """Get growth category based on rate."""
        if self.growth_rate > 0.20:
            return GrowthCategory.STRONG_GROWTH
        elif self.growth_rate > 0.05:
            return GrowthCategory.MODERATE_GROWTH
        elif self.growth_rate > -0.05:
            return GrowthCategory.STABLE
        elif self.growth_rate > -0.20:
            return GrowthCategory.MODERATE_DECLINE
        else:
            return GrowthCategory.STRONG_DECLINE

    @property
    def color(self) -> str:
        """Get Rich color based on growth category."""
        colors = {
            GrowthCategory.STRONG_GROWTH: "bright_green",
            GrowthCategory.MODERATE_GROWTH: "green",
            GrowthCategory.STABLE: "yellow",
            GrowthCategory.MODERATE_DECLINE: "red",
            GrowthCategory.STRONG_DECLINE: "bright_red",
        }
        return colors.get(self.category, "white")


# French regions with their simplified positions for terminal display
FRANCE_REGIONS = {
    "IDF": {"name": "Île-de-France", "short": "IDF", "row": 1, "col": 2},
    "HDF": {"name": "Hauts-de-France", "short": "HDF", "row": 0, "col": 2},
    "GES": {"name": "Grand Est", "short": "GES", "row": 1, "col": 3},
    "NOR": {"name": "Normandie", "short": "NOR", "row": 1, "col": 0},
    "BRE": {"name": "Bretagne", "short": "BRE", "row": 2, "col": 0},
    "PDL": {"name": "Pays de la Loire", "short": "PDL", "row": 2, "col": 1},
    "CVL": {"name": "Centre-Val de Loire", "short": "CVL", "row": 2, "col": 2},
    "BFC": {"name": "Bourgogne-Franche-Comté", "short": "BFC", "row": 2, "col": 3},
    "NAQ": {"name": "Nouvelle-Aquitaine", "short": "NAQ", "row": 3, "col": 1},
    "ARA": {"name": "Auvergne-Rhône-Alpes", "short": "ARA", "row": 3, "col": 2},
    "OCC": {"name": "Occitanie", "short": "OCC", "row": 4, "col": 1},
    "PAC": {"name": "Provence-Alpes-Côte d'Azur", "short": "PAC", "row": 4, "col": 2},
    "COR": {"name": "Corse", "short": "COR", "row": 4, "col": 3},
}

# Moroccan regions
MOROCCO_REGIONS = {
    "TTA": {"name": "Tanger-Tétouan-Al Hoceïma", "short": "TTA", "row": 0, "col": 1},
    "ORI": {"name": "Oriental", "short": "ORI", "row": 0, "col": 2},
    "FME": {"name": "Fès-Meknès", "short": "FME", "row": 1, "col": 1},
    "RSK": {"name": "Rabat-Salé-Kénitra", "short": "RSK", "row": 1, "col": 0},
    "BMK": {"name": "Béni Mellal-Khénifra", "short": "BMK", "row": 2, "col": 1},
    "CSB": {"name": "Casablanca-Settat", "short": "CSB", "row": 2, "col": 0},
    "MTD": {"name": "Marrakech-Safi", "short": "MTD", "row": 3, "col": 0},
    "DTA": {"name": "Drâa-Tafilalet", "short": "DTA", "row": 3, "col": 1},
    "SMD": {"name": "Souss-Massa", "short": "SMD", "row": 4, "col": 0},
    "GLM": {"name": "Guelmim-Oued Noun", "short": "GLM", "row": 5, "col": 0},
    "LAA": {"name": "Laâyoune-Sakia El Hamra", "short": "LAA", "row": 6, "col": 0},
    "DAK": {"name": "Dakhla-Oued Ed-Dahab", "short": "DAK", "row": 7, "col": 0},
}


class RegionButton(Button):
    """Clickable region button with metrics display."""

    DEFAULT_CSS = """
    RegionButton {
        width: 12;
        height: 3;
        margin: 0;
        padding: 0 1;
        border: solid $primary;
        background: $surface;
        text-align: center;
    }

    RegionButton:hover {
        background: $primary-darken-1;
        border: solid $secondary;
    }

    RegionButton.strong-growth {
        background: #1a472a;
        border: solid #2d5a3d;
    }

    RegionButton.moderate-growth {
        background: #2d4a3a;
        border: solid #3d6a4d;
    }

    RegionButton.stable {
        background: #4a4a2d;
        border: solid #6a6a4d;
    }

    RegionButton.moderate-decline {
        background: #4a2d2d;
        border: solid #6a4d4d;
    }

    RegionButton.strong-decline {
        background: #5a1a1a;
        border: solid #7a3a3a;
    }

    RegionButton.selected {
        border: double $accent;
    }
    """

    def __init__(
        self,
        region_code: str,
        region_name: str,
        metrics: RegionMetrics | None = None,
        **kwargs
    ):
        self.region_code = region_code
        self.region_name = region_name
        self._metrics = metrics

        # Build label
        label = self._build_label()
        super().__init__(label, id=f"region-{region_code}", **kwargs)

    def _build_label(self) -> str:
        """Build button label with metrics."""
        if self._metrics:
            growth_pct = self._metrics.growth_rate * 100
            sign = "+" if growth_pct > 0 else ""
            return f"{self.region_code}\n{sign}{growth_pct:.0f}%"
        return f"{self.region_code}\n--"

    def update_metrics(self, metrics: RegionMetrics) -> None:
        """Update metrics and refresh display."""
        self._metrics = metrics

        # Update CSS class based on growth category
        self.remove_class("strong-growth", "moderate-growth", "stable",
                          "moderate-decline", "strong-decline")
        css_class = metrics.category.value.replace("_", "-")
        self.add_class(css_class)

        # Update label
        self.label = self._build_label()

    @property
    def metrics(self) -> RegionMetrics | None:
        return self._metrics


class InteractiveMap(Container):
    """Interactive territory map with clickable regions."""

    DEFAULT_CSS = """
    InteractiveMap {
        height: auto;
        width: auto;
        padding: 1;
        border: solid $primary;
        background: $surface;
    }

    InteractiveMap > .map-title {
        text-align: center;
        text-style: bold;
        padding: 0 0 1 0;
    }

    InteractiveMap > .map-grid {
        align: center middle;
    }

    InteractiveMap > .map-row {
        height: auto;
        width: auto;
        align: center middle;
    }

    InteractiveMap > .map-legend {
        margin-top: 1;
        padding: 0 1;
    }
    """

    class RegionSelected(Message):
        """Message sent when a region is selected."""
        def __init__(self, region_code: str, metrics: RegionMetrics | None) -> None:
            super().__init__()
            self.region_code = region_code
            self.metrics = metrics

    selected_region = reactive("")

    def __init__(
        self,
        country: str = "france",
        on_region_click: Callable[[str, RegionMetrics | None], None] | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.country = country
        self._on_region_click = on_region_click
        self._regions = FRANCE_REGIONS if country == "france" else MOROCCO_REGIONS
        self._metrics: dict[str, RegionMetrics] = {}
        self._region_buttons: dict[str, RegionButton] = {}

    def compose(self) -> ComposeResult:
        """Compose the map layout."""
        title = "🇫🇷 FRANCE" if self.country == "france" else "🇲🇦 MAROC"
        yield Label(f"[bold]{title}[/]", classes="map-title")

        # Create grid of regions
        with Vertical(classes="map-grid"):
            # Group regions by row
            rows: dict[int, list[str]] = {}
            for code, info in self._regions.items():
                row = info["row"]
                if row not in rows:
                    rows[row] = []
                rows[row].append(code)

            # Create row containers
            for row_idx in sorted(rows.keys()):
                with Horizontal(classes="map-row"):
                    for code in sorted(rows[row_idx], key=lambda c: self._regions[c]["col"]):
                        info = self._regions[code]
                        metrics = self._metrics.get(code)
                        btn = RegionButton(code, info["name"], metrics)
                        self._region_buttons[code] = btn
                        yield btn

        # Legend
        yield Static(
            "[bold]Légende:[/] "
            "[bright_green]██[/] >20% "
            "[green]██[/] 5-20% "
            "[yellow]██[/] ±5% "
            "[red]██[/] -5 à -20% "
            "[bright_red]██[/] <-20%",
            classes="map-legend"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle region button click."""
        button_id = event.button.id or ""
        if button_id.startswith("region-"):
            region_code = button_id.replace("region-", "")

            # Update selection
            if self.selected_region:
                old_btn = self._region_buttons.get(self.selected_region)
                if old_btn:
                    old_btn.remove_class("selected")

            self.selected_region = region_code
            event.button.add_class("selected")

            # Get metrics and emit message
            metrics = self._metrics.get(region_code)
            self.post_message(self.RegionSelected(region_code, metrics))

            # Call callback if provided
            if self._on_region_click:
                self._on_region_click(region_code, metrics)

    def update_region_metrics(self, code: str, metrics: RegionMetrics) -> None:
        """Update metrics for a single region."""
        self._metrics[code] = metrics
        if code in self._region_buttons:
            self._region_buttons[code].update_metrics(metrics)

    def update_all_metrics(self, metrics: dict[str, RegionMetrics]) -> None:
        """Update metrics for all regions."""
        self._metrics = metrics
        for code, region_metrics in metrics.items():
            if code in self._region_buttons:
                self._region_buttons[code].update_metrics(region_metrics)

    def load_from_cognitive_output(self, cognitive_output: dict[str, Any]) -> None:
        """Load region metrics from CognitiveEngine output.

        Args:
            cognitive_output: Output from CognitiveEngine.process()
        """
        # Extract territory data from cognitive output
        levels = cognitive_output.get("cognitive_levels", {})
        discovery = levels.get("discovery", {})
        signals = discovery.get("signals", [])

        for signal in signals:
            if "territory" in signal:
                code = self._territory_to_code(signal["territory"])
                if code:
                    metrics = RegionMetrics(
                        code=code,
                        name=signal.get("territory", code),
                        companies_count=signal.get("companies", 0),
                        growth_rate=signal.get("growth", 0.0),
                        confidence=cognitive_output.get("confidence", 0.5),
                        cognitive_score=cognitive_output.get("confidence", 0.5),
                    )
                    self.update_region_metrics(code, metrics)

    def _territory_to_code(self, territory: str) -> str | None:
        """Convert territory name to region code."""
        territory_lower = territory.lower()

        # France mappings
        france_mappings = {
            "paris": "IDF", "ile-de-france": "IDF", "île-de-france": "IDF",
            "lyon": "ARA", "rhone-alpes": "ARA", "auvergne": "ARA",
            "marseille": "PAC", "provence": "PAC", "paca": "PAC",
            "toulouse": "OCC", "occitanie": "OCC",
            "bordeaux": "NAQ", "aquitaine": "NAQ",
            "lille": "HDF", "nord": "HDF",
            "strasbourg": "GES", "alsace": "GES",
            "nantes": "PDL", "loire": "PDL",
            "rennes": "BRE", "bretagne": "BRE",
        }

        # Morocco mappings
        morocco_mappings = {
            "casablanca": "CSB", "casa": "CSB",
            "rabat": "RSK",
            "marrakech": "MTD",
            "fes": "FME", "fès": "FME",
            "tanger": "TTA", "tangier": "TTA",
            "agadir": "SMD",
            "oujda": "ORI",
        }

        mappings = {**france_mappings, **morocco_mappings}
        for key, code in mappings.items():
            if key in territory_lower:
                return code

        return None


class RegionDetailPanel(Static):
    """Detail panel showing selected region information."""

    DEFAULT_CSS = """
    RegionDetailPanel {
        height: auto;
        min-height: 12;
        padding: 1;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._metrics: RegionMetrics | None = None
        self._region_name: str = ""

    def render(self) -> str:
        """Render region details."""
        if not self._metrics:
            return (
                "[dim]Sélectionnez une région sur la carte[/]\n"
                "[dim]pour voir les détails...[/]"
            )

        m = self._metrics
        growth_pct = m.growth_rate * 100
        sign = "+" if growth_pct > 0 else ""
        color = m.color

        lines = [
            f"[bold]{m.name}[/] ({m.code})",
            "─" * 30,
            f"Entreprises: [cyan]{m.companies_count:,}[/]",
            f"Croissance: [{color}]{sign}{growth_pct:.1f}%[/]",
            f"Confiance: [yellow]{m.confidence*100:.0f}%[/]",
            f"Score TAJINE: [magenta]{m.cognitive_score*100:.0f}%[/]",
        ]

        if m.top_sector:
            lines.append(f"Secteur principal: [green]{m.top_sector}[/]")

        if m.sectors:
            lines.append("─" * 30)
            lines.append("[bold]Secteurs:[/]")
            for sector, count in list(m.sectors.items())[:5]:
                lines.append(f"  • {sector}: {count}")

        return "\n".join(lines)

    def show_region(self, metrics: RegionMetrics) -> None:
        """Display metrics for a region."""
        self._metrics = metrics
        self.refresh()

    def clear(self) -> None:
        """Clear the panel."""
        self._metrics = None
        self.refresh()
