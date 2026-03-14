"""Terminal graph rendering system using plotext."""

import sys
from io import StringIO

import plotext as plt


class TerminalGraph:
    """Base class for terminal graphs with Tawiza design system integration."""

    def __init__(self, width: int = 80, height: int = 20):
        """
        Initialize terminal graph.

        Args:
            width: Graph width in characters
            height: Graph height in characters
        """
        self.width = width
        self.height = height
        self.colors = {
            "primary": "cyan",
            "secondary": "magenta",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "info": "blue",
            "accent": "orange",
        }

    def configure_plot(self, title: str = "", xlabel: str = "", ylabel: str = ""):
        """
        Configure plot with Tawiza styling.

        Args:
            title: Plot title
            xlabel: X-axis label
            ylabel: Y-axis label
        """
        plt.clear_figure()
        plt.plotsize(self.width, self.height)

        if title:
            plt.title(title)
        if xlabel:
            plt.xlabel(xlabel)
        if ylabel:
            plt.ylabel(ylabel)

        # Apply Tawiza color scheme
        plt.theme("pro")

    def render(self) -> str:
        """
        Render plot to string.

        Returns:
            Rendered plot as string
        """
        # Capture plotext output
        old_stdout = sys.stdout
        sys.stdout = output = StringIO()

        try:
            plt.show()
            result = output.getvalue()
        finally:
            sys.stdout = old_stdout
            plt.clear_figure()

        return result

    def get_color(self, name: str) -> str:
        """
        Get color from Tawiza palette.

        Args:
            name: Color name (primary, secondary, success, etc.)

        Returns:
            Color string for plotext
        """
        return self.colors.get(name, "default")


class LineGraph(TerminalGraph):
    """Line graph for time series and trends."""

    def plot(
        self,
        x_data: list[float],
        y_data: list[float],
        title: str = "Line Graph",
        xlabel: str = "X",
        ylabel: str = "Y",
        color: str = "primary",
        marker: str = "●",
    ) -> str:
        """
        Create a line graph.

        Args:
            x_data: X-axis data points
            y_data: Y-axis data points
            title: Graph title
            xlabel: X-axis label
            ylabel: Y-axis label
            color: Line color from Tawiza palette
            marker: Point marker

        Returns:
            Rendered graph as string
        """
        self.configure_plot(title, xlabel, ylabel)

        # Plot line with color
        plt.plot(x_data, y_data, color=self.get_color(color), marker=marker)

        return self.render()

    def plot_multiple(
        self,
        data: dict[str, tuple[list[float], list[float]]],
        title: str = "Multi-Line Graph",
        xlabel: str = "X",
        ylabel: str = "Y",
    ) -> str:
        """
        Create a multi-line graph.

        Args:
            data: Dictionary of {label: (x_data, y_data)}
            title: Graph title
            xlabel: X-axis label
            ylabel: Y-axis label

        Returns:
            Rendered graph as string
        """
        self.configure_plot(title, xlabel, ylabel)

        colors = ["primary", "secondary", "success", "warning", "info"]
        for idx, (label, (x_data, y_data)) in enumerate(data.items()):
            color = colors[idx % len(colors)]
            plt.plot(x_data, y_data, label=label, color=self.get_color(color), marker="●")

        return self.render()


class BarGraph(TerminalGraph):
    """Bar graph for comparisons and distributions."""

    def plot(
        self,
        labels: list[str],
        values: list[float],
        title: str = "Bar Graph",
        xlabel: str = "Category",
        ylabel: str = "Value",
        color: str = "primary",
        horizontal: bool = False,
    ) -> str:
        """
        Create a bar graph.

        Args:
            labels: Bar labels
            values: Bar values
            title: Graph title
            xlabel: X-axis label
            ylabel: Y-axis label
            color: Bar color from Tawiza palette
            horizontal: Use horizontal bars

        Returns:
            Rendered graph as string
        """
        self.configure_plot(title, xlabel, ylabel)

        if horizontal:
            plt.bar(labels, values, orientation="h", color=self.get_color(color))
        else:
            plt.bar(labels, values, color=self.get_color(color))

        return self.render()

    def plot_grouped(
        self,
        labels: list[str],
        data: dict[str, list[float]],
        title: str = "Grouped Bar Graph",
        xlabel: str = "Category",
        ylabel: str = "Value",
    ) -> str:
        """
        Create a grouped bar graph.

        Args:
            labels: Category labels
            data: Dictionary of {group: values}
            title: Graph title
            xlabel: X-axis label
            ylabel: Y-axis label

        Returns:
            Rendered graph as string
        """
        self.configure_plot(title, xlabel, ylabel)

        colors = ["primary", "secondary", "success", "warning"]
        for idx, (group, values) in enumerate(data.items()):
            color = colors[idx % len(colors)]
            plt.bar(labels, values, label=group, color=self.get_color(color))

        return self.render()


class SparklineGraph(TerminalGraph):
    """Compact sparkline for inline metrics."""

    def __init__(self):
        """Initialize sparkline with minimal height."""
        super().__init__(width=40, height=5)

    def plot(self, data: list[float], color: str = "primary") -> str:
        """
        Create a sparkline.

        Args:
            data: Data points
            color: Line color

        Returns:
            Rendered sparkline as string
        """
        self.configure_plot()

        plt.plot(list(range(len(data))), data, color=self.get_color(color), marker="●")

        # Remove labels for compact display
        plt.xlabel("")
        plt.ylabel("")
        plt.ticks_style("noaxis")

        return self.render()


class HistogramGraph(TerminalGraph):
    """Histogram for distribution visualization."""

    def plot(
        self,
        data: list[float],
        bins: int = 10,
        title: str = "Histogram",
        xlabel: str = "Value",
        ylabel: str = "Frequency",
        color: str = "primary",
    ) -> str:
        """
        Create a histogram.

        Args:
            data: Data values
            bins: Number of bins
            title: Graph title
            xlabel: X-axis label
            ylabel: Y-axis label
            color: Bar color

        Returns:
            Rendered histogram as string
        """
        self.configure_plot(title, xlabel, ylabel)

        plt.hist(data, bins=bins, color=self.get_color(color))

        return self.render()


class ScatterGraph(TerminalGraph):
    """Scatter plot for correlations."""

    def plot(
        self,
        x_data: list[float],
        y_data: list[float],
        title: str = "Scatter Plot",
        xlabel: str = "X",
        ylabel: str = "Y",
        color: str = "primary",
        marker: str = "●",
    ) -> str:
        """
        Create a scatter plot.

        Args:
            x_data: X-axis data points
            y_data: Y-axis data points
            title: Graph title
            xlabel: X-axis label
            ylabel: Y-axis label
            color: Point color
            marker: Point marker

        Returns:
            Rendered plot as string
        """
        self.configure_plot(title, xlabel, ylabel)

        plt.scatter(x_data, y_data, color=self.get_color(color), marker=marker)

        return self.render()


class StackedAreaGraph(TerminalGraph):
    """Stacked area chart for cumulative data."""

    def plot(
        self,
        x_data: list[float],
        y_data_list: list[list[float]],
        labels: list[str],
        title: str = "Stacked Area",
        xlabel: str = "X",
        ylabel: str = "Y",
    ) -> str:
        """
        Create a stacked area chart.

        Args:
            x_data: X-axis data points
            y_data_list: List of y-data series
            labels: Series labels
            title: Graph title
            xlabel: X-axis label
            ylabel: Y-axis label

        Returns:
            Rendered chart as string
        """
        self.configure_plot(title, xlabel, ylabel)

        colors = ["primary", "secondary", "success", "warning"]

        # Plot stacked areas
        cumulative = [0] * len(x_data)
        for idx, (y_data, label) in enumerate(zip(y_data_list, labels, strict=False)):
            y_stacked = [c + y for c, y in zip(cumulative, y_data, strict=False)]
            plt.plot(
                x_data,
                y_stacked,
                label=label,
                color=self.get_color(colors[idx % len(colors)]),
                fillx=True,
            )
            cumulative = y_stacked

        return self.render()


class BoxPlotGraph(TerminalGraph):
    """Box plot for statistical distribution."""

    def plot(
        self,
        data: list[list[float]],
        labels: list[str],
        title: str = "Box Plot",
        xlabel: str = "Category",
        ylabel: str = "Value",
    ) -> str:
        """
        Create a box plot.

        Args:
            data: List of data series
            labels: Series labels
            title: Graph title
            xlabel: X-axis label
            ylabel: Y-axis label

        Returns:
            Rendered plot as string
        """
        self.configure_plot(title, xlabel, ylabel)

        plt.box(data, labels=labels)

        return self.render()


# Convenience functions
def quick_line(x_data: list[float], y_data: list[float], title: str = "", **kwargs) -> str:
    """
    Quick line graph.

    Args:
        x_data: X-axis data
        y_data: Y-axis data
        title: Graph title
        **kwargs: Additional arguments for LineGraph.plot()

    Returns:
        Rendered graph
    """
    graph = LineGraph()
    return graph.plot(x_data, y_data, title=title, **kwargs)


def quick_bar(labels: list[str], values: list[float], title: str = "", **kwargs) -> str:
    """
    Quick bar graph.

    Args:
        labels: Bar labels
        values: Bar values
        title: Graph title
        **kwargs: Additional arguments for BarGraph.plot()

    Returns:
        Rendered graph
    """
    graph = BarGraph()
    return graph.plot(labels, values, title=title, **kwargs)


def quick_sparkline(data: list[float]) -> str:
    """
    Quick sparkline.

    Args:
        data: Data points

    Returns:
        Rendered sparkline
    """
    graph = SparklineGraph()
    return graph.plot(data)


def quick_histogram(data: list[float], title: str = "", **kwargs) -> str:
    """
    Quick histogram.

    Args:
        data: Data values
        title: Graph title
        **kwargs: Additional arguments for HistogramGraph.plot()

    Returns:
        Rendered histogram
    """
    graph = HistogramGraph()
    return graph.plot(data, title=title, **kwargs)
