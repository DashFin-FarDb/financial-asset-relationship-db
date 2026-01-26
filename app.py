"""
Financial Asset Relationship Database Visualization.
Refactored for Python 3.12+ compatibility with strict adherence to
PEP 8, Black, Ruff, and MyPy standards.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

import gradio as gr
import plotly.graph_objects as go

# Consolidated and cleaned imports
from src.analysis.formulaic_analysis import FormulaicAnalyzer
from src.analysis.formulaic_visualizer import FormulaicVisualizer
from src.data.real_data_fetcher import create_real_database
from src.graph.asset_graph import Asset, AssetRelationshipGraph
from src.logging import LOGGER
from src.models.financial_models import Asset as FinancialAsset
from src.reports.schema_report import generate_schema_report
from src.visualizations.graph_2d_visuals import visualize_2d_graph
from src.visualizations.graph_visuals import (
    visualize_3d_graph,
    visualize_3d_graph_with_filters,
)
from src.visualizations.metric_visuals import visualize_metrics

# Logger configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
LOGGER = logging.getLogger(__name__)


class AppConstants:
    """Centralized application constants, labels, and UI markdown content."""

    TITLE = "Financial Asset Relationship Database Visualization"

    MARKDOWN_HEADER = """
    # 🏦 Financial Asset Relationship Network
    A comprehensive 3D visualization of interconnected financial assets:
    **Equities, Bonds, Commodities, Currencies, and Regulatory Events**
    """

    TAB_3D_VISUALIZATION = "3D Network Visualization"
    TAB_METRICS_ANALYTICS = "Metrics & Analytics"
    TAB_SCHEMA_RULES = "Schema & Rules"
    TAB_ASSET_EXPLORER = "Asset Explorer"
    TAB_DOCUMENTATION = "Documentation"

    ERROR_LABEL = "Error"
    REFRESH_BUTTON_LABEL = "Refresh Visualization"
    GENERATE_SCHEMA_BUTTON_LABEL = "Generate Schema Report"
    SCHEMA_REPORT_LABEL = "Generate Schema Report"
    SELECT_ASSET_LABEL = "Select Asset"
    ASSET_DETAILS_LABEL = "Asset Details"
    RELATED_ASSETS_LABEL = "Related Assets"
    NETWORK_STATISTICS_LABEL = "Network Statistics"

    INITIAL_GRAPH_ERROR = "Failed to create sample database"
    REFRESH_OUTPUTS_ERROR = "Error refreshing outputs"
    APP_START_INFO = "Starting Financial Asset Relationship Database application"
    APP_LAUNCH_INFO = "Launching Gradio interface"
    APP_START_ERROR = "Failed to start application"

    INTERACTIVE_3D_GRAPH_MD = """
    ## Interactive 3D Network Graph
    Explore asset relationships in 3D. Nodes represent assets; edges show relationship strength.
    **Asset Colors:** 🔵 Equities | 🟢 Bonds | 🟠 Commodities | 🔴 Currencies | 🟣 Derivatives
    """

    NETWORK_METRICS_ANALYSIS_MD = "## Network Metrics & Analytics"
    SCHEMA_RULES_GUIDE_MD = "## Database Schema & Business Rules"
    DETAILED_ASSET_INFO_MD = "## Asset Explorer"

    DOC_MARKDOWN = """
    ## Documentation & Help
    - **3D Visualization**: Interactive network graph exploration.
    - **Metrics**: Quantitative analysis of relationships.
    - **Schema**: Data model and business rules documentation.
    - **Explorer**: Detailed individual asset analysis.
    """

    NETWORK_STATISTICS_TEXT = """Network Statistics:
Total Assets: {total_assets}
Total Relationships: {total_relationships}
Average Relationship Strength: {average_relationship_strength:.3f}
Relationship Density: {relationship_density:.2f}%
Regulatory Events: {regulatory_event_count}

Asset Class Distribution:
{asset_class_distribution}

Top Relationships:
"""


class FinancialAssetApp:
    """Main application class managing state, logic, and the Gradio UI."""

    def __init__(self) -> None:
        """
        Initialize application state and construct the asset relationship graph.

        Sets the initial graph attribute to None and triggers graph construction; graph initialization may raise an exception if building the underlying asset relationship graph fails.
        """
        self.graph: AssetRelationshipGraph | None = None
        self._initialize_graph()

    def _initialize_graph(self) -> None:
        """Builds the asset relationship graph from real financial data."""
        try:
            LOGGER.info("Initializing with real financial data from Yahoo Finance")
            self.graph = create_real_database()
            LOGGER.info("Database initialized with %d assets", len(self.graph.assets))
        except Exception as e:
            LOGGER.error("%s: %s", AppConstants.INITIAL_GRAPH_ERROR, e)
            raise

    def ensure_graph(self) -> AssetRelationshipGraph:
        """
        Ensure the application's asset relationship graph is initialized, initializing it if absent.

        Returns:
            The initialized AssetRelationshipGraph instance.

        Raises:
            RuntimeError: If initialization is attempted but the graph remains uninitialized.
        """
        if self.graph is None:
            self._initialize_graph()
            if self.graph is None:
                raise RuntimeError("Asset graph initialization failed")
        return self.graph

    @staticmethod
    def _update_metrics_text(graph: AssetRelationshipGraph) -> str:
        """
        Builds a human-readable network metrics report for the given asset relationship graph.

        Parameters:
            graph (AssetRelationshipGraph): Graph whose metrics will be summarized.

        Returns:
            report (str): Multi-line text containing totals, averages, distribution JSON, and a numbered list of top relationships in the format "source → target (relationship_type): strength%".
        """
        metrics = graph.calculate_metrics()
        text = AppConstants.NETWORK_STATISTICS_TEXT.format(
            total_assets=metrics["total_assets"],
            total_relationships=metrics["total_relationships"],
            average_relationship_strength=metrics["average_relationship_strength"],
            relationship_density=metrics["relationship_density"],
            regulatory_event_count=metrics["regulatory_event_count"],
            asset_class_distribution=json.dumps(
                metrics["asset_class_distribution"], indent=2
            ),
        )
        for idx, (s, t, rel, strength) in enumerate(metrics["top_relationships"], 1):
            text += f"{idx}. {s} → {t} ({rel}): {strength:.1%}\n"
        return text

    def update_all_metrics_outputs(
        self, graph: AssetRelationshipGraph
    ) -> tuple[go.Figure, go.Figure, go.Figure, str]:
        """
        Create metric figures and a formatted metrics report from the asset relationship graph.

        Returns:
            tuple:
                f1 (plotly.graph_objs.Figure): First metric visualization (e.g., distribution).
                f2 (plotly.graph_objs.Figure): Second metric visualization (e.g., timeline).
                f3 (plotly.graph_objs.Figure): Third metric visualization (e.g., comparison).
                text (str): Human-readable metrics summary produced from the graph.
        """
        f1, f2, f3 = visualize_metrics(graph)
        text = self._update_metrics_text(graph)
        return f1, f2, f3, text

    @staticmethod
    def update_asset_info(
        selected_asset: str | None,
        graph: AssetRelationshipGraph,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Return asset metadata and its incoming and outgoing relationships.

        Parameters:
            selected_asset (str | None): Asset identifier to look up. If `None` or not present in the graph, no data is returned.
            graph (AssetRelationshipGraph): Graph containing assets and relationship mappings.

        Returns:
            tuple[dict[str, Any], dict[str, Any]]: A tuple where the first element is a dictionary representation of the asset (with `asset_class` as a string) and the second element is a dictionary with two keys:
                - "outgoing": mapping of target asset id -> {"relationship_type": str, "strength": number}
                - "incoming": mapping of source asset id -> {"relationship_type": str, "strength": number}
        """
        if not selected_asset or selected_asset not in graph.assets:
            return {}, {"outgoing": {}, "incoming": {}}

        asset: Asset = graph.assets[selected_asset]
        asset_dict = asdict(asset)
        asset_dict["asset_class"] = asset.asset_class.value

        outgoing = {
            target_id: {"relationship_type": rel_type, "strength": strength}
            for target_id, rel_type, strength in graph.relationships.get(
                selected_asset, []
            )
        }
        incoming = {
            src_id: {"relationship_type": rel_type, "strength": strength}
            for src_id, rel_type, strength in graph.incoming_relationships.get(
                selected_asset, []
            )
        }
        return asset_dict, {"outgoing": outgoing, "incoming": incoming}

    def refresh_all_outputs(
        self, graph_state: AssetRelationshipGraph
    ) -> tuple[go.Figure, go.Figure, go.Figure, go.Figure, str, str, Any, Any]:
        """
        Refreshes the app's primary visualizations, metric figures, textual reports, and UI component updates for the current asset graph.

        Parameters:
            graph_state (AssetRelationshipGraph | None): Graph instance to use for generating outputs. If falsy, the app's internal graph will be ensured and used.

        Returns:
            tuple[go.Figure, go.Figure, go.Figure, go.Figure, str, str, Any, Any]:
                A tuple containing, in order:
                - viz_3d: 3D network visualization figure.
                - f1: first metrics/analytics figure (distribution/timeline style).
                - f2: second metrics/analytics figure.
                - f3: third metrics/analytics figure.
                - m_text: plain-text metrics report.
                - schema_report: textual schema/rules report.
                - asset_choices_update: UI update payload for the asset selector (choices and reset value).
                - ui_reset_update: UI update payload for an error/message component (value and visibility).
        """
        try:
            graph = graph_state or self.ensure_graph()
            viz_3d = visualize_3d_graph(graph)
            f1, f2, f3, m_text = self.update_all_metrics_outputs(graph)
            schema_report = generate_schema_report(graph)
            asset_choices = list(graph.assets.keys())

            return (
                viz_3d,
                f1,
                f2,
                f3,
                m_text,
                schema_report,
                gr.update(choices=asset_choices, value=None),
                gr.update(value="", visible=False),
            )
        except Exception:
            LOGGER.exception(AppConstants.REFRESH_OUTPUTS_ERROR)
            empty = go.Figure()
            return (
                empty,
                empty,
                empty,
                empty,
                "",
                "",
                gr.update(choices=[]),
                gr.update(
                    value=f"Error: {AppConstants.REFRESH_OUTPUTS_ERROR}", visible=True
                ),
            )

    def refresh_visualization(
        self,
        graph_state: AssetRelationshipGraph,
        view_mode: str,
        layout_type: str,
        *filters: bool,
    ) -> tuple[go.Figure, Any]:
        """
        Create a 2D or 3D network visualization filtered by the provided flags.

        Parameters:
            graph_state (AssetRelationshipGraph): The asset relationship graph or state object to visualize.
            view_mode (str): "2D" to produce a 2D layout; any other value produces a 3D visualization.
            layout_type (str): Layout algorithm or style name used for 2D layouts.
            *filters (bool): Boolean flags in the order:
                (show_same_sector, show_market_cap, show_correlation,
                 show_corporate_bond, show_commodity_currency, show_income_comparison,
                 show_regulatory, show_all_relationships, toggle_arrows).

        Returns:
            tuple:
                - Plotly Figure: The generated visualization figure.
                - Any: A UI update object controlling visibility or presenting an error message.
                On error, returns an empty Figure and a visible error update indicating the refresh failed.
        """
        try:
            graph = graph_state or self.ensure_graph()
            s_sec, s_mc, s_corr, s_cb, s_cc, s_ic, s_reg, s_all, t_arr = filters

            if view_mode == "2D":
                fig = visualize_2d_graph(
                    graph,
                    show_same_sector=s_sec,
                    show_market_cap=s_mc,
                    show_correlation=s_corr,
                    show_corporate_bond=s_cb,
                    show_commodity_currency=s_cc,
                    show_income_comparison=s_ic,
                    show_regulatory=s_reg,
                    show_all_relationships=s_all,
                    layout_type=layout_type,
                )
            else:
                fig = visualize_3d_graph_with_filters(
                    graph,
                    show_same_sector=s_sec,
                    show_market_cap=s_mc,
                    show_correlation=s_corr,
                    show_corporate_bond=s_cb,
                    show_commodity_currency=s_cc,
                    show_income_comparison=s_ic,
                    show_regulatory=s_reg,
                    show_all_relationships=s_all,
                    toggle_arrows=t_arr,
                )
            return fig, gr.update(visible=False)
        except Exception:
            LOGGER.exception("Error refreshing visualization")
            return go.Figure(), gr.update(
                value="Error refreshing visualization", visible=True
            )

    def generate_formulaic_analysis(
        self, graph_state: AssetRelationshipGraph | None
    ) -> tuple[go.Figure, go.Figure, go.Figure, Any, str, Any]:
        """
        Run formulaic analysis on the provided asset relationship graph and produce visualization objects plus UI updates.

        Parameters:
            graph_state (AssetRelationshipGraph | None): Optional graph to analyze. If None, the app's internal graph is used.

        Returns:
            tuple:
                - dashboard_figure (go.Figure): Main formula dashboard visualization.
                - correlation_network_figure (go.Figure): Network figure for empirical correlations.
                - comparison_chart_figure (go.Figure): Metric comparison chart across formulas.
                - choices_update (Any): UI update containing available formula choices and a selected value (or None).
                - summary_text (str): Human-readable summary of the analysis results.
                - visibility_update (Any): UI update controlling visibility of formula-detail components.

        Error behavior:
            On analysis failure, returns three empty figures, an empty choices update, the string "Analysis error", and a visibility update indicating an error state.
        """
        try:
            graph = graph_state or self.ensure_graph()
            analyzer = (
                FormulaicAnalyzer()
            )  # Fixed typo: FormulaicdAnalyzer -> FormulaicAnalyzer
            visualizer = FormulaicVisualizer()
            results = analyzer.analyze_graph(graph)

            dash = visualizer.create_formula_dashboard(results)
            corr_net = visualizer.create_correlation_network(
                results.get("empirical_relationships", {})
            )
            comp_chart = visualizer.create_metric_comparison_chart(results)

            choices = [f.name for f in results.get("formulas", [])]
            summary_text = self._format_formula_summary(
                results.get("summary", {}), results
            )

            return (
                dash,
                corr_net,
                comp_chart,
                gr.update(choices=choices, value=choices[0] if choices else None),
                summary_text,
                gr.update(visible=False),
            )
        except Exception:
            LOGGER.exception("Error generating formulaic analysis")
            empty = go.Figure()
            return (
                empty,
                empty,
                empty,
                gr.update(choices=[]),
                "Analysis error",
                gr.update(visible=True),
            )

    @staticmethod
    def show_formula_details(
        formula_name: str, graph: AssetRelationshipGraph
    ) -> tuple[go.Figure, Any]:
        """
        Return a figure presenting details for the specified formula and a UI update for the detail panel.

        Parameters:
                formula_name (str): The name of the formula to display.
                graph (AssetRelationshipGraph): Graph used to derive or locate formula-related data.

        Returns:
                tuple[go.Figure, Any]: A Plotly figure with the formula details and a Gradio update object for the details panel (for example, visibility or value updates).
        """
        return go.Figure(), gr.update(visible=False)

    @staticmethod
    def _format_formula_summary(summary: dict, results: dict) -> str:
        """
        Builds a markdown-formatted summary of formulaic analysis results.

        Parameters:
            summary (dict): Aggregate summary metrics, expected keys include
                'avg_r_squared' (float), 'empirical_data_points' (int), and optional
                'key_insights' (iterable of str).
            results (dict): Full analysis results; expected keys include
                'formulas' (iterable) and 'empirical_relationships' (dict) which may
                contain 'strongest_correlations' (iterable of dicts with 'pair' and 'correlation').

        Returns:
            str: Markdown text containing totals, average R², empirical data point count,
            optional key insights, and up to the top three correlations.
        """
        formulas = results.get("formulas", [])
        empirical = results.get("empirical_relationships", {})
        lines = [
            "**Formulaic Analysis Summary**",
            f"\nTotal formulas identified: {len(formulas)}",
            f"Average reliability (R²): {summary.get('avg_r_squared', 0.0):.3f}",
            f"Empirical data points: {summary.get('empirical_data_points', 0)}",
        ]
        if insights := summary.get("key_insights"):
            lines.extend(["\nKey insights:"] + [f"- {i}" for i in insights])
        if correlations := empirical.get("strongest_correlations"):
            lines.extend(
                ["\nTop Correlations:"]
                + [f"- {c['pair']}: {c['correlation']:.3f}" for c in correlations[:3]]
            )
        return "\n".join(lines)

    def create_interface(self) -> gr.Blocks:
        """
        Builds the Gradio interface for the application and wires its widgets to event handlers.

        Constructs all tabs, controls, plots, and state used by the app and connects buttons, selectors,
        and controls to the corresponding FinancialAssetApp handlers so the UI is fully interactive.

        Returns:
            gr.Blocks: The constructed Gradio Blocks object representing the complete UI.
        """
        ui = gr.Blocks(title=AppConstants.TITLE)
        with ui:
            gr.Markdown(AppConstants.MARKDOWN_HEADER)
            error_box = gr.Textbox(
                label=AppConstants.ERROR_LABEL, visible=False, interactive=False
            )

            with gr.Tabs():
                with gr.Tab("🌐 Network Visualization"):
                    gr.Markdown(AppConstants.INTERACTIVE_3D_GRAPH_MD)
                    with gr.Row():
                        view_mode = gr.Radio(
                            label="Mode", choices=["3D", "2D"], value="3D"
                        )
                        layout_type = gr.Radio(
                            label="2D Layout",
                            choices=["spring", "circular", "grid"],
                            value="spring",
                            visible=False,
                        )
                    with gr.Row():
                        s_sec = gr.Checkbox(label="Sector", value=True)
                        s_mc = gr.Checkbox(label="Market Cap", value=True)
                        s_corr = gr.Checkbox(label="Correlation", value=True)
                        s_cb = gr.Checkbox(label="Corp Bond", value=True)
                        s_cc = gr.Checkbox(label="Comm/Curr", value=True)
                        s_ic = gr.Checkbox(label="Income", value=True)
                        s_reg = gr.Checkbox(label="Regulatory", value=True)
                        s_all = gr.Checkbox(label="All", value=True)
                        t_arr = gr.Checkbox(label="Arrows", value=True)
                    viz_plot = gr.Plot()
                    with gr.Row():
                        refresh_btn = gr.Button(
                            AppConstants.REFRESH_BUTTON_LABEL, variant="primary"
                        )
                        reset_btn = gr.Button("Reset View", variant="secondary")

                with gr.Tab(AppConstants.TAB_METRICS_ANALYTICS):
                    with gr.Row():
                        a_dist = gr.Plot()
                        r_dist = gr.Plot()
                    e_timeline = gr.Plot()
                    m_text = gr.Textbox(
                        label=AppConstants.NETWORK_STATISTICS_LABEL,
                        lines=10,
                        interactive=False,
                    )
                    refresh_m_btn = gr.Button("Refresh Metrics")

                with gr.Tab(AppConstants.TAB_SCHEMA_RULES):
                    s_report = gr.Textbox(
                        label=AppConstants.SCHEMA_REPORT_LABEL,
                        lines=25,
                        interactive=False,
                    )
                    refresh_s_btn = gr.Button(AppConstants.GENERATE_SCHEMA_BUTTON_LABEL)

                with gr.Tab(AppConstants.TAB_ASSET_EXPLORER):
                    a_selector = gr.Dropdown(
                        label=AppConstants.SELECT_ASSET_LABEL, choices=[]
                    )
                    a_details = gr.JSON(label=AppConstants.ASSET_DETAILS_LABEL)
                    a_rels = gr.JSON(label=AppConstants.RELATED_ASSETS_LABEL)
                    refresh_e_btn = gr.Button("Refresh Explorer")

                with gr.Tab("📊 Formulaic Analysis"):
                    with gr.Row():
                        f_dash = gr.Plot(scale=2)
                        with gr.Column(scale=1):
                            f_selector = gr.Dropdown(label="Select Formula")
                            f_detail = gr.Plot()
                    with gr.Row():
                        c_net = gr.Plot()
                        m_comp = gr.Plot()
                    f_sum = gr.Textbox(
                        label="Analysis Summary", lines=5, interactive=False
                    )
                    refresh_f_btn = gr.Button("Refresh Formulaic Analysis")

            graph_state = gr.State(value=self.graph)

            # Global Refreshes
            refresh_outs = [
                viz_plot,
                a_dist,
                r_dist,
                e_timeline,
                m_text,
                s_report,
                a_selector,
                error_box,
            ]
            for btn in [refresh_btn, refresh_m_btn, refresh_s_btn, refresh_e_btn]:
                btn.click(
                    self.refresh_all_outputs, inputs=[graph_state], outputs=refresh_outs
                )

            # Visualization Logic
            v_inputs = [
                graph_state,
                view_mode,
                layout_type,
                s_sec,
                s_mc,
                s_corr,
                s_cb,
                s_cc,
                s_ic,
                s_reg,
                s_all,
                t_arr,
            ]
            view_mode.change(
                lambda m: gr.update(visible=m == "2D"),
                inputs=[view_mode],
                outputs=[layout_type],
            )
            for ctrl in v_inputs[1:]:
                ctrl.change(
                    self.refresh_visualization,
                    inputs=v_inputs,
                    outputs=[viz_plot, error_box],
                )
            reset_btn.click(
                self.refresh_visualization,
                inputs=v_inputs,
                outputs=[viz_plot, error_box],
            )

            # Logic Handlers
            a_selector.change(
                self.update_asset_info,
                inputs=[a_selector, graph_state],
                outputs=[a_details, a_rels],
            )
            refresh_f_btn.click(
                self.generate_formulaic_analysis,
                inputs=[graph_state],
                outputs=[f_dash, c_net, m_comp, f_selector, f_sum, error_box],
            )
            f_selector.change(
                self.show_formula_details,
                inputs=[f_selector, graph_state],
                outputs=[f_detail, error_box],
            )

        return ui


if __name__ == "__main__":
    try:
        LOGGER.info(AppConstants.APP_START_INFO)
        app_instance = FinancialAssetApp()
        demo = app_instance.create_interface()
        demo.launch()
    except Exception as exc:
        LOGGER.error("%s: %s", AppConstants.APP_START_ERROR, exc)
