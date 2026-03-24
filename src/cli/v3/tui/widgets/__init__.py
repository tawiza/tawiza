"""TUI Widgets."""

from src.cli.v3.tui.widgets.action_timeline import ActionTimeline
from src.cli.v3.tui.widgets.breadcrumb import Breadcrumb
from src.cli.v3.tui.widgets.browser_preview import BrowserPreview
from src.cli.v3.tui.widgets.chat_modal import ChatMessage, ChatModal, MessageBubble
from src.cli.v3.tui.widgets.cognitive_charts import (
    CognitiveLevelsWidget,
    ConfidenceGauge,
    MonteCarloChart,
    RegionalHeatmap,
    TimeSeriesChart,
)
from src.cli.v3.tui.widgets.command_input import CommandInput

# TUI v6 Navigation widgets
from src.cli.v3.tui.widgets.global_sidebar import GlobalSidebar, SidebarItem

# TAJINE Cognitive widgets
from src.cli.v3.tui.widgets.interactive_map import (
    InteractiveMap,
    RegionButton,
    RegionDetailPanel,
    RegionMetrics,
)
from src.cli.v3.tui.widgets.metric_gauge import MetricGauge
from src.cli.v3.tui.widgets.plotext_charts import CPUMemoryChart, GPUChart, PerformanceChart
from src.cli.v3.tui.widgets.service_status import ServiceStatusWidget
from src.cli.v3.tui.widgets.sparkline import MetricCard, MultiSparkline, Sparkline
from src.cli.v3.tui.widgets.spinner import (
    LoadingBar,
    Spinner,
    TaskProgress,
    ThinkingIndicator,
)
from src.cli.v3.tui.widgets.task_list import TaskInfo, TaskList, TaskStatus
from src.cli.v3.tui.widgets.thinking_log import ThinkingLog

__all__ = [
    # Gauges and metrics
    "MetricGauge",
    "Sparkline",
    "MultiSparkline",
    "MetricCard",
    # Status widgets
    "ServiceStatusWidget",
    "TaskList",
    "TaskInfo",
    "TaskStatus",
    # Input
    "CommandInput",
    # Logs and timelines
    "ThinkingLog",
    "ActionTimeline",
    # Browser
    "BrowserPreview",
    # Charts (plotext)
    "GPUChart",
    "CPUMemoryChart",
    "PerformanceChart",
    # Spinners and loading
    "Spinner",
    "LoadingBar",
    "ThinkingIndicator",
    "TaskProgress",
    # TUI v6 Navigation
    "GlobalSidebar",
    "SidebarItem",
    "Breadcrumb",
    "ChatModal",
    "ChatMessage",
    "MessageBubble",
    # TAJINE Cognitive widgets
    "InteractiveMap",
    "RegionDetailPanel",
    "RegionMetrics",
    "RegionButton",
    "CognitiveLevelsWidget",
    "MonteCarloChart",
    "TimeSeriesChart",
    "RegionalHeatmap",
    "ConfidenceGauge",
]
