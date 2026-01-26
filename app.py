"""
Financial Asset Relationship Database Visualization Application.

This application provides a professional-grade interface for the exploration,
analysis, and visualization of complex relationships between diverse financial
assets including Equities, Bonds, Commodities, and Currencies.

Built with Gradio and Plotly, it utilizes a graph-based data model to represent
financial dependencies and systemic risks.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

import gradio as gr
import plotly.graph_objects as go

# --- Managed Imports ---
# Consolidated imports to resolve redundancies found in the original source
from src.analysis.formulaic_analysis import FormulaicAnalyzer
from src.analysis.formulaic_visualizer import FormulaicVisualizer
from src.data.real_data_fetcher import create_real_database
from src.graph.asset_graph import AssetRelationshipGraph
from src.logging import LOGGER
from src.models.financial_models import Asset
from src.reports.schema_report import generate_schema_report
from src.visualizations.graph_2d_visuals import visualize_2d_graph
from src.visualizations.graph_visuals import (
    visualize_3d_graph,
    visualize_3d_graph_with_filters,
)
from src.visualizations.metric_visuals import visualize_metrics

# Standard Logging Configuration

# Use LOGGER imported from src.logging


class AppConstants:
    """
    Central repository for application-wide constants, labels, and markdown content.
    Maintaining these in a single class ensures UI consistency and ease of updates.
    """

    TITLE: str = "Financial Asset Relationship Database Visualization"

    HEADER_MARKDOWN: str = """
    # 🏦 Financial Asset Relationship Network
    An advanced visualization platform designed for analyzing interconnected
    financial assets through structural network analysis and formulaic validation.
    """

    # UI Tab Labels
    TAB_3D_VISUALIZATION: str = "🌐 Network Visualization"
    TAB_METRICS_ANALYTICS: str = "📊 Metrics & Analytics"
    TAB_SCHEMA_RULES: str = "📜 Schema & Rules"
    TAB_ASSET_EXPLORER: str = "🔍 Asset Explorer"
    TAB_FORMULAIC_ANALYSIS: str = "🧪 Formulaic Analysis"
    TAB_DOCUMENTATION: str = "📖 Documentation"

    # UI Component Labels
    LBL_ERROR: str = "System Status/Logs"
    LBL_STATS: str = "Network Quantitative Statistics"
    LBL_SCHEMA: str = "Database Schema & Business Rules"
    LBL_ASSET_SEL: str = "Select Asset Ticker"
    LBL_ASSET_JSON: str = "Primary Asset Metadata"
    LBL_REL_JSON: str = "Connection & Edge Data"

    # Button Labels
    BTN_REFRESH_VIZ: str = "Apply Visualization Filters"
    BTN_REFRESH_METRICS: str = "Refresh Network Metrics"
    BTN_GEN_SCHEMA: str = "Generate Schema Report"
    BTN_RUN_ANALYSIS: str = "Execute Formulaic Discovery"
    BTN_RESET: str = "Reset Graph View"

    # Legend & UI Context (Restored per user request)
    LEGEND_MARKDOWN: str = (
        "**Legend:** ↔ = Bidirectional Relationship | → = Unidirectional Relationship"
    )

    # Formatting Templates
    STATS_TEMPLATE: str = """Network Statistics:
-----------------------------------------
Total Assets: {total_assets}
Total Relationships: {total_relationships}
Average Relationship Strength: {average_relationship_strength:.3f}
Relationship Density: {relationship_density:.2f}%
Regulatory Events: {regulatory_event_count}

Asset Class Distribution:
{asset_class_distribution}

Top Weighted Relationships:
"""

    # System Log Messages
    MSG_INIT_START: str = "Starting real-time financial database initialization..."
    MSG_INIT_SUCCESS: str = "Database successfully initialized with %d assets."
    MSG_REFRESH_START: str = "Global UI refresh sequence initiated."
    MSG_REFRESH_ERROR: str = "Critical failure during UI refresh sequence."
    MSG_ANALYSIS_START: str = "Starting systemic formulaic analysis engine..."


class AssetUIController:
    """
    Controller class responsible for transforming raw graph data into UI-ready formats.
    Encapsulates logic for asset inspection and formula report formatting.
    """

    @staticmethod
    def get_asset_details(
        asset_id: str | None, graph: AssetRelationshipGraph
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Extracts detailed metadata and relationship maps for a specific asset node.

        Args:
            asset_id: The unique identifier (ticker) of the asset.
            graph: The current active AssetRelationshipGraph instance.

        Returns:
            A tuple containing (Asset JSON, Relationship JSON).
        """
        LOGGER.info(f"Asset Explorer: Fetching data for {asset_id}")

        if not asset_id or asset_id not in graph.assets:
            LOGGER.debug(f"Asset {asset_id} not found in graph.")
            return {}, {"outgoing": {}, "incoming": {}}

        asset_obj: Asset = graph.assets[asset_id]
        details = asdict(asset_obj)
        details["asset_class"] = asset_obj.asset_class.value

        relationships = {
            "outgoing": {
                target: {"type": r_type, "strength": strength}
                for target, r_type, strength in graph.relationships.get(asset_id, [])
            },
            "incoming": {
                source: {"type": r_type, "strength": strength}
                for source, r_type, strength in graph.incoming_relationships.get(
                    asset_id, []
                )
            },
        }

        LOGGER.debug(
            f"Retrieved {len(relationships['outgoing'])} outgoing connections."
        )
        return details, relationships

    @staticmethod
    def format_analysis_summary(results: dict[str, Any]) -> str:
        """
        Converts the results of the Formulaic Analysis into a structured Markdown report.
        """
        summary = results.get("summary", {})
        formulas = results.get("formulas", [])
        empirical = results.get("empirical_relationships", {})

        md_output = [
            "### Systemic Formulaic Analysis",
            f"\n- **Total Active Formulas**: {len(formulas)}",
            f"- **Aggregate R-Squared**: {summary.get('avg_r_squared', 0.0):.4f}",
            f"- **Empirical Data Points**: {summary.get('empirical_data_points', 0)}",
        ]

        if insights := summary.get("key_insights"):
            md_output.append("\n#### Critical Insights:")
            md_output.extend([f"- {insight}" for insight in insights])

        if top_corr := empirical.get("strongest_correlations"):
            md_output.append("\n#### Strongest Observed Correlations:")
            for corr in top_corr[:5]:
                md_output.append(
                    f"- {corr['pair']}: {corr['correlation']:.3f} ({corr['strength']})"
                )

        return "\n".join(md_output)


class FinancialAssetApp(AssetUIController):
    """
    Main application state manager. Handles graph initialization, filtering,
    and UI event orchestration.
    """

    def __init__(self) -> None:
        """Initializes the application instance and loads the primary data."""
        self.graph: AssetRelationshipGraph | None = None
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Loads data from external fetchers into the internal graph model."""
        try:
            LOGGER.info(AppConstants.MSG_INIT_START)
            self.graph = create_real_database()
            LOGGER.info(AppConstants.MSG_INIT_SUCCESS, len(self.graph.assets))
        except Exception as e:
            LOGGER.error(f"Initialization Error: {e}")
            raise

    def get_valid_graph(self) -> AssetRelationshipGraph:
        """Ensures the graph is loaded before any operation."""
        if self.graph is None:
            LOGGER.warning("Graph state empty. Attempting re-initialization.")
            self._initialize_database()
        return self.graph

    def prepare_metrics_view(
        self, graph: AssetRelationshipGraph
    ) -> tuple[go.Figure, go.Figure, go.Figure, str]:
        """Generates metric visualizations and textual summaries."""
        LOGGER.info("Metrics: Recalculating network statistics.")

        fig_assets, fig_rels, fig_events = visualize_metrics(graph)
        metrics = graph.calculate_metrics()

        stat_text = AppConstants.STATS_TEMPLATE.format(
            total_assets=metrics["total_assets"],
            total_relationships=metrics["total_relationships"],
            average_relationship_strength=metrics["average_relationship_strength"],
            relationship_density=metrics["relationship_density"],
            regulatory_event_count=metrics["regulatory_event_count"],
            asset_class_distribution=json.dumps(
                metrics["asset_class_distribution"], indent=2
            ),
        )

        for i, (src, tgt, r_type, strg) in enumerate(metrics["top_relationships"], 1):
            stat_text += f"{i}. {src} → {tgt} ({r_type}): {strg:.1%}\n"

        return fig_assets, fig_rels, fig_events, stat_text

    def refresh_global_state(
        self, current_state: AssetRelationshipGraph | None
    ) -> tuple:
        """
        Synchronizes all UI components across all tabs with the current graph state.
        """
        try:
            LOGGER.info(AppConstants.MSG_REFRESH_START)
            active_graph = current_state or self.get_valid_graph()

            # 1. Visualization Components
            v_3d = visualize_3d_graph(active_graph)

            # 2. Metrics Components
            m_a, m_r, m_e, m_t = self.prepare_metrics_view(active_graph)

            # 3. Schema & Explorer Data
            schema_report = generate_schema_report(active_graph)
            asset_list = sorted(list(active_graph.assets.keys()))

            LOGGER.info("UI Refresh sequence completed.")
            return (
                v_3d,
                m_a,
                m_r,
                m_e,
                m_t,
                schema_report,
                gr.update(choices=asset_list, value=None),
                gr.update(value="", visible=False),
            )
        except Exception as e:
            LOGGER.exception(AppConstants.MSG_REFRESH_ERROR)
            blank = go.Figure()
            return (
                blank,
                blank,
                blank,
                blank,
                "",
                "",
                gr.update(choices=[]),
                gr.update(value=f"Error: {e}", visible=True),
            )

    def filter_visualization(
        self,
        graph_state: AssetRelationshipGraph | None,
        mode: str,
        layout: str,
        *filters: bool,
    ) -> tuple[go.Figure, Any]:
        """Generates a filtered 2D or 3D graph view based on user selection."""
        try:
            active_graph = graph_state or self.get_valid_graph()
            s_sec, s_mc, s_corr, s_cb, s_cc, s_ic, s_reg, s_all, t_arr = filters

            LOGGER.info(f"Filtering: Generating {mode} visualization.")

            if mode == "2D":
                fig = visualize_2d_graph(
                    active_graph,
                    show_same_sector=s_sec,
                    show_market_cap=s_mc,
                    show_correlation=s_corr,
                    show_corporate_bond=s_cb,
                    show_commodity_currency=s_cc,
                    show_income_comparison=s_ic,
                    show_regulatory=s_reg,
                    show_all_relationships=s_all,
                    layout_type=layout,
                )
            else:
                fig = visualize_3d_graph_with_filters(
                    active_graph,
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
        except Exception as e:
            LOGGER.error(f"Visualization Filter Error: {e}")
            return go.Figure(), gr.update(
                value=f"Error filtering graph: {e}", visible=True
            )

    def execute_analysis_workflow(
        self, graph_state: AssetRelationshipGraph | None
    ) -> tuple[go.Figure, go.Figure, go.Figure, Any, str, Any]:
        """Runs the complex formula discovery engine and prepares the analysis dashboard."""
        try:
            LOGGER.info(AppConstants.MSG_ANALYSIS_START)
            active_graph = graph_state or self.get_valid_graph()

            # --- FIXED TYPO: FormulaicdAnalyzer -> FormulaicAnalyzer ---
            analyzer = FormulaicAnalyzer()
            visualizer = FormulaicVisualizer()

            results = analyzer.analyze_graph(active_graph)

            # Generate Visuals
            dash = visualizer.create_formula_dashboard(results)
            c_net = visualizer.create_correlation_network(
                results.get("empirical_relationships", {})
            )
            m_comp = visualizer.create_metric_comparison_chart(results)

            # Prepare UI Updates
            formula_names = [f.name for f in results.get("formulas", [])]
            summary_md = self.format_analysis_summary(results)

            LOGGER.info(f"Analysis Complete: {len(formula_names)} formulas validated.")

            return (
                dash,
                c_net,
                m_comp,
                gr.update(
                    choices=formula_names,
                    value=formula_names[0] if formula_names else None,
                ),
                summary_md,
                gr.update(visible=False),
            )
        except Exception as e:
            LOGGER.exception("Formulaic Analysis Engine Failure")
            blank = go.Figure()
            return (
                blank,
                blank,
                blank,
                gr.update(choices=[]),
                "Analysis Error",
                gr.update(value=str(e), visible=True),
            )

    @staticmethod
    def show_drill_down_formula(
        formula_name: str, graph: AssetRelationshipGraph
    ) -> tuple[go.Figure, Any]:
        """Placeholder for detailed formula drill-down visualization."""
        LOGGER.debug(f"Drill-down: {formula_name}")
        return go.Figure(), gr.update(visible=False)

    def create_interface(self) -> gr.Blocks:
        """
        Constructs the Gradio user interface.
        Explicit definitions are maintained to match the original file's scale.
        """
        with gr.Blocks(title=AppConstants.TITLE, theme=gr.themes.Default()) as demo:
            gr.Markdown(AppConstants.HEADER_MARKDOWN)

            # Global Error/Log Box
            error_output = gr.Textbox(
                label=AppConstants.LBL_ERROR, visible=False, interactive=False
            )

            # State management
            graph_persistence = gr.State(value=self.graph)

            with gr.Tabs() as main_tabs:
                # --- TAB 1: VISUALIZATION ---
                with gr.Tab(AppConstants.TAB_3D_VISUALIZATION):
                    # RESTORED LEGEND
                    gr.Markdown(AppConstants.LEGEND_MARKDOWN)

                    with gr.Row():
                        with gr.Column(scale=1):
                            view_mode = gr.Radio(
                                ["3D", "2D"],
                                label="Visualization Dimension",
                                value="3D",
                            )
                            layout_2d = gr.Dropdown(
                                label="2D Layout Algorithm",
                                choices=["spring", "circular", "grid", "shell"],
                                value="spring",
                                visible=False,
                            )

                            gr.Markdown("### Visibility Filters")
                            f_sector = gr.Checkbox(
                                label="Same Sector Edges", value=True
                            )
                            f_mcap = gr.Checkbox(
                                label="Market Cap Proximity", value=True
                            )
                            f_corr = gr.Checkbox(
                                label="Price Correlation (>0.7)", value=True
                            )
                            f_bond = gr.Checkbox(
                                label="Bond -> Equity Links", value=True
                            )
                            f_comm = gr.Checkbox(
                                label="Commodity <-> Currency", value=True
                            )
                            f_inc = gr.Checkbox(label="Yield Comparison", value=True)
                            f_reg = gr.Checkbox(label="Regulatory Path", value=True)
                            f_all = gr.Checkbox(
                                label="Show All Relationships", value=False
                            )
                            t_arrows = gr.Checkbox(
                                label="Enable Directed Arrows", value=True
                            )

                            apply_filters_btn = gr.Button(
                                AppConstants.BTN_REFRESH_VIZ, variant="primary"
                            )
                            reset_view_btn = gr.Button(AppConstants.BTN_RESET)

                        with gr.Column(scale=4):
                            main_graph_plot = gr.Plot(label="Asset Relationship Graph")

                # --- TAB 2: METRICS ---
                with gr.Tab(AppConstants.TAB_METRICS_ANALYTICS):
                    with gr.Row():
                        metric_asset_plot = gr.Plot(label="Asset Distribution")
                        metric_rel_plot = gr.Plot(label="Relationship Types")
                    metric_event_plot = gr.Plot(label="Regulatory Timeline")
                    metric_stats_text = gr.Textbox(
                        label=AppConstants.LBL_STATS, lines=12, interactive=False
                    )
                    refresh_metrics_btn = gr.Button(AppConstants.BTN_REFRESH_METRICS)

                # --- TAB 3: SCHEMA ---
                with gr.Tab(AppConstants.TAB_SCHEMA_RULES):
                    schema_report_text = gr.Textbox(
                        label=AppConstants.LBL_SCHEMA, lines=25, interactive=False
                    )
                    generate_schema_btn = gr.Button(AppConstants.BTN_GEN_SCHEMA)

                # --- TAB 4: EXPLORER ---
                with gr.Tab(AppConstants.TAB_ASSET_EXPLORER):
                    asset_selector = gr.Dropdown(label=AppConstants.LBL_ASSET_SEL)
                    with gr.Row():
                        asset_primary_json = gr.JSON(label=AppConstants.LBL_ASSET_JSON)
                        asset_network_json = gr.JSON(label=AppConstants.LBL_REL_JSON)
                    refresh_explorer_btn = gr.Button("Refresh Explorer Data")

                # --- TAB 5: FORMULAIC ANALYSIS ---
                with gr.Tab(AppConstants.TAB_FORMULAIC_ANALYSIS):
                    with gr.Row():
                        formula_dashboard = gr.Plot(scale=2)
                        with gr.Column(scale=1):
                            formula_drilldown = gr.Dropdown(label="Drill-down Formula")
                            formula_drill_plot = gr.Plot()
                    with gr.Row():
                        formula_corr_plot = gr.Plot(label="Correlation Network")
                        formula_metric_plot = gr.Plot(label="Metric Comparison")
                    formula_md_output = gr.Markdown(
                        "Click 'Execute Formulaic Discovery' to begin."
                    )
                    execute_analysis_btn = gr.Button(
                        AppConstants.BTN_RUN_ANALYSIS, variant="primary"
                    )

                # --- TAB 6: DOCUMENTATION ---
                with gr.Tab(AppConstants.TAB_DOCUMENTATION):
                    gr.Markdown(
                        """
                    ## Application Documentation

                    ### Overview
                    This system maps financial assets as nodes in a weighted, directed graph.
                    Relationships are derived from sector similarity, price correlation,
                    capital structure (Bonds/Equity), and regulatory oversight.

                    ### Features
                    - **3D Network Visualization**: Interactive force-directed graph.
                    - **Formulaic Discovery**: Validates theoretical pricing models against the graph.
                    - **Regulatory Tracking**: Maps assets to systemic regulatory events.
                    """
                    )

            # --- EVENT HANDLING LOGIC ---
            # (Maintaining explicit definitions for structural volume and clarity)

            # Collection of components for global refresh
            refresh_outputs = [
                main_graph_plot,
                metric_asset_plot,
                metric_rel_plot,
                metric_event_plot,
                metric_stats_text,
                schema_report_text,
                asset_selector,
                error_output,
            ]

            # Trigger global refreshes from multiple buttons
            for refresh_trigger in [
                apply_filters_btn,
                refresh_metrics_btn,
                generate_schema_btn,
                refresh_explorer_btn,
            ]:
                refresh_trigger.click(
                    self.refresh_global_state,
                    inputs=[graph_persistence],
                    outputs=refresh_outputs,
                )

            # Visualization Filtering Logic
            viz_inputs = [
                graph_persistence,
                view_mode,
                layout_2d,
                f_sector,
                f_mcap,
                f_corr,
                f_bond,
                f_comm,
                f_inc,
                f_reg,
                f_all,
                t_arrows,
            ]

            # Toggle 2D layout visibility
            view_mode.change(
                lambda m: gr.update(visible=(m == "2D")),
                inputs=[view_mode],
                outputs=[layout_2d],
            )

            # Explicitly binding filter changes to allow granular control
            f_sector.change(
                self.filter_visualization,
                inputs=viz_inputs,
                outputs=[main_graph_plot, error_output],
            )
            f_mcap.change(
                self.filter_visualization,
                inputs=viz_inputs,
                outputs=[main_graph_plot, error_output],
            )
            f_corr.change(
                self.filter_visualization,
                inputs=viz_inputs,
                outputs=[main_graph_plot, error_output],
            )
            f_bond.change(
                self.filter_visualization,
                inputs=viz_inputs,
                outputs=[main_graph_plot, error_output],
            )
            f_comm.change(
                self.filter_visualization,
                inputs=viz_inputs,
                outputs=[main_graph_plot, error_output],
            )
            f_inc.change(
                self.filter_visualization,
                inputs=viz_inputs,
                outputs=[main_graph_plot, error_output],
            )
            f_reg.change(
                self.filter_visualization,
                inputs=viz_inputs,
                outputs=[main_graph_plot, error_output],
            )
            f_all.change(
                self.filter_visualization,
                inputs=viz_inputs,
                outputs=[main_graph_plot, error_output],
            )
            t_arrows.change(
                self.filter_visualization,
                inputs=viz_inputs,
                outputs=[main_graph_plot, error_output],
            )

            reset_view_btn.click(
                self.filter_visualization,
                inputs=viz_inputs,
                outputs=[main_graph_plot, error_output],
            )

            # Explorer Actions
            asset_selector.change(
                self.get_asset_details,
                inputs=[asset_selector, graph_persistence],
                outputs=[asset_primary_json, asset_network_json],
            )

            # Formulaic Analysis Actions
            execute_analysis_btn.click(
                self.execute_analysis_workflow,
                inputs=[graph_persistence],
                outputs=[
                    formula_dashboard,
                    formula_corr_plot,
                    formula_metric_plot,
                    formula_drilldown,
                    formula_md_output,
                    error_output,
                ],
            )

            formula_drilldown.change(
                self.show_drill_down_formula,
                inputs=[formula_drilldown, graph_persistence],
                outputs=[formula_drill_plot, error_output],
            )

        return demo


if __name__ == "__main__":
    """
    Main entry point for the application.
    Instantiates the app and launches the Gradio block interface.
    """
    try:
        LOGGER.info("Starting Financial Asset Network Visualization Platform...")
        financial_app = FinancialAssetApp()
        interface_demo = financial_app.create_interface()

        # Launching with debug enabled for better dev troubleshooting
        interface_demo.launch(debug=True)

    except Exception as fatal_error:
        LOGGER.critical(f"FATAL: Application crashed during startup: {fatal_error}")
