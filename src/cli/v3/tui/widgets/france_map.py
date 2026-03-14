"""France map widget for territory visualization.

Displays a simplified ASCII map of France with territory highlights
and data overlays for regional analysis.
"""

from dataclasses import dataclass

from textual.reactive import reactive
from textual.widgets import Static


@dataclass
class TerritoryData:
    """Data for a territory on the map."""

    code: str
    name: str
    companies: int = 0
    growth: float = 0.0
    confidence: float = 0.0


# ASCII Map of France with region markers
FRANCE_MAP_TEMPLATE = """
        ╭───╮
       ╱ ·75 ╲        ·62
      ╱   ▪   ╲      ╱───╮
     │  Paris  │────┤·59 │
     ╰─────────╯    ╰────╯
    ·35│        │·51
   ╭───┤ ·45    ├───╮·67
  ╱    │   ·37  │    ╲
 │·44  ╰────────╯·21  │
 │      │·41│        ·68│
 ╰──────┤   ├─────╮    │
   ·49  │·18│ ·69 │·25 │
        ╰───┤Lyon ├────╯
    ·86    ·03·  ·38
   ╭────╮   │·42
  ╱ ·33 ╲  ╱ ·43
 │Bordeaux│╱
 │   ▪   ╱╲·15
  ╲     ╱  ╲·12·34
   ╰───╯    ╲·81
    ·40·64   ╲·31
         ·65  │Toulouse
              │   ▪·11
              ╰────────╮
                  ·66  │·13
                  ╭────┤Marseille
                 ╱ ·83 │  ▪
                ╰──────╯·06
"""

# Simplified France regions with their approximate positions
REGIONS = {
    "Île-de-France": {"pos": (14, 3), "depts": ["75", "77", "78", "91", "92", "93", "94", "95"]},
    "Hauts-de-France": {"pos": (22, 2), "depts": ["02", "59", "60", "62", "80"]},
    "Grand Est": {
        "pos": (28, 6),
        "depts": ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"],
    },
    "Normandie": {"pos": (6, 4), "depts": ["14", "27", "50", "61", "76"]},
    "Bretagne": {"pos": (2, 6), "depts": ["22", "29", "35", "56"]},
    "Pays de la Loire": {"pos": (4, 8), "depts": ["44", "49", "53", "72", "85"]},
    "Centre-Val de Loire": {"pos": (12, 8), "depts": ["18", "28", "36", "37", "41", "45"]},
    "Bourgogne-Franche-Comté": {
        "pos": (22, 9),
        "depts": ["21", "25", "39", "58", "70", "71", "89", "90"],
    },
    "Nouvelle-Aquitaine": {
        "pos": (6, 13),
        "depts": ["16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"],
    },
    "Auvergne-Rhône-Alpes": {
        "pos": (20, 12),
        "depts": ["01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"],
    },
    "Occitanie": {
        "pos": (12, 17),
        "depts": ["09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"],
    },
    "Provence-Alpes-Côte d'Azur": {"pos": (26, 18), "depts": ["04", "05", "06", "13", "83", "84"]},
    "Corse": {"pos": (32, 20), "depts": ["2A", "2B"]},
}

# Major cities with their positions and departments
CITIES = {
    "Paris": {"pos": (14, 3), "dept": "75"},
    "Marseille": {"pos": (26, 19), "dept": "13"},
    "Lyon": {"pos": (20, 12), "dept": "69"},
    "Toulouse": {"pos": (12, 17), "dept": "31"},
    "Bordeaux": {"pos": (6, 13), "dept": "33"},
    "Lille": {"pos": (22, 2), "dept": "59"},
    "Nice": {"pos": (30, 19), "dept": "06"},
    "Nantes": {"pos": (4, 8), "dept": "44"},
    "Strasbourg": {"pos": (30, 5), "dept": "67"},
    "Montpellier": {"pos": (18, 18), "dept": "34"},
}


class FranceMapWidget(Static):
    """Interactive ASCII map of France with territory data visualization."""

    DEFAULT_CSS = """
    FranceMapWidget {
        height: 22;
        width: 45;
        padding: 0 1;
        border: solid $primary;
        background: $surface;
    }
    """

    selected_region = reactive("")

    def __init__(self, territory_data: dict[str, TerritoryData] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._territory_data = territory_data or {}
        self._highlighted_cities: list[str] = []

    def render(self) -> str:
        """Render the France map with data overlays."""
        lines = [
            "╭─────────────────────────────────╮",
            "│        FRANCE - Territoires     │",
            "├─────────────────────────────────┤",
        ]

        # Simplified compact map
        map_lines = self._render_compact_map()
        lines.extend(map_lines)

        # Legend
        lines.append("├─────────────────────────────────┤")
        lines.append("│ [green]●[/] Croissance  [red]●[/] Déclin    │")
        lines.append("│ [yellow]●[/] Stable     [cyan]●[/] Sélectionné │")
        lines.append("╰─────────────────────────────────╯")

        return "\n".join(lines)

    def _render_compact_map(self) -> list[str]:
        """Render a compact stylized map of France."""
        # Build the map based on territory data
        map_art = [
            "│       ╭──────╮                  │",
            "│      ╱ ·Lille ╲    ·Stras      │",
            "│   ╭─┤  ·Paris  ├──╮             │",
            "│  ╱  ╰────┬─────╯  ╲             │",
            "│·Nantes   │    ·Lyon╲            │",
            "│  ╲   ╭───┴───╮     │            │",
            "│   ╰──┤       ├─────╯            │",
            "│ ·Bord│       │·Mont             │",
            "│      ╰─┬───┬─╯                  │",
            "│ ·Toul  │   │  ·Mars  ·Nice     │",
            "│        ╰───╯                    │",
        ]

        # Apply data-driven coloring
        colored_lines = []
        for line in map_art:
            colored_line = line
            for city, info in CITIES.items():
                short_name = city[:5] if len(city) > 5 else city
                marker = f"·{short_name}"
                if marker in colored_line:
                    # Get color based on territory data
                    dept = info["dept"]
                    color = self._get_territory_color(dept)
                    colored_marker = f"[{color}]●{short_name}[/]"
                    colored_line = colored_line.replace(marker, colored_marker)
            colored_lines.append(colored_line)

        return colored_lines

    def _get_territory_color(self, dept: str) -> str:
        """Get color for a territory based on its data."""
        if dept in self._territory_data:
            data = self._territory_data[dept]
            if data.growth > 0.1:
                return "green"
            elif data.growth < -0.1:
                return "red"
            else:
                return "yellow"
        return "dim"

    def update_territory(self, dept: str, data: TerritoryData) -> None:
        """Update data for a territory."""
        self._territory_data[dept] = data
        self.refresh()

    def update_territories(self, data: dict[str, TerritoryData]) -> None:
        """Update multiple territories at once."""
        self._territory_data.update(data)
        self.refresh()

    def highlight_city(self, city: str) -> None:
        """Highlight a city on the map."""
        if city in CITIES:
            self._highlighted_cities.append(city)
            self.refresh()

    def clear_highlights(self) -> None:
        """Clear all city highlights."""
        self._highlighted_cities.clear()
        self.refresh()

    def get_region_for_dept(self, dept: str) -> str | None:
        """Get the region name for a department code."""
        for region, info in REGIONS.items():
            if dept in info["depts"]:
                return region
        return None


class MoroccoMapWidget(Static):
    """ASCII map of Morocco for territory visualization.

    Supports the original Tawiza use case for Moroccan market analysis.
    """

    DEFAULT_CSS = """
    MoroccoMapWidget {
        height: 18;
        width: 40;
        padding: 0 1;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, territory_data: dict[str, TerritoryData] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._territory_data = territory_data or {}

    def render(self) -> str:
        """Render Morocco map with data overlays."""
        lines = [
            "╭──────────────────────────────╮",
            "│     MAROC - Territoires      │",
            "├──────────────────────────────┤",
            "│     ·Tanger                  │",
            "│    ╭─────╮  ·Oujda          │",
            "│   ╱ ·Fès  ╲                  │",
            "│  │ ·Rabat  │·Meknès         │",
            "│  │●Casa    │                 │",
            "│   ╲        ╱                 │",
            "│    ╰──────╯                  │",
            "│      │  ·Marrakech          │",
            "│      │      ·Ouarzazate     │",
            "│     ·Agadir                  │",
            "│      ╲                       │",
            "│       ·Laâyoune             │",
            "├──────────────────────────────┤",
            "│ [green]●[/] Croiss [yellow]●[/] Stable [red]●[/] Déclin │",
            "╰──────────────────────────────╯",
        ]
        return "\n".join(lines)

    def update_territory(self, city: str, data: TerritoryData) -> None:
        """Update data for a territory."""
        self._territory_data[city] = data
        self.refresh()
