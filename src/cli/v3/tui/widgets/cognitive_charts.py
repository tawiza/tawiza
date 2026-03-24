"""Cognitive analysis visualization widgets.

Provides real-time visualization of TAJINE CognitiveEngine output:
- Cognitive levels progress
- Monte Carlo distribution
- Time series projections
- Regional heatmaps
"""

from dataclasses import dataclass
from typing import Any

from textual.reactive import reactive
from textual.widgets import Static
from textual_plotext import PlotextPlot


@dataclass
class CognitiveLevelResult:
    """Result from a cognitive level."""

    name: str
    confidence: float
    processing_time: float = 0.0
    method: str = "rule_based"
    key_findings: list[str] = None

    def __post_init__(self):
        if self.key_findings is None:
            self.key_findings = []


class CognitiveLevelsWidget(Static):
    """Widget showing progress of all 5 cognitive levels."""

    DEFAULT_CSS = """
    CognitiveLevelsWidget {
        height: 12;
        padding: 1;
        border: solid $primary;
        background: $surface;
    }
    """

    LEVEL_NAMES = {
        "discovery": "L1 Discovery",
        "causal": "L2 Causal",
        "scenario": "L3 Scenario",
        "strategy": "L4 Strategy",
        "theoretical": "L5 Theoretical",
    }

    LEVEL_ICONS = {
        "discovery": "🔍",
        "causal": "🔗",
        "scenario": "📊",
        "strategy": "🎯",
        "theoretical": "🧠",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._levels: dict[str, CognitiveLevelResult] = {}
        self._active_level: str | None = None

    def render(self) -> str:
        """Render cognitive levels progress."""
        lines = ["[bold]Niveaux Cognitifs TAJINE[/]", "─" * 35]

        for level_key in ["discovery", "causal", "scenario", "strategy", "theoretical"]:
            icon = self.LEVEL_ICONS.get(level_key, "○")
            name = self.LEVEL_NAMES.get(level_key, level_key)

            if level_key in self._levels:
                result = self._levels[level_key]
                confidence = result.confidence
                pct = int(confidence * 100)

                # Progress bar
                filled = int(confidence * 20)
                empty = 20 - filled
                bar = "█" * filled + "░" * empty

                # Color based on confidence
                if confidence >= 0.7:
                    color = "green"
                elif confidence >= 0.4:
                    color = "yellow"
                else:
                    color = "red"

                # Method indicator
                method_indicator = "⚡" if result.method == "monte_carlo" else "📏"

                if level_key == self._active_level:
                    lines.append(f"[bold cyan]▶ {icon} {name}[/]")
                else:
                    lines.append(f"  {icon} {name}")

                lines.append(f"    [{color}]{bar}[/] {pct}% {method_indicator}")
            else:
                lines.append(f"  {icon} [dim]{name}[/]")
                lines.append(f"    [dim]{'░' * 20}[/] --")

        return "\n".join(lines)

    def update_level(self, level: str, result: CognitiveLevelResult) -> None:
        """Update a cognitive level result."""
        self._levels[level] = result
        self.refresh()

    def set_active_level(self, level: str | None) -> None:
        """Set the currently processing level."""
        self._active_level = level
        self.refresh()

    def load_from_output(self, cognitive_output: dict[str, Any]) -> None:
        """Load all levels from CognitiveEngine output."""
        levels = cognitive_output.get("cognitive_levels", {})

        for level_key, level_data in levels.items():
            if isinstance(level_data, dict):
                confidence = level_data.get("confidence", 0.5)
                method = level_data.get("method", "rule_based")
                findings = []

                # Extract key findings based on level type
                if level_key == "discovery":
                    signals = level_data.get("signals", [])
                    findings = [s.get("description", str(s)) for s in signals[:3]]
                elif level_key == "causal":
                    causes = level_data.get("causes", [])
                    findings = [
                        f"{c.get('factor', 'unknown')}: {c.get('contribution', 0):.0%}"
                        for c in causes[:3]
                    ]
                elif level_key == "scenario":
                    findings = [
                        f"Optimiste: {level_data.get('optimistic', {}).get('growth_rate', 0):.1%}",
                        f"Médian: {level_data.get('median', {}).get('growth_rate', 0):.1%}",
                        f"Pessimiste: {level_data.get('pessimistic', {}).get('growth_rate', 0):.1%}",
                    ]
                elif level_key == "strategy":
                    recs = level_data.get("recommendations", [])
                    findings = [r.get("action", str(r)) for r in recs[:3] if isinstance(r, dict)]
                elif level_key == "theoretical":
                    theories = level_data.get("theories_applied", [])
                    findings = [t.get("name", str(t)) for t in theories[:3] if isinstance(t, dict)]

                self._levels[level_key] = CognitiveLevelResult(
                    name=self.LEVEL_NAMES.get(level_key, level_key),
                    confidence=confidence,
                    method=method,
                    key_findings=findings,
                )

        self._active_level = None
        self.refresh()


class MonteCarloChart(PlotextPlot):
    """Monte Carlo distribution histogram chart."""

    DEFAULT_CSS = """
    MonteCarloChart {
        height: 15;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, title: str = "Distribution Monte Carlo", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._bins: list[float] = []
        self._counts: list[int] = []
        self._percentiles: dict[int, float] = {}
        self._mean: float = 0.0

    def on_mount(self) -> None:
        """Initialize the chart."""
        self._update_chart()

    def update_distribution(
        self,
        bins: list[float],
        counts: list[int],
        percentiles: dict[int, float] | None = None,
        mean: float = 0.0,
    ) -> None:
        """Update the distribution data."""
        self._bins = bins
        self._counts = counts
        self._percentiles = percentiles or {}
        self._mean = mean
        self._update_chart()

    def load_from_scenario_output(self, scenario_output: dict[str, Any]) -> None:
        """Load distribution from ScenarioLevel output."""
        stats = scenario_output.get("final_value_stats", {})

        self._bins = stats.get("histogram_bins", [])
        self._counts = stats.get("histogram_counts", [])
        self._percentiles = stats.get("percentiles", {})
        self._mean = stats.get("mean", 0.0)

        self._update_chart()

    def _update_chart(self) -> None:
        """Update the plotext chart."""
        plt = self.plt
        plt.clear_figure()

        if self._bins and self._counts:
            # Create histogram bars
            plt.bar(self._bins, self._counts, color="cyan", width=0.8)

            # Add percentile lines
            if self._percentiles:
                # P10 (pessimistic)
                if 10 in self._percentiles:
                    plt.vline(self._percentiles[10], color="red")

                # P50 (median)
                if 50 in self._percentiles:
                    plt.vline(self._percentiles[50], color="yellow")

                # P90 (optimistic)
                if 90 in self._percentiles:
                    plt.vline(self._percentiles[90], color="green")

            plt.title(self._title)
            plt.xlabel("Growth Rate")
            plt.ylabel("Frequency")
            plt.theme("textual-dark")

        self.refresh()


class TimeSeriesChart(PlotextPlot):
    """Time series projection chart with confidence bands."""

    DEFAULT_CSS = """
    TimeSeriesChart {
        height: 12;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, title: str = "Projection Temporelle", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._months: list[int] = []
        self._mean_path: list[float] = []
        self._lower_bound: list[float] = []
        self._upper_bound: list[float] = []

    def on_mount(self) -> None:
        """Initialize the chart."""
        self._update_chart()

    def update_projection(
        self,
        months: list[int],
        mean_path: list[float],
        lower_bound: list[float] | None = None,
        upper_bound: list[float] | None = None,
    ) -> None:
        """Update the time series projection."""
        self._months = months
        self._mean_path = mean_path
        self._lower_bound = lower_bound or []
        self._upper_bound = upper_bound or []
        self._update_chart()

    def load_from_scenario_output(self, scenario_output: dict[str, Any]) -> None:
        """Load from ScenarioLevel output."""
        ts = scenario_output.get("time_series", {})

        self._months = ts.get("months", [])
        self._mean_path = ts.get("mean_path", [])
        self._lower_bound = ts.get("lower_bound", [])
        self._upper_bound = ts.get("upper_bound", [])

        self._update_chart()

    def _update_chart(self) -> None:
        """Update the plotext chart."""
        plt = self.plt
        plt.clear_figure()

        if self._months and self._mean_path:
            # Plot bounds as fill area (using two lines)
            if self._upper_bound:
                plt.plot(
                    self._months, self._upper_bound, color="green", marker="braille", label="P90"
                )

            if self._lower_bound:
                plt.plot(
                    self._months, self._lower_bound, color="red", marker="braille", label="P10"
                )

            # Plot mean path
            plt.plot(self._months, self._mean_path, color="cyan", marker="braille", label="Mean")

            plt.title(self._title)
            plt.xlabel("Mois")
            plt.ylabel("Croissance")
            plt.theme("textual-dark")

        self.refresh()


class RegionalHeatmap(PlotextPlot):
    """Regional heatmap using plotext matrix/heatmap."""

    DEFAULT_CSS = """
    RegionalHeatmap {
        height: 18;
        border: solid $primary;
        background: $surface;
    }
    """

    # Region grid layout (simplified France)
    FRANCE_GRID = {
        "layout": [
            ["", "HDF", "", ""],
            ["NOR", "IDF", "GES", ""],
            ["BRE", "PDL", "CVL", "BFC"],
            ["", "NAQ", "ARA", ""],
            ["", "OCC", "PAC", "COR"],
        ],
        "names": {
            "HDF": "Hauts-de-France",
            "NOR": "Normandie",
            "IDF": "Île-de-France",
            "GES": "Grand Est",
            "BRE": "Bretagne",
            "PDL": "Pays de la Loire",
            "CVL": "Centre-Val de Loire",
            "BFC": "Bourgogne-FC",
            "NAQ": "Nouvelle-Aquitaine",
            "ARA": "Auvergne-RA",
            "OCC": "Occitanie",
            "PAC": "PACA",
            "COR": "Corse",
        },
    }

    def __init__(self, title: str = "Carte Régionale", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._region_values: dict[str, float] = {}

    def on_mount(self) -> None:
        """Initialize the heatmap."""
        self._update_heatmap()

    def update_region(self, code: str, value: float) -> None:
        """Update a single region value."""
        self._region_values[code] = value
        self._update_heatmap()

    def update_all_regions(self, values: dict[str, float]) -> None:
        """Update all region values."""
        self._region_values = values
        self._update_heatmap()

    def load_from_cognitive_output(self, cognitive_output: dict[str, Any]) -> None:
        """Load regional data from CognitiveEngine output."""
        levels = cognitive_output.get("cognitive_levels", {})
        discovery = levels.get("discovery", {})

        # Extract growth rates by territory
        signals = discovery.get("signals", [])
        for signal in signals:
            territory = signal.get("territory", "")
            growth = signal.get("growth", 0.0)

            # Map territory to region code
            code = self._territory_to_code(territory)
            if code:
                self._region_values[code] = growth

        self._update_heatmap()

    def _territory_to_code(self, territory: str) -> str | None:
        """Map territory name to region code."""
        mappings = {
            "paris": "IDF",
            "ile-de-france": "IDF",
            "lyon": "ARA",
            "marseille": "PAC",
            "toulouse": "OCC",
            "bordeaux": "NAQ",
            "lille": "HDF",
            "nantes": "PDL",
            "strasbourg": "GES",
            "rennes": "BRE",
        }
        for key, code in mappings.items():
            if key in territory.lower():
                return code
        return None

    def _update_heatmap(self) -> None:
        """Update the plotext heatmap."""
        plt = self.plt
        plt.clear_figure()

        # Build matrix from grid layout
        layout = self.FRANCE_GRID["layout"]
        matrix = []

        for row in layout:
            matrix_row = []
            for cell in row:
                if cell and cell in self._region_values:
                    # Convert growth rate to 0-100 scale for heatmap
                    # -50% to +50% -> 0 to 100
                    value = (self._region_values[cell] + 0.5) * 100
                    value = max(0, min(100, value))
                    matrix_row.append(value)
                elif cell:
                    # Region exists but no data
                    matrix_row.append(50)  # Neutral
                else:
                    # Empty cell
                    matrix_row.append(0)
            matrix.append(matrix_row)

        # Use simple bar chart as heatmap approximation
        # (plotext heatmap requires pandas DataFrame)
        if self._region_values:
            regions = list(self._region_values.keys())
            values = [self._region_values[r] * 100 for r in regions]

            # Color based on value
            colors = []
            for v in values:
                if v > 10:
                    colors.append("green")
                elif v > -10:
                    colors.append("yellow")
                else:
                    colors.append("red")

            plt.bar(regions, values, color=colors)
            plt.title(self._title)
            plt.ylabel("Croissance %")
            plt.theme("textual-dark")

        self.refresh()


class ConfidenceGauge(Static):
    """Circular confidence gauge widget."""

    DEFAULT_CSS = """
    ConfidenceGauge {
        height: 5;
        width: 20;
        padding: 0 1;
        border: solid $primary;
        background: $surface;
        text-align: center;
    }
    """

    confidence = reactive(0.0)

    def __init__(self, label: str = "Confiance", **kwargs):
        super().__init__(**kwargs)
        self._label = label

    def render(self) -> str:
        """Render the confidence gauge."""
        pct = int(self.confidence * 100)

        # Color based on confidence level
        if self.confidence >= 0.7:
            color = "green"
            icon = "✓"
        elif self.confidence >= 0.4:
            color = "yellow"
            icon = "◐"
        else:
            color = "red"
            icon = "✗"

        # Simple gauge visualization
        filled = int(self.confidence * 10)
        empty = 10 - filled
        bar = "█" * filled + "░" * empty

        return f"[bold]{self._label}[/]\n[{color}]{bar}[/]\n[{color}]{icon} {pct}%[/]"

    def update_confidence(self, value: float) -> None:
        """Update the confidence value."""
        self.confidence = max(0.0, min(1.0, value))
