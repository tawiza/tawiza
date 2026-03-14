"""Department list widget with color-coded growth rates.

Displays French departments in a scrollable list with:
- Color coding by growth rate (green/yellow/red)
- Key metrics (code, name, growth, companies)
- Click to select and show details
"""

from dataclasses import dataclass

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DataTable, Static


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
    def growth_color(self) -> str:
        """Get color based on growth rate."""
        if self.growth_rate > 0.20:
            return "green"
        elif self.growth_rate >= 0.05:
            return "bright_green"
        elif self.growth_rate >= -0.05:
            return "yellow"
        elif self.growth_rate >= -0.20:
            return "red"
        else:
            return "bright_red"

    @property
    def growth_icon(self) -> str:
        """Get icon based on growth rate."""
        if self.growth_rate > 0.10:
            return "📈"
        elif self.growth_rate > 0:
            return "↗️"
        elif self.growth_rate >= -0.05:
            return "➡️"
        elif self.growth_rate >= -0.10:
            return "↘️"
        else:
            return "📉"


class DepartmentList(Static):
    """Scrollable list of departments with color-coded growth rates."""

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter", "select", "Select", show=False),
    ]

    DEFAULT_CSS = """
    DepartmentList {
        height: 100%;
        width: 100%;
        background: $surface;
    }

    DepartmentList DataTable {
        height: 100%;
        width: 100%;
    }

    DepartmentList DataTable > .datatable--header {
        background: $primary;
        color: $text;
        text-style: bold;
    }

    DepartmentList DataTable > .datatable--cursor {
        background: $accent;
    }
    """

    class DepartmentSelected(Message):
        """Message when a department is selected."""

        def __init__(self, data: DepartmentData):
            super().__init__()
            self.data = data

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._departments: dict[str, DepartmentData] = {}
        self._table: DataTable | None = None

    def compose(self) -> ComposeResult:
        """Create the data table."""
        self._table = DataTable(id="dept-table", cursor_type="row")
        yield self._table

    def on_mount(self) -> None:
        """Initialize table columns."""
        if self._table:
            self._table.add_columns("Code", "Département", "Croissance", "Entreprises", "Secteur")

    def update_department(self, data: DepartmentData) -> None:
        """Update a single department."""
        self._departments[data.code] = data
        self._refresh_table()

    def update_all_data(self, data: dict[str, DepartmentData]) -> None:
        """Update all departments."""
        self._departments = data.copy()
        self._refresh_table()
        logger.debug(f"Updated {len(data)} departments in list")

    def clear_data(self) -> None:
        """Clear all data."""
        self._departments.clear()
        if self._table:
            self._table.clear()

    def _refresh_table(self) -> None:
        """Refresh table with current data."""
        if not self._table:
            return

        self._table.clear()

        # Sort by growth rate (descending)
        sorted_depts = sorted(self._departments.values(), key=lambda d: d.growth_rate, reverse=True)

        for dept in sorted_depts:
            # Format growth with color
            growth_pct = f"{dept.growth_rate:+.1%}"
            color = dept.growth_color
            icon = dept.growth_icon

            self._table.add_row(
                dept.code,
                dept.name[:20],  # Truncate long names
                f"[{color}]{icon} {growth_pct}[/]",
                f"{dept.companies_count:,}",
                dept.top_sector[:10],
                key=dept.code,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        if event.row_key and event.row_key.value in self._departments:
            dept = self._departments[event.row_key.value]
            self.post_message(self.DepartmentSelected(dept))

    def get_department(self, code: str) -> DepartmentData | None:
        """Get department by code."""
        return self._departments.get(code)


class DepartmentSummary(Static):
    """Summary statistics for departments."""

    DEFAULT_CSS = """
    DepartmentSummary {
        height: auto;
        width: 100%;
        padding: 1;
        background: $surface;
        border: solid $primary;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._departments: dict[str, DepartmentData] = {}

    def update_data(self, data: dict[str, DepartmentData]) -> None:
        """Update summary with department data."""
        self._departments = data
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        """Refresh summary display."""
        if not self._departments:
            self.update("[dim]Aucune donnée[/]")
            return

        depts = list(self._departments.values())
        total = len(depts)

        # Count by category
        strong_growth = sum(1 for d in depts if d.growth_rate > 0.20)
        growth = sum(1 for d in depts if 0.05 <= d.growth_rate <= 0.20)
        stable = sum(1 for d in depts if -0.05 <= d.growth_rate < 0.05)
        decline = sum(1 for d in depts if -0.20 <= d.growth_rate < -0.05)
        strong_decline = sum(1 for d in depts if d.growth_rate < -0.20)

        # Average growth
        avg_growth = sum(d.growth_rate for d in depts) / total
        total_companies = sum(d.companies_count for d in depts)

        summary = (
            f"[bold]📊 Résumé France[/] ({total} depts)\n"
            f"[green]█[/] >20%: {strong_growth}  "
            f"[bright_green]█[/] 5-20%: {growth}  "
            f"[yellow]█[/] ±5%: {stable}  "
            f"[red]█[/] -20/-5%: {decline}  "
            f"[bright_red]█[/] <-20%: {strong_decline}\n"
            f"Croissance moy: [{self._get_color(avg_growth)}]{avg_growth:+.1%}[/]  "
            f"Entreprises: {total_companies:,}"
        )
        self.update(summary)

    def _get_color(self, rate: float) -> str:
        """Get color for growth rate."""
        if rate > 0.05:
            return "green"
        elif rate >= -0.05:
            return "yellow"
        else:
            return "red"
