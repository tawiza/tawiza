#!/usr/bin/env python3
"""
Graphiques ASCII Avancés pour CLI Tawiza-V2
Line charts, histogrammes, heatmaps, Gantt charts, tables avancées
"""

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# ===== LINE CHARTS =====

class LineChart:
    """Graphiques en ligne (séries temporelles)"""

    @staticmethod
    def create(
        data: list[float],
        width: int = 60,
        height: int = 10,
        title: str = "",
        color: str = "cyan",
        show_values: bool = True
    ) -> str:
        """Créer un line chart ASCII"""
        if not data:
            return "[dim]No data[/]"

        min_val = min(data)
        max_val = max(data)
        value_range = max_val - min_val if max_val != min_val else 1

        # Normalize data
        normalized = [(v - min_val) / value_range for v in data]

        # Build chart
        chart_lines = []

        # Y-axis labels
        for row in range(height, -1, -1):
            threshold = row / height
            line = ""

            # Y-axis value
            y_value = min_val + (value_range * threshold)
            line += f"{y_value:6.1f} │ "

            # Plot points
            for i, val in enumerate(normalized):
                if i < len(normalized) - 1:
                    next_val = normalized[i + 1]

                    # Determine character
                    if abs(val - threshold) < 0.05:
                        char = "●"
                    elif threshold < val and threshold < next_val or threshold > val and threshold > next_val:
                        char = " "
                    elif val < next_val and threshold >= val and threshold <= next_val:
                        char = "/"
                    elif val > next_val and threshold <= val and threshold >= next_val:
                        char = "\\"
                    else:
                        char = " "

                    line += char
                else:
                    if abs(val - threshold) < 0.05:
                        line += "●"
                    else:
                        line += " "

            chart_lines.append(f"[{color}]{line}[/]")

        # X-axis
        x_axis = "       └" + "─" * len(data)
        chart_lines.append(f"[dim]{x_axis}[/]")

        result = "\n".join(chart_lines)

        if title:
            result = f"[bold {color}]{title}[/]\n{result}"

        if show_values:
            result += f"\n[dim]Min: {min_val:.2f} | Max: {max_val:.2f} | Avg: {statistics.mean(data):.2f}[/]"

        return result

    @staticmethod
    def create_sparkline(data: list[float], length: int = 20) -> str:
        """Créer une sparkline compacte"""
        if not data:
            return ""

        chars = "▁▂▃▄▅▆▇█"
        min_val = min(data)
        max_val = max(data)

        if max_val == min_val:
            return chars[0] * len(data[:length])

        normalized = [(v - min_val) / (max_val - min_val) for v in data[:length]]
        return "".join(chars[min(int(n * 7), 7)] for n in normalized)


# ===== BAR CHARTS =====

class BarChart:
    """Graphiques à barres avancés"""

    @staticmethod
    def create_horizontal(
        data: dict[str, float],
        width: int = 40,
        title: str = "",
        color: str = "cyan",
        show_values: bool = True
    ) -> str:
        """Créer un bar chart horizontal"""
        if not data:
            return "[dim]No data[/]"

        max_value = max(data.values())
        max_label_len = max(len(label) for label in data)

        lines = []
        if title:
            lines.append(f"[bold {color}]{title}[/]\n")

        for label, value in data.items():
            bar_length = int((value / max_value) * width) if max_value > 0 else 0
            bar = "█" * bar_length

            # Color based on value
            if value >= max_value * 0.9:
                bar_color = "green"
            elif value >= max_value * 0.7:
                bar_color = "yellow"
            else:
                bar_color = "red"

            if show_values:
                line = f"{label:{max_label_len}} │ [{bar_color}]{bar}[/] {value:.1f}"
            else:
                line = f"{label:{max_label_len}} │ [{bar_color}]{bar}[/]"

            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def create_vertical(
        data: dict[str, float],
        height: int = 10,
        title: str = "",
        width_per_bar: int = 5
    ) -> str:
        """Créer un bar chart vertical"""
        if not data:
            return "[dim]No data[/]"

        max_value = max(data.values())
        lines = []

        if title:
            lines.append(f"[bold cyan]{title}[/]\n")

        # Build bars from top to bottom
        for row in range(height, -1, -1):
            threshold = (row / height) * max_value
            line = ""

            for label, value in data.items():
                if value >= threshold:
                    line += f"[cyan]{'█' * width_per_bar}[/] "
                else:
                    line += " " * (width_per_bar + 1)

            lines.append(line)

        # X-axis
        x_axis = "─" * (len(data) * (width_per_bar + 1))
        lines.append(x_axis)

        # Labels
        label_line = ""
        for label in data:
            label_line += f"{label[:width_per_bar]:^{width_per_bar}} "
        lines.append(label_line)

        return "\n".join(lines)


# ===== HISTOGRAMMES =====

class Histogram:
    """Histogrammes pour distributions"""

    @staticmethod
    def create(
        data: list[float],
        bins: int = 10,
        width: int = 40,
        title: str = "Distribution"
    ) -> str:
        """Créer un histogramme"""
        if not data:
            return "[dim]No data[/]"

        min_val = min(data)
        max_val = max(data)
        bin_width = (max_val - min_val) / bins if bins > 0 else 1

        # Create bins
        bin_counts = [0] * bins
        for value in data:
            bin_index = min(int((value - min_val) / bin_width), bins - 1)
            bin_counts[bin_index] += 1

        # Build histogram
        max_count = max(bin_counts) if bin_counts else 1

        lines = [f"[bold cyan]{title}[/]\n"]

        for i, count in enumerate(bin_counts):
            bin_start = min_val + i * bin_width
            bin_end = bin_start + bin_width
            bar_length = int((count / max_count) * width) if max_count > 0 else 0
            bar = "█" * bar_length

            lines.append(f"{bin_start:6.1f}-{bin_end:6.1f} │ [green]{bar}[/] ({count})")

        lines.append(f"\n[dim]Total: {len(data)} values | Mean: {statistics.mean(data):.2f}[/]")

        return "\n".join(lines)


# ===== HEATMAPS =====

class Heatmap:
    """Heatmaps ASCII"""

    @staticmethod
    def create(
        data: list[list[float]],
        row_labels: list[str] | None = None,
        col_labels: list[str] | None = None,
        title: str = ""
    ) -> str:
        """Créer une heatmap"""
        if not data:
            return "[dim]No data[/]"

        # Chars for intensity (light to dark)
        intensity_chars = " ░▒▓█"

        # Flatten and get min/max
        flat_data = [val for row in data for val in row]
        min_val = min(flat_data)
        max_val = max(flat_data)
        value_range = max_val - min_val if max_val != min_val else 1

        lines = []
        if title:
            lines.append(f"[bold cyan]{title}[/]\n")

        # Column headers
        if col_labels:
            header = "      "
            for label in col_labels:
                header += f" {label[:4]:^4}"
            lines.append(header)

        # Rows
        for i, row in enumerate(data):
            row_label = row_labels[i][:5] if row_labels and i < len(row_labels) else f"Row{i}"
            line = f"{row_label:5} │"

            for val in row:
                normalized = (val - min_val) / value_range
                char_index = min(int(normalized * 4), 4)
                char = intensity_chars[char_index]

                # Color based on value
                if normalized > 0.75:
                    color = "red"
                elif normalized > 0.5:
                    color = "yellow"
                elif normalized > 0.25:
                    color = "cyan"
                else:
                    color = "blue"

                line += f" [{color}]{char * 4}[/]"

            lines.append(line)

        # Legend
        lines.append(f"\n[dim]Legend: {intensity_chars[0]}=Low {intensity_chars[-1]}=High | Range: {min_val:.2f}-{max_val:.2f}[/]")

        return "\n".join(lines)


# ===== GANTT CHARTS =====

@dataclass
class GanttTask:
    """Tâche pour Gantt chart"""
    name: str
    start: datetime
    duration: timedelta
    status: str = "pending"  # pending, running, completed, failed


class GanttChart:
    """Gantt charts pour timeline"""

    @staticmethod
    def create(
        tasks: list[GanttTask],
        width: int = 60,
        title: str = "Project Timeline"
    ) -> str:
        """Créer un Gantt chart"""
        if not tasks:
            return "[dim]No tasks[/]"

        # Find time range
        min_time = min(task.start for task in tasks)
        max_time = max(task.start + task.duration for task in tasks)
        time_range = (max_time - min_time).total_seconds()

        lines = [f"[bold cyan]{title}[/]\n"]

        # Find max name length
        max_name_len = max(len(task.name) for task in tasks)

        for task in tasks:
            # Calculate position and length
            start_pos = int(((task.start - min_time).total_seconds() / time_range) * width)
            task_length = int((task.duration.total_seconds() / time_range) * width)
            task_length = max(task_length, 1)  # Minimum 1 char

            # Status color
            status_colors = {
                "pending": "dim white",
                "running": "yellow",
                "completed": "green",
                "failed": "red"
            }
            color = status_colors.get(task.status, "white")

            # Build line
            line = f"{task.name:{max_name_len}} │"
            line += " " * start_pos
            line += f"[{color}]{'█' * task_length}[/]"

            # Add status indicator
            status_icons = {
                "pending": "○",
                "running": "◐",
                "completed": "●",
                "failed": "✗"
            }
            icon = status_icons.get(task.status, "?")
            line += f" [{color}]{icon}[/]"

            lines.append(line)

        # Timeline markers
        timeline = " " * max_name_len + " └" + "─" * width + "┘"
        lines.append(f"[dim]{timeline}[/]")
        lines.append(f"[dim]{min_time.strftime('%Y-%m-%d %H:%M')} → {max_time.strftime('%Y-%m-%d %H:%M')}[/]")

        return "\n".join(lines)


# ===== TABLES AVANCÉES =====

class AdvancedTable:
    """Tables avancées avec sorting et filtering"""

    @staticmethod
    def create_sortable(
        data: list[dict[str, Any]],
        columns: list[str],
        sort_by: str | None = None,
        reverse: bool = False,
        title: str = ""
    ) -> Table:
        """Créer une table sortable"""
        table = Table(title=title if title else None, box=box.ROUNDED)

        # Add columns
        for col in columns:
            table.add_column(col, style="cyan")

        # Sort data
        if sort_by and sort_by in columns:
            data = sorted(data, key=lambda x: x.get(sort_by, ""), reverse=reverse)

        # Add rows
        for row in data:
            table.add_row(*[str(row.get(col, "")) for col in columns])

        return table

    @staticmethod
    def create_paginated(
        data: list[dict[str, Any]],
        columns: list[str],
        page: int = 1,
        page_size: int = 10,
        title: str = ""
    ) -> tuple[Table, dict[str, int]]:
        """Créer une table avec pagination"""
        total_pages = (len(data) + page_size - 1) // page_size
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, len(data))

        page_data = data[start_idx:end_idx]

        table = Table(
            title=f"{title} (Page {page}/{total_pages})" if title else f"Page {page}/{total_pages}",
            box=box.ROUNDED
        )

        for col in columns:
            table.add_column(col, style="cyan")

        for row in page_data:
            table.add_row(*[str(row.get(col, "")) for col in columns])

        pagination_info = {
            "current_page": page,
            "total_pages": total_pages,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "total_rows": len(data)
        }

        return table, pagination_info

    @staticmethod
    def create_with_totals(
        data: list[dict[str, Any]],
        columns: list[str],
        numeric_columns: list[str],
        title: str = ""
    ) -> Table:
        """Créer une table avec totaux"""
        table = Table(title=title if title else None, box=box.ROUNDED)

        for col in columns:
            table.add_column(col, style="cyan", justify="right" if col in numeric_columns else "left")

        # Add data rows
        for row in data:
            table.add_row(*[str(row.get(col, "")) for col in columns])

        # Add totals row
        totals_row = []
        for col in columns:
            if col in numeric_columns:
                total = sum(float(row.get(col, 0)) for row in data if row.get(col))
                totals_row.append(f"[bold green]{total:.2f}[/]")
            elif col == columns[0]:
                totals_row.append("[bold]TOTAL[/]")
            else:
                totals_row.append("")

        table.add_row(*totals_row)

        return table


# ===== DEMO =====

if __name__ == "__main__":
    console.clear()
    console.print(Panel(
        "[bold cyan]Advanced Charts Demo[/]\n"
        "[dim]Line charts, histograms, heatmaps, Gantt, tables[/]",
        border_style="cyan"
    ))
    console.print()

    # 1. Line Chart
    console.print("[bold]1. Line Chart:[/]\n")
    data = [10, 15, 13, 17, 20, 18, 22, 25, 23, 28, 30, 27, 32, 35]
    chart = LineChart.create(data, width=50, height=8, title="Sales Over Time", color="green")
    console.print(chart)
    console.print()

    # 2. Sparklines
    console.print("[bold]2. Sparklines:[/]\n")
    console.print(f"[cyan]CPU:    [/][green]{LineChart.create_sparkline([10, 20, 15, 25, 30, 28, 35, 40, 38, 42])}[/]")
    console.print(f"[cyan]Memory: [/][yellow]{LineChart.create_sparkline([50, 52, 55, 53, 58, 60, 62, 65, 63, 68])}[/]")
    console.print(f"[cyan]Disk:   [/][red]{LineChart.create_sparkline([70, 72, 75, 78, 80, 83, 85, 88, 90, 92])}[/]")
    console.print()

    # 3. Bar Charts
    console.print("[bold]3. Horizontal Bar Chart:[/]\n")
    bar_data = {
        "ML Engineer": 42,
        "Data Analyst": 38,
        "Optimizer": 25,
        "Code Reviewer": 18,
        "Test Gen": 12
    }
    bar_chart = BarChart.create_horizontal(bar_data, width=30, title="Tasks by Agent")
    console.print(bar_chart)
    console.print()

    # 4. Histogram
    console.print("[bold]4. Histogram:[/]\n")
    hist_data = [10, 12, 15, 15, 18, 20, 20, 22, 25, 25, 25, 28, 30, 30, 35]
    histogram = Histogram.create(hist_data, bins=5, width=30, title="Response Time Distribution")
    console.print(histogram)
    console.print()

    # 5. Heatmap
    console.print("[bold]5. Heatmap:[/]\n")
    heatmap_data = [
        [0.1, 0.3, 0.5, 0.7, 0.9],
        [0.2, 0.4, 0.6, 0.8, 1.0],
        [0.15, 0.35, 0.55, 0.75, 0.95],
    ]
    heatmap = Heatmap.create(
        heatmap_data,
        row_labels=["Mon", "Tue", "Wed"],
        col_labels=["9AM", "11AM", "1PM", "3PM", "5PM"],
        title="CPU Usage by Day/Hour"
    )
    console.print(heatmap)
    console.print()

    # 6. Gantt Chart
    console.print("[bold]6. Gantt Chart:[/]\n")
    now = datetime.now()
    tasks = [
        GanttTask("Phase 1", now, timedelta(hours=2), "completed"),
        GanttTask("Phase 2", now + timedelta(hours=2), timedelta(hours=1.5), "completed"),
        GanttTask("Phase 3", now + timedelta(hours=3.5), timedelta(hours=1), "running"),
        GanttTask("Phase 4", now + timedelta(hours=4.5), timedelta(hours=2), "pending"),
    ]
    gantt = GanttChart.create(tasks, width=40, title="Project Timeline")
    console.print(gantt)
    console.print()

    # 7. Advanced Table
    console.print("[bold]7. Table with Totals:[/]\n")
    table_data = [
        {"Agent": "ML Engineer", "Tasks": 42, "Success": 98.5},
        {"Agent": "Data Analyst", "Tasks": 38, "Success": 99.1},
        {"Agent": "Optimizer", "Tasks": 25, "Success": 97.2},
    ]
    adv_table = AdvancedTable.create_with_totals(
        table_data,
        columns=["Agent", "Tasks", "Success"],
        numeric_columns=["Tasks"],
        title="Agent Performance"
    )
    console.print(adv_table)

    console.print()
    console.print(Panel(
        "[bold green]All Charts Demo Complete![/]",
        border_style="green"
    ))
