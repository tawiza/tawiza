"""TAJINE Screen - Cognitive Analysis Dashboard (TUI v6).

TUI v6 Updates:
- Global sidebar navigation (removed local sidebar)
- Breadcrumb integration for department selection
- Real data from APIs (no mock data)
- Chat available via global modal (Ctrl+C) or inline tab

Features:
- Department list with growth rates
- Cognitive levels progress
- Monte Carlo distributions
- Time series projections
"""

import asyncio
from datetime import datetime

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Button, Input, Label, Select, Static, TabbedContent, TabPane

from src.cli.v3.tui.services.department_data import (
    LoadingProgress,
    LoadingState,
    get_department_service,
)
from src.cli.v3.tui.services.error_telemetry import (
    get_error_telemetry,
)
from src.cli.v3.tui.services.tajine_service import (
    ProcessingEvent,
    ProcessingState,
    TAJINEChatService,
    TAJINEService,
)
from src.cli.v3.tui.widgets.breadcrumb import Breadcrumb
from src.cli.v3.tui.widgets.cognitive_charts import (
    CognitiveLevelsWidget,
    MonteCarloChart,
    TimeSeriesChart,
)
from src.cli.v3.tui.widgets.department_list import (
    DepartmentData,
    DepartmentList,
    DepartmentSummary,
)
from src.cli.v3.tui.widgets.interactive_map import (
    RegionDetailPanel,
    RegionMetrics,
)


class TAJINEChatWidget(Container):
    """Integrated chat widget for TAJINE conversations."""

    DEFAULT_CSS = """
    TAJINEChatWidget {
        height: 100%;
        border: solid $primary;
        background: $surface;
    }

    TAJINEChatWidget .chat-header {
        height: 2;
        padding: 0 1;
        background: $surface-darken-1;
        border-bottom: solid $primary;
    }

    TAJINEChatWidget .chat-messages {
        height: 1fr;
        padding: 1;
        overflow-y: auto;
    }

    TAJINEChatWidget .chat-input-area {
        height: 3;
        padding: 0 1;
        border-top: solid $primary;
        background: $surface-darken-1;
    }

    TAJINEChatWidget .message {
        margin-bottom: 1;
        padding: 0 1;
    }

    TAJINEChatWidget .message.user {
        background: $primary;
        color: $surface;
        text-align: right;
        margin-left: 5;
    }

    TAJINEChatWidget .message.assistant {
        background: $surface-lighten-1;
        border-left: thick $accent;
        margin-right: 5;
    }
    """

    def __init__(self, chat_service: TAJINEChatService | None = None, **kwargs):
        super().__init__(**kwargs)
        self._chat_service = chat_service or TAJINEChatService()
        self._processing = False

    def compose(self) -> ComposeResult:
        """Create chat layout."""
        yield Static("[bold cyan]🤖 TAJINE Agent[/]", classes="chat-header")
        yield ScrollableContainer(id="tajine-messages", classes="chat-messages")
        with Horizontal(classes="chat-input-area"):
            yield Input(
                placeholder="Demandez une analyse... (ex: Analyse le secteur tech à Lyon)",
                id="tajine-input",
            )
            yield Button("📤", id="send-btn", variant="primary")

    def on_mount(self) -> None:
        """Add welcome message on mount."""
        self._add_message(
            "assistant",
            "Bonjour! Je suis TAJINE, votre assistant d'analyse cognitive. "
            "Posez-moi des questions sur les territoires, secteurs ou tendances.",
        )

    def _add_message(self, role: str, content: str) -> None:
        """Add a message to the chat."""
        messages = self.query_one("#tajine-messages", ScrollableContainer)
        time_str = datetime.now().strftime("%H:%M")

        if role == "user":
            text = f"{content}\n[dim]{time_str}[/]"
        else:
            text = f"[bold cyan]TAJINE[/] [dim]{time_str}[/]\n{content}"

        message = Static(text, classes=f"message {role}")
        messages.mount(message)
        messages.scroll_end(animate=True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        if event.input.id == "tajine-input" and not self._processing:
            message = event.value.strip()
            if message:
                event.input.value = ""
                self._send_message(message)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle send button press."""
        if event.button.id == "send-btn" and not self._processing:
            input_widget = self.query_one("#tajine-input", Input)
            message = input_widget.value.strip()
            if message:
                input_widget.value = ""
                self._send_message(message)

    def _send_message(self, message: str) -> None:
        """Send message to TAJINE."""
        self._add_message("user", message)
        self._processing = True

        # Show typing indicator
        self._add_message("assistant", "[dim]Analyse en cours...[/] [blink]▌[/]")

        # Process asynchronously
        self.run_worker(self._process_message(message))

    async def _process_message(self, message: str) -> None:
        """Process message with TAJINE service."""
        try:
            response = await self._chat_service.send_message(message)

            # Remove typing indicator and add response
            messages = self.query_one("#tajine-messages", ScrollableContainer)
            if messages.children:
                messages.children[-1].remove()

            self._add_message("assistant", response)

            # Emit event to update other widgets
            self.post_message(
                TAJINEScreen.AnalysisComplete(self._chat_service._service.last_result)
            )

        except Exception as e:
            logger.error(f"TAJINE chat error: {e}")
            messages = self.query_one("#tajine-messages", ScrollableContainer)
            if messages.children:
                messages.children[-1].remove()
            self._add_message("assistant", f"[red]Erreur: {e}[/]")

        finally:
            self._processing = False


class QuickAnalysisPanel(Container):
    """Panel for quick analysis actions."""

    DEFAULT_CSS = """
    QuickAnalysisPanel {
        height: auto;
        padding: 1;
        border: solid $primary;
        background: $surface;
    }

    QuickAnalysisPanel .action-row {
        height: auto;
        margin-bottom: 1;
    }

    QuickAnalysisPanel Button {
        margin-right: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Create quick actions layout."""
        yield Label("[bold]Analyses Rapides[/]")

        with Horizontal(classes="action-row"):
            yield Button("🇫🇷 France", id="analyze-france", variant="primary")
            yield Button("🇲🇦 Maroc", id="analyze-morocco", variant="primary")

        with Horizontal(classes="action-row"):
            yield Button("📈 Croissance", id="analyze-growth")
            yield Button("📉 Déclin", id="analyze-decline")
            yield Button("🔄 Comparer", id="analyze-compare")

        with Horizontal(classes="action-row"):
            yield Select(
                [
                    ("Tous secteurs", "all"),
                    ("Technologie", "tech"),
                    ("Santé", "health"),
                    ("Finance", "finance"),
                    ("Industrie", "industry"),
                ],
                value="all",
                id="sector-filter",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle quick action buttons."""
        action_map = {
            "analyze-france": ("Analyse globale France", "france"),
            "analyze-morocco": ("Analyse globale Maroc", "maroc"),
            "analyze-growth": ("Régions en croissance", None),
            "analyze-decline": ("Régions en déclin", None),
            "analyze-compare": ("Comparaison régionale", None),
        }

        if event.button.id in action_map:
            query, territory = action_map[event.button.id]
            self.post_message(TAJINEScreen.QuickAnalysisRequested(query, territory))


class TAJINEScreen(Container):
    """Main TAJINE cognitive analysis content (Container for ContentSwitcher).

    Note: Changed from Screen to Container in TUI v6 to work properly
    with ContentSwitcher layout. All functionality is preserved.

    Uses global sidebar for navigation. Local layout is:
    - Department list (60% height) with summary and details
    - Bottom bar (40% height) with cognitive levels and charts tabs
    """

    BINDINGS = [
        Binding("ctrl+r", "refresh_analysis", "Refresh", show=True),
        Binding("f1", "show_help", "Help", show=True),
        Binding("1", "show_tab('cognitive')", "1:Cogn", show=True),
        Binding("2", "show_tab('charts')", "2:Charts", show=True),
        Binding("3", "show_tab('actions')", "3:Actions", show=True),
    ]

    DEFAULT_CSS = """
    TAJINEScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    /* Department list panel - takes 60% of height */
    #dept-panel {
        height: 3fr;
        min-height: 15;
        border: solid $primary;
        background: $surface;
        layout: vertical;
    }

    #dept-panel DepartmentList {
        height: 1fr;
    }

    #dept-panel DepartmentSummary {
        height: auto;
    }

    /* Bottom bar with metrics/charts - 40% */
    #bottom-bar {
        height: 2fr;
        min-height: 10;
        layout: horizontal;
        padding: 0;
    }

    /* Panels in bottom bar */
    #metrics-panel {
        width: 1fr;
        border: solid $secondary;
        background: $surface;
        margin-right: 1;
    }

    #bottom-panel {
        width: 2fr;
        border: solid $accent;
        background: $surface;
    }

    .panel-title {
        text-align: center;
        text-style: bold;
        background: $primary;
        color: $surface;
        padding: 0 1;
        height: 1;
    }

    /* Cognitive levels widget - compact */
    CognitiveLevelsWidget {
        height: 100%;
    }

    /* Region detail - compact */
    RegionDetailPanel {
        height: auto;
        max-height: 6;
    }

    /* Loading overlay */
    #loading-overlay {
        width: 100%;
        height: 100%;
        background: $surface 80%;
        align: center middle;
        display: none;
    }

    #loading-overlay.visible {
        display: block;
    }

    #loading-text {
        text-align: center;
        padding: 2;
        background: $surface;
        border: solid $primary;
    }
    """

    from textual.message import Message

    class AnalysisComplete(Message):
        """Message when analysis is complete."""

        def __init__(self, result):
            super().__init__()
            self.result = result

    class QuickAnalysisRequested(Message):
        """Message for quick analysis request."""

        def __init__(self, query: str, territory: str | None):
            super().__init__()
            self.query = query
            self.territory = territory

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service = TAJINEService()
        self._chat_service = TAJINEChatService(self._service)
        self._current_country = "france"
        self._dept_service = get_department_service()
        self._loading = False

    def compose(self) -> ComposeResult:
        """Create the TAJINE dashboard layout (TUI v6 - lazy loading).

        Uses lightweight placeholders initially, then loads heavy widgets
        progressively in on_mount to avoid blocking the event loop.
        """
        # Loading screen shown while widgets are mounted
        yield Static(
            "[bold cyan]🔄 Chargement de TAJINE...[/]\n\n[dim]Initialisation des composants...[/]",
            id="init-loading",
        )

        # Department list panel - main focus (placeholder)
        yield Container(id="dept-panel")

        # Loading overlay (shown during API fetch)
        with Container(id="loading-overlay"):
            yield Static(
                "[bold cyan]🔄 Chargement des données SIRENE...[/]\n\n[dim]0 / 96 départements[/]",
                id="loading-text",
            )

        # Bottom bar placeholder - will be populated lazily
        yield Horizontal(id="bottom-bar")

    def on_mount(self) -> None:
        """Initialize on mount with lazy widget loading."""
        self._service.add_event_listener(self._on_processing_event)

        # Register progress callback for loading updates
        self._dept_service.add_progress_callback(self._on_loading_progress)

        # Load heavy widgets progressively (non-blocking)
        self.run_worker(self._lazy_load_widgets())

    async def _lazy_load_widgets(self) -> None:
        """Load heavy widgets progressively to keep UI responsive.

        Uses 150ms delays between widget mounts to allow the event loop
        to process other events (like screen switches) without freezing.
        """
        # Step 1: Mount department panel content
        self.call_later(self._mount_dept_panel)
        await asyncio.sleep(0.15)  # 150ms for UI responsiveness

        # Step 2: Mount metrics panel (left side of bottom bar)
        self.call_later(self._mount_metrics_panel)
        await asyncio.sleep(0.15)

        # Step 3: Mount charts panel (right side of bottom bar)
        self.call_later(self._mount_charts_panel)
        await asyncio.sleep(0.15)

        # Step 4: Hide loading, start data fetch
        self.call_later(self._finish_loading)

    def _mount_dept_panel(self) -> None:
        """Mount department panel widgets."""
        try:
            dept_panel = self.query_one("#dept-panel", Container)
            dept_panel.mount(
                Label(
                    "[bold]🇫🇷 Départements - Croissance Entreprises[/]",
                    classes="panel-title",
                    id="dept-title",
                )
            )
            dept_panel.mount(DepartmentSummary(id="dept-summary"))
            dept_panel.mount(DepartmentList(id="dept-list"))
            dept_panel.mount(RegionDetailPanel(id="region-detail"))
        except Exception as e:
            logger.warning(f"Failed to mount dept panel: {e}")

    def _mount_metrics_panel(self) -> None:
        """Mount metrics panel with cognitive levels and actions."""
        try:
            bottom_bar = self.query_one("#bottom-bar", Horizontal)

            # Create metrics panel with tabs
            metrics_panel = Container(id="metrics-panel")
            bottom_bar.mount(metrics_panel)

            # Add tabbed content
            tabs = TabbedContent()
            metrics_panel.mount(tabs)

            # Note: TabbedContent needs children added via compose or explicit mount
            # Use a simpler structure to avoid complexity
            tabs.mount(
                TabPane("🧠 Niveaux", CognitiveLevelsWidget(id="cognitive-levels"), id="tab-levels")
            )
            tabs.mount(
                TabPane("⚡ Actions", QuickAnalysisPanel(id="quick-actions"), id="tab-actions")
            )
        except Exception as e:
            logger.warning(f"Failed to mount metrics panel: {e}")

    def _mount_charts_panel(self) -> None:
        """Mount charts panel with Monte Carlo and time series."""
        try:
            bottom_bar = self.query_one("#bottom-bar", Horizontal)

            # Create charts panel with tabs
            charts_panel = Container(id="bottom-panel")
            bottom_bar.mount(charts_panel)

            # Add tabbed content
            tabs = TabbedContent()
            charts_panel.mount(tabs)

            tabs.mount(
                TabPane(
                    "📊 Monte Carlo", MonteCarloChart(id="monte-carlo-chart"), id="tab-montecarlo"
                )
            )
            tabs.mount(
                TabPane(
                    "📈 Projection", TimeSeriesChart(id="time-series-chart"), id="tab-projection"
                )
            )
        except Exception as e:
            logger.warning(f"Failed to mount charts panel: {e}")

    def _finish_loading(self) -> None:
        """Hide initial loading and start data fetch."""
        try:
            # Hide initial loading message
            init_loading = self.query_one("#init-loading", Static)
            init_loading.display = False
        except Exception:
            pass

        # Load real data from SIRENE API
        self.run_worker(self._load_real_data())

    def _on_loading_progress(self, progress: LoadingProgress) -> None:
        """Handle loading progress updates from DepartmentDataService.

        Uses call_later to safely update widgets from async worker context.
        """
        # Use call_later to defer widget updates to the main event loop
        # This prevents blocking during tab switches
        self.call_later(self._update_loading_ui, progress)

    def _update_loading_ui(self, progress: LoadingProgress) -> None:
        """Actually update the loading UI (called via call_later)."""
        try:
            loading_text = self.query_one("#loading-text", Static)
            overlay = self.query_one("#loading-overlay")

            if progress.state == LoadingState.LOADING:
                overlay.add_class("visible")
                loading_text.update(
                    f"[bold cyan]🔄 Chargement des données SIRENE...[/]\n\n"
                    f"[dim]{progress.loaded} / {progress.total} départements[/]\n"
                    f"[dim italic]{progress.current_dept}[/]"
                )
            elif progress.state == LoadingState.LOADED:
                overlay.remove_class("visible")
                self.app.notify(f"[green]✓ {progress.total} départements chargés[/]", timeout=3)
            elif progress.state == LoadingState.ERROR:
                overlay.remove_class("visible")
                self.app.notify(f"[red]Erreur: {progress.error}[/]", timeout=5)
        except Exception as e:
            logger.debug(f"Progress update error: {e}")

    async def _load_real_data(self) -> None:
        """Load real department data from SIRENE API.

        Uses call_later for all widget updates to avoid blocking the event loop
        during tab switches.
        """

        telemetry = get_error_telemetry()

        # Show loading state via call_later to not block
        self._loading = True
        self.call_later(self._show_loading_overlay, True)

        try:
            # Fetch real data from SIRENE API
            # Use cache if available, otherwise fetch fresh
            dept_stats = await self._dept_service.fetch_all_departments()

            # Convert DepartmentStats to DepartmentData for the widget
            real_data = {}
            for code, stats in dept_stats.items():
                real_data[code] = DepartmentData(
                    code=stats.code,
                    name=stats.name,
                    growth_rate=stats.growth_rate,
                    companies_count=stats.companies_count,
                    confidence=stats.confidence,
                    top_sector=stats.top_sector,
                )

            # Update department list with real data via call_later
            self.call_later(self._update_department_widgets, real_data, telemetry)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to load real data: {error_msg}")
            telemetry.track_render_error(
                widget="TAJINEScreen", message=f"Real data load failed: {error_msg}", exception=e
            )
            self.call_later(
                lambda msg=error_msg: self.app.notify(
                    f"[red]Erreur chargement API: {msg}[/]", timeout=5
                )
            )

        finally:
            self._loading = False
            self.call_later(self._show_loading_overlay, False)

        # Load cognitive levels (still simulated - requires TAJINE analysis)
        # Yield to event loop before heavy computation
        await asyncio.sleep(0)
        await self._load_cognitive_charts()

    def _show_loading_overlay(self, show: bool) -> None:
        """Show or hide the loading overlay (called via call_later)."""
        try:
            overlay = self.query_one("#loading-overlay")
            if show:
                overlay.add_class("visible")
            else:
                overlay.remove_class("visible")
        except Exception:
            pass

    def _update_department_widgets(self, real_data: dict[str, DepartmentData], telemetry) -> None:
        """Update department widgets with data (called via call_later)."""
        try:
            dept_list = self.query_one("#dept-list", DepartmentList)
            dept_list.update_all_data(real_data)

            dept_summary = self.query_one("#dept-summary", DepartmentSummary)
            dept_summary.update_data(real_data)

            # Update title to show data is real
            title = self.query_one("#dept-title", Label)
            title.update("[bold]🇫🇷 Départements - Données SIRENE[/]")

        except Exception as e:
            telemetry.track_render_error(
                widget="DepartmentList",
                message=f"Department list failed: {e}",
                exception=e,
                context={"dept_count": len(real_data)},
            )

    async def _load_cognitive_charts(self) -> None:
        """Load cognitive level charts (simulated until TAJINE analysis runs).

        Uses call_later for widget updates to avoid blocking the event loop.
        """
        import random

        import numpy as np

        telemetry = get_error_telemetry()

        # Prepare demo cognitive levels data
        from src.cli.v3.tui.widgets.cognitive_charts import CognitiveLevelResult

        demo_levels = [
            ("discovery", 0.85, "rule_based"),
            ("causal", 0.72, "rule_based"),
            ("scenario", 0.88, "monte_carlo"),
            ("strategy", 0.65, "rule_based"),
            ("theoretical", 0.78, "rule_based"),
        ]

        # Update via call_later to not block
        self.call_later(self._update_cognitive_levels, demo_levels, CognitiveLevelResult, telemetry)

        # Yield to event loop
        await asyncio.sleep(0)

        # Prepare Monte Carlo distribution data (numpy computation)
        try:
            samples = np.random.normal(0.12, 0.08, 1000)
            hist, bin_edges = np.histogram(samples, bins=20)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            mc_data = {
                "bins": bin_centers.tolist(),
                "counts": hist.tolist(),
                "percentiles": {
                    10: float(np.percentile(samples, 10)),
                    50: float(np.percentile(samples, 50)),
                    90: float(np.percentile(samples, 90)),
                },
                "mean": float(np.mean(samples)),
            }
            self.call_later(self._update_monte_carlo, mc_data, telemetry)
        except Exception as e:
            logger.debug(f"Monte Carlo computation error: {e}")

        # Yield to event loop
        await asyncio.sleep(0)

        # Prepare time series projection data
        try:
            months = list(range(1, 13))
            base = 1.0
            mean_path = [base * (1 + 0.01 * m + random.uniform(-0.02, 0.02)) for m in months]
            upper_bound = [v * 1.15 for v in mean_path]
            lower_bound = [v * 0.85 for v in mean_path]

            ts_data = {
                "months": months,
                "mean_path": mean_path,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
            }
            self.call_later(self._update_time_series, ts_data, telemetry)
        except Exception as e:
            logger.debug(f"Time series computation error: {e}")

    def _update_cognitive_levels(self, demo_levels, CognitiveLevelResult, telemetry) -> None:
        """Update cognitive levels widget (called via call_later)."""
        try:
            levels_widget = self.query_one("#cognitive-levels", CognitiveLevelsWidget)
            for level, conf, method in demo_levels:
                levels_widget.update_level(
                    level, CognitiveLevelResult(name=level, confidence=conf, method=method)
                )
        except Exception as e:
            telemetry.track_render_error(
                widget="CognitiveLevelsWidget", message=f"Cognitive levels failed: {e}", exception=e
            )

    def _update_monte_carlo(self, mc_data: dict, telemetry) -> None:
        """Update Monte Carlo chart (called via call_later)."""
        try:
            mc_chart = self.query_one("#monte-carlo-chart", MonteCarloChart)
            mc_chart.update_distribution(
                bins=mc_data["bins"],
                counts=mc_data["counts"],
                percentiles=mc_data["percentiles"],
                mean=mc_data["mean"],
            )
        except Exception as e:
            telemetry.track_render_error(
                widget="MonteCarloChart", message=f"Monte Carlo chart failed: {e}", exception=e
            )

    def _update_time_series(self, ts_data: dict, telemetry) -> None:
        """Update time series chart (called via call_later)."""
        try:
            ts_chart = self.query_one("#time-series-chart", TimeSeriesChart)
            ts_chart.update_projection(
                months=ts_data["months"],
                mean_path=ts_data["mean_path"],
                lower_bound=ts_data["lower_bound"],
                upper_bound=ts_data["upper_bound"],
            )
        except Exception as e:
            telemetry.track_render_error(
                widget="TimeSeriesChart", message=f"Time series projection failed: {e}", exception=e
            )

    def _on_processing_event(self, event: ProcessingEvent) -> None:
        """Handle processing events from TAJINE service."""
        try:
            levels_widget = self.query_one("#cognitive-levels", CognitiveLevelsWidget)

            if event.state == ProcessingState.PROCESSING:
                levels_widget.set_active_level(event.level)
            elif event.state == ProcessingState.COMPLETED:
                from src.cli.v3.tui.widgets.cognitive_charts import CognitiveLevelResult

                levels_widget.update_level(
                    event.level,
                    CognitiveLevelResult(
                        name=event.level,
                        confidence=event.confidence,
                        method=event.data.get("method", "rule_based"),
                    ),
                )
        except Exception as e:
            logger.debug(f"Error updating cognitive levels: {e}")

    def on_department_list_department_selected(
        self, event: DepartmentList.DepartmentSelected
    ) -> None:
        """Handle department selection from list."""
        detail_panel = self.query_one("#region-detail", RegionDetailPanel)

        if event.data:
            # Convert DepartmentData to RegionMetrics for the detail panel
            metrics = RegionMetrics(
                code=event.data.code,
                name=event.data.name,
                companies_count=event.data.companies_count,
                growth_rate=event.data.growth_rate,
                confidence=event.data.confidence,
            )
            detail_panel.show_region(metrics)

            # Update breadcrumb (TUI v6)
            try:
                breadcrumb = self.app.query_one("#breadcrumb", Breadcrumb)
                breadcrumb.set_context("Départements")
                breadcrumb.add_detail(f"{event.data.code}-{event.data.name}")
            except Exception:
                pass

            self.app.notify(
                f"📍 {event.data.name} ({event.data.code}): {event.data.growth_rate:+.1%}",
                timeout=3,
            )

    def on_tajine_screen_analysis_complete(self, event: AnalysisComplete) -> None:
        """Handle completed analysis."""
        if event.result:
            output = event.result.cognitive_output

            # Update cognitive levels
            try:
                levels_widget = self.query_one("#cognitive-levels", CognitiveLevelsWidget)
                levels_widget.load_from_output(output)
            except Exception as e:
                logger.debug(f"Error updating cognitive levels: {e}")

            # Update charts if scenario data exists
            scenario = output.get("cognitive_levels", {}).get("scenario", {})
            if scenario:
                try:
                    mc_chart = self.query_one("#monte-carlo-chart", MonteCarloChart)
                    mc_chart.load_from_scenario_output(scenario)

                    ts_chart = self.query_one("#time-series-chart", TimeSeriesChart)
                    ts_chart.load_from_scenario_output(scenario)
                except Exception as e:
                    logger.debug(f"Error updating charts: {e}")

            self.app.notify(
                f"[green]Analyse complète[/] - Confiance: {event.result.confidence:.0%}", timeout=3
            )

    def on_tajine_screen_quick_analysis_requested(self, event: QuickAnalysisRequested) -> None:
        """Handle quick analysis request.

        TUI v6: Quick analysis now uses the global chat modal.
        """
        # Open global chat modal with the query
        try:
            self.app.action_toggle_chat_modal()
            # The query will be typed by the user in the modal
            self.app.notify(f"Chat ouvert - Demandez: {event.query}", timeout=3)
        except Exception as e:
            logger.debug(f"Could not open chat modal: {e}")

    def action_refresh_analysis(self) -> None:
        """Refresh the current analysis with fresh API data."""
        self.app.notify("Actualisation des données SIRENE...", timeout=1)
        # Force refresh to bypass cache
        self._dept_service.clear_cache()
        self.run_worker(self._load_real_data())

    def action_show_help(self) -> None:
        """Show help dialog."""
        help_text = """
[bold]TAJINE - Analyse Cognitive (TUI v6)[/]

[cyan]Raccourcis:[/]
  1      : Onglet Niveaux cognitifs
  2      : Onglet Charts
  3      : Onglet Actions rapides
  Ctrl+R : Rafraîchir l'analyse
  Ctrl+C : Chat modal (global)
  F1     : Afficher cette aide

[cyan]Fonctionnalités:[/]
  • Liste départements par croissance
  • 5 niveaux d'analyse cognitive
  • Simulation Monte Carlo
  • Projections temporelles
        """
        self.app.notify(help_text, timeout=10)

    def action_show_tab(self, tab_name: str) -> None:
        """Switch to a specific tab via keyboard shortcut."""
        try:
            if tab_name == "cognitive":
                tabs = self.query_one("#metrics-panel TabbedContent")
                tabs.active = "tab-levels"
            elif tab_name == "charts":
                tabs = self.query_one("#bottom-panel TabbedContent")
                tabs.active = "tab-montecarlo"
            elif tab_name == "actions":
                tabs = self.query_one("#metrics-panel TabbedContent")
                tabs.active = "tab-actions"

            self.app.notify(f"Onglet: {tab_name}", timeout=1)
        except Exception as e:
            logger.debug(f"Tab switch error: {e}")
