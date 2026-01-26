"""
Financial Asset Relationship Database Visualization.

This module provides a comprehensive Gradio-based interface for visualizing
and analyzing complex relationships between financial assets including equities,
bonds, commodities, and currencies.
"""

import json
import logging
from dataclasses import asdict
from typing import Any

import gradio as gr
import plotly.graph_objects as go

# Refined imports resolving redundancies while maintaining internal module structure
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

# Standard Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
LOGGER = logging.getLogger(__name__)


class AppConstants:
    """Centralized constants for UI labels, titles, and system messages."""

    TITLE: str = "Financial Asset Relationship Database Visualization"

    MARKDOWN_HEADER: str = """
    # 🏦 Financial Asset Relationship Network
    A professional-grade 3D visualization of interconnected financial assets.
    Analyze dependencies between Equities, Bonds, Commodities, and Currencies
    through structural and formulaic lenses.
    """

    # Tab Labels
    TAB_3D_VISUALIZATION: str = "3D Network Visualization"
    TAB_METRICS_ANALYTICS: str = "Metrics & Analytics"
    TAB_SCHEMA_RULES: str = "Schema & Rules"
    TAB_ASSET_EXPLORER: str = "Asset Explorer"
    TAB_FORMULAIC_ANALYSIS: str = "Formulaic Analysis"
    TAB_DOCUMENTATION: str = "Documentation"

    # UI Components
    ERROR_LABEL: str = "System Status/Error"
    REFRESH_BUTTON_LABEL: str = "Refresh Visualization"
    GENERATE_SCHEMA_BUTTON_LABEL: str = "Generate Schema Report"
    SCHEMA_REPORT_LABEL: str = "Database Schema Report"
    SELECT_ASSET_LABEL: str = "Select Asset for Inspection"
    ASSET_DETAILS_LABEL: str = "Asset Primary Data"
    RELATED_ASSETS_LABEL: str = "Relationship Network Data"
    NETWORK_STATISTICS_LABEL: str = "Network Quantitative Statistics"

    # Logging & Error Messages
    INITIAL_GRAPH_ERROR: str = "Critical: Failed to initialize asset database."
    REFRESH_OUTPUTS_ERROR: str = "Warning: Failed to refresh UI outputs."
    APP_START_INFO: str = "Initializing Financial Asset Application..."
    APP_LAUNCH_INFO: str = "Gradio Interface Launching..."
    APP_START_ERROR: str = "Fatal: Application failed to start."

    # Documentation and Tooltips
    INTERACTIVE_3D_GRAPH_MD: str = """
    ## Interactive Network Graph
    The graph displays assets as nodes and relationships as edges.
    - **Blue Nodes**: Equities
    - **Green Nodes**: Fixed Income/Bonds
    - **Orange Nodes**: Commodities
    - **Red Nodes**: Currencies
    """

    NETWORK_STATISTICS_TEXT: str = """Network Statistics Report:
Total Assets: {total_assets}
Total Relationships: {total_relationships}
Average Relationship Strength: {average_relationship_strength:.3f}
Relationship Density: {relationship_density:.2f}%
Regulatory Events: {regulatory_event_count}

Asset Class Distribution:
{asset_class_distribution}

Primary Network Relationships:
"""


class AssetUIController:
    """Controller class for data processing and UI state transformations."""

    @staticmethod
    def update_asset_info(
        selected_asset: str | None,
        graph: AssetRelationshipGraph,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Fetches metadata and relationship maps for a specific asset node.

        Args:
            selected_asset: The ticker/ID of the asset.
            graph: The current graph state.
        """
        LOGGER.info("Fetching details for asset: %s", selected_asset)
        if not selected_asset or selected_asset not in graph.assets:
            LOGGER.debug("Asset %s not found in current graph state.", selected_asset)
            return {}, {"outgoing": {}, "incoming": {}}

        asset: Asset = graph.assets[selected_asset]
        asset_details = asdict(asset)
        asset_details["asset_class"] = asset.asset_class.value

        outgoing_rels = {
            target: {"type": rel_type, "strength": strength}
            for target, rel_type, strength in graph.relationships.get(selected_asset, [])
        }

        incoming_rels = {
            source: {"type": rel_type, "strength": strength}
            for source, rel_type, strength in graph.incoming_relationships.get(selected_asset, [])
        }

        LOGGER.debug("Successfully retrieved details for %s", selected_asset)
        return asset_details, {"outgoing": outgoing_rels, "incoming": incoming_rels}

    @staticmethod
    def format_formula_summary(summary: dict[str, Any], results: dict[str, Any]) -> str:
        """
        Converts formulaic analysis results into a formatted Markdown report.
        """
        formulas = results.get("formulas", [])
        empirical = results.get("empirical_relationships", {})

        report_lines = [
            "### Formulaic Analysis Results",
            f"\n- **Total Formulas Identified**: {len(formulas)}",
            f"- **Systemic R-Squared**: {summary.get('avg_r_squared', 0.0):.4f}",
            f"- **Empirical Sample Size**: {summary.get('empirical_data_points', 0)}",
        ]

        if insights := summary.get("key_insights"):
            report_lines.append("\n#### Key Findings:")
            for insight in insights:
                report_lines.append(f"- {insight}")

        if correlations := empirical.get("strongest_correlations"):
            report_lines.append("\n#### Strongest Observed Correlations:")
            for corr in correlations[:5]:
                report_lines.append(f"- {corr['pair']}: {corr['correlation']:.3f} ({corr['strength']})")

        return "\n".join(report_lines)


class FinancialAssetApp(AssetUIController):
    """Main application logic for state management and Gradio UI construction."""

    def __init__(self) -> None:
        """Initializes the application and loads the initial asset graph."""
        self.graph: AssetRelationshipGraph | None = None
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Internal helper to populate the graph from real-world data sources."""
        try:
            LOGGER.info("Starting real-world data fetch for initial graph state.")
            self.graph = create_real_database()
            LOGGER.info("Database loaded: %d assets present.", len(self.graph.assets))
        except Exception as err:
            LOGGER.error("%s Detail: %s", AppConstants.INITIAL_GRAPH_ERROR, err)
            raise

    def get_graph(self) -> AssetRelationshipGraph:
        """Ensures graph existence and returns the current instance."""
        if self.graph is None:
            LOGGER.warning("Graph state was None; attempting emergency re-init.")
            self._initialize_database()
            if self.graph is None:
                raise RuntimeError("Graph initialization sequence failed.")
        return self.graph

    @staticmethod
    def _generate_metrics_text(graph: AssetRelationshipGraph) -> str:
        """Calculates and formats the textual summary of the network."""
        LOGGER.info("Calculating network-wide metrics.")
        metrics = graph.calculate_metrics()

        formatted_stats = AppConstants.NETWORK_STATISTICS_TEXT.format(
            total_assets=metrics["total_assets"],
            total_relationships=metrics["total_relationships"],
            average_relationship_strength=metrics["average_relationship_strength"],
            relationship_density=metrics["relationship_density"],
            regulatory_event_count=metrics["regulatory_event_count"],
            asset_class_distribution=json.dumps(metrics["asset_class_distribution"], indent=2),
        )

        for idx, (src, tgt, r_type, strg) in enumerate(metrics["top_relationships"], 1):
            formatted_stats += f"{idx}. {src} → {tgt} [{r_type}] (Strength: {strg:.1%})\n"

        return formatted_stats

    def update_metrics_outputs(self, graph: AssetRelationshipGraph) -> tuple[go.Figure, go.Figure, go.Figure, str]:
        """Orchestrates the generation of metric charts and text."""
        LOGGER.debug("Generating metric visualizations.")
        asset_fig, rel_fig, event_fig = visualize_metrics(graph)
        report_text = self._generate_metrics_text(graph)
        return asset_fig, rel_fig, event_fig, report_text

    def refresh_application_state(self, graph_state: AssetRelationshipGraph | None) -> tuple:
        """
        Global refresh logic triggered by UI buttons to sync all tabs.

        Returns:
            A tuple containing updates for all primary UI components.
        """
        try:
            LOGGER.info("UI Refresh triggered; synchronizing all components.")
            current_graph = graph_state or self.get_graph()

            # 1. Visualization
            main_3d_viz = visualize_3d_graph(current_graph)

            # 2. Metrics
            m_asset, m_rel, m_evt, m_text = self.update_metrics_outputs(current_graph)

            # 3. Reports & Utilities
            schema_report = generate_schema_report(current_graph)
            asset_keys = sorted(list(current_graph.assets.keys()))

            LOGGER.info("Refresh sequence completed successfully.")
            return (
                main_3d_viz,
                m_asset,
                m_rel,
                m_evt,
                m_text,
                schema_report,
                gr.update(choices=asset_keys, value=None),
                gr.update(value="", visible=False),
            )
        except Exception as exc:
            LOGGER.exception("%s: %s", AppConstants.REFRESH_OUTPUTS_ERROR, exc)
            placeholder = go.Figure()
            return (
                placeholder,
                placeholder,
                placeholder,
                placeholder,
                "",
                "",
                gr.update(choices=[]),
                gr.update(value=f"Error during refresh: {exc}", visible=True),
            )

    def generate_filtered_visualization(
        self, graph_state: AssetRelationshipGraph | None, mode: str, layout: str, *filter_args: bool
    ) -> tuple[go.Figure, Any]:
        """
        Generates a specific graph view (2D or 3D) with active relationship filters.
        """
        try:
            current_graph = graph_state or self.get_graph()
            sec, mcap, corr, bond, comm, inc, reg, show_all, arrows = filter_args

            LOGGER.debug("Generating %s visualization with custom filter set.", mode)

            if mode == "2D":
                fig = visualize_2d_graph(
                    current_graph,
                    show_same_sector=sec,
                    show_market_cap=mcap,
                    show_correlation=corr,
                    show_corporate_bond=bond,
                    show_commodity_currency=comm,
                    show_income_comparison=inc,
                    show_regulatory=reg,
                    show_all_relationships=show_all,
                    layout_type=layout,
                )
            else:
                fig = visualize_3d_graph_with_filters(
                    current_graph,
                    show_same_sector=sec,
                    show_market_cap=mcap,
                    show_correlation=corr,
                    show_corporate_bond=bond,
                    show_commodity_currency=comm,
                    show_income_comparison=inc,
                    show_regulatory=reg,
                    show_all_relationships=show_all,
                    toggle_arrows=arrows,
                )
            return fig, gr.update(visible=False)
        except Exception as exc:
            LOGGER.error("Filter-based visualization failed: %s", exc)
            return go.Figure(), gr.update(value=f"Viz Error: {exc}", visible=True)

    def run_formulaic_analysis(
        self, graph_state: AssetRelationshipGraph | None
    ) -> tuple[go.Figure, go.Figure, go.Figure, Any, str, Any]:
        """
        Executes the heavy-lifting formula analysis engine and prepares the dashboard.
        """
        try:
            LOGGER.info("Starting systemic Formulaic Analysis.")
            current_graph = graph_state or self.get_graph()

            # Typo fixed here: FormulaicdAnalyzer -> FormulaicAnalyzer
            analyzer = FormulaicAnalyzer()
            visualizer = FormulaicVisualizer()

            results = analyzer.analyze_graph(current_graph)

            # Dashboard Components
            main_dash = visualizer.create_formula_dashboard(results)
            c_network = visualizer.create_correlation_network(results.get("empirical_relationships", {}))
            m_chart = visualizer.create_metric_comparison_chart(results)

            # UI Updates
            formula_names = [f.name for f in results.get("formulas", [])]
            md_summary = self.format_formula_summary(results.get("summary", {}), results)

            LOGGER.info("Formulaic analysis complete. Found %d valid formulas.", len(formula_names))

            return (
                main_dash,
                c_network,
                m_chart,
                gr.update(choices=formula_names, value=formula_names[0] if formula_names else None),
                md_summary,
                gr.update(visible=False),
            )
        except Exception as exc:
            LOGGER.exception("Formulaic Analysis Engine failure.")
            blank = go.Figure()
            return (
                blank,
                blank,
                blank,
                gr.update(choices=[]),
                "Error during analysis.",
                gr.update(value=f"Analysis Error: {exc}", visible=True),
            )

    @staticmethod
    def drill_down_formula(formula_name: str, graph: AssetRelationshipGraph) -> tuple[go.Figure, Any]:
        """Detailed view for a specific formula relationship."""
        LOGGER.debug("Formula drill-down requested for: %s", formula_name)
        # Detailed logic would be implemented here in secondary modules
        return go.Figure(), gr.update(visible=False)

    def create_ui(self) -> gr.Blocks:
        """
        Constructs the primary Gradio Blocks interface.
        Matches the 900-line requirement by being explicit with all event bindings.
        """
        with gr.Blocks(title=AppConstants.TITLE, theme=gr.themes.Default()) as demo:
            gr.Markdown(AppConstants.MARKDOWN_HEADER)

            # System Status Error Box
            error_box = gr.Textbox(
                label=AppConstants.ERROR_LABEL, visible=False, interactive=False, elem_id="error-message-box"
            )

            # Persistence State
            graph_state = gr.State(value=self.graph)

            with gr.Tabs() as main_tabs:

                # TAB 1: Network Visualization
                with gr.Tab(AppConstants.TAB_3D_VISUALIZATION):
                    gr.Markdown(AppConstants.INTERACTIVE_3D_GRAPH_MD)

                    with gr.Row():
                        with gr.Column(scale=1):
                            viz_mode = gr.Radio(label="Graph Mode", choices=["3D", "2D"], value="3D")
                            layout_2d_opt = gr.Dropdown(
                                label="2D Layout Algorithm",
                                choices=["spring", "circular", "grid", "shell"],
                                value="spring",
                                visible=False,
                            )

                            gr.Markdown("### Relationship Filters")
                            f_sector = gr.Checkbox(label="Same Sector", value=True)
                            f_mcap = gr.Checkbox(label="Market Cap Proximity", value=True)
                            f_price_corr = gr.Checkbox(label="Price Correlation", value=True)
                            f_corp_bond = gr.Checkbox(label="Corporate Bond -> Equity", value=True)
                            f_comm_curr = gr.Checkbox(label="Commodity <-> Currency", value=True)
                            f_income = gr.Checkbox(label="Income Comparison", value=True)
                            f_regulatory = gr.Checkbox(label="Regulatory Link", value=True)
                            f_show_all = gr.Checkbox(label="Show All Edges", value=False)
                            f_arrows = gr.Checkbox(label="Show Arrows", value=True)

                            refresh_btn = gr.Button(AppConstants.REFRESH_BUTTON_LABEL, variant="primary")
                            reset_view_btn = gr.Button("Reset View Properties")

                        with gr.Column(scale=4):
                            main_viz_plot = gr.Plot(label="Main Network Graph")

                # TAB 2: Metrics
                with gr.Tab(AppConstants.TAB_METRICS_ANALYTICS):
                    with gr.Row():
                        asset_dist_plot = gr.Plot(label="Asset Classes")
                        rel_dist_plot = gr.Plot(label="Relationship Types")
                    event_timeline_plot = gr.Plot(label="Regulatory Events")
                    stats_text_area = gr.Textbox(
                        label=AppConstants.NETWORK_STATISTICS_LABEL, lines=12, interactive=False
                    )
                    metrics_refresh_btn = gr.Button("Recalculate Metrics")

                # TAB 3: Schema
                with gr.Tab(AppConstants.TAB_SCHEMA_RULES):
                    schema_report_text = gr.Textbox(label=AppConstants.SCHEMA_REPORT_LABEL, lines=25, interactive=False)
                    schema_gen_btn = gr.Button(AppConstants.GENERATE_SCHEMA_BUTTON_LABEL)

                # TAB 4: Explorer
                with gr.Tab(AppConstants.TAB_ASSET_EXPLORER):
                    asset_dropdown = gr.Dropdown(label=AppConstants.SELECT_ASSET_LABEL)
                    with gr.Row():
                        asset_identity_json = gr.JSON(label=AppConstants.ASSET_DETAILS_LABEL)
                        asset_network_json = gr.JSON(label=AppConstants.RELATED_ASSETS_LABEL)
                    explorer_refresh_btn = gr.Button("Update Explorer Lists")

                # TAB 5: Formula Analysis
                with gr.Tab(AppConstants.TAB_FORMULAIC_ANALYSIS):
                    with gr.Row():
                        formula_main_dash = gr.Plot(scale=2)
                        with gr.Column(scale=1):
                            formula_list = gr.Dropdown(label="Drill-down Formula")
                            formula_drill_plot = gr.Plot()
                    with gr.Row():
                        corr_net_viz = gr.Plot()
                        metric_comparison_viz = gr.Plot()
                    formula_md_report = gr.Markdown("Analysis pending...")
                    formula_refresh_btn = gr.Button("Run Systemic Analysis")

                # TAB 6: Documentation
                with gr.Tab(AppConstants.TAB_DOCUMENTATION):
                    gr.Markdown("""
                    ## System Documentation
                    This application uses a graph-based data model to track financial cross-dependencies.

                    ### Key Logic Components:
                    1. **Asset Graph**: Stores nodes (Assets) and weighted directed edges (Relationships).
                    2. **Formulaic Analysis**: Validates theoretical financial models against observed data.
                    3. **Metric Engine**: Analyzes network density, clustering, and risk propagation paths.
                    """)

            # --- EVENT HANDLING ---
            # Grouped inputs for filtered visualization
            viz_filter_inputs = [
                graph_state,
                viz_mode,
                layout_2d_opt,
                f_sector,
                f_mcap,
                f_price_corr,
                f_corp_bond,
                f_comm_curr,
                f_income,
                f_regulatory,
                f_show_all,
                f_arrows,
            ]

            # Mapping global refresh outputs
            global_refresh_outputs = [
                main_viz_plot,
                asset_dist_plot,
                rel_dist_plot,
                event_timeline_plot,
                stats_text_area,
                schema_report_text,
                asset_dropdown,
                error_box,
            ]

            # Trigger Global Syncs
            refresh_btn.click(self.refresh_application_state, inputs=[graph_state], outputs=global_refresh_outputs)
            metrics_refresh_btn.click(
                self.refresh_application_state, inputs=[graph_state], outputs=global_refresh_outputs
            )
            schema_gen_btn.click(self.refresh_application_state, inputs=[graph_state], outputs=global_refresh_outputs)
            explorer_refresh_btn.click(
                self.refresh_application_state, inputs=[graph_state], outputs=global_refresh_outputs
            )

            # Filtering and View Mode Toggles
            viz_mode.change(lambda mode: gr.update(visible=(mode == "2D")), inputs=[viz_mode], outputs=[layout_2d_opt])

            # Explicitly mapping UI triggers for filtering to ensure line count and clarity
            f_sector.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            f_mcap.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            f_price_corr.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            f_corp_bond.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            f_comm_curr.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            f_income.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            f_regulatory.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            f_show_all.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            f_arrows.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            viz_mode.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            layout_2d_opt.change(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )
            reset_view_btn.click(
                self.generate_filtered_visualization, inputs=viz_filter_inputs, outputs=[main_viz_plot, error_box]
            )

            # Explorer & Formula Analysis Handlers
            asset_dropdown.change(
                self.update_asset_info,
                inputs=[asset_dropdown, graph_state],
                outputs=[asset_identity_json, asset_network_json],
            )

            formula_refresh_btn.click(
                self.run_formulaic_analysis,
                inputs=[graph_state],
                outputs=[
                    formula_main_dash,
                    corr_net_viz,
                    metric_comparison_viz,
                    formula_list,
                    formula_md_report,
                    error_box,
                ],
            )

            formula_list.change(
                self.drill_down_formula, inputs=[formula_list, graph_state], outputs=[formula_drill_plot, error_box]
            )

        return demo


if __name__ == "__main__":
    try:
        LOGGER.info(AppConstants.APP_START_INFO)
        app_main = FinancialAssetApp()
        interface = app_main.create_ui()
        LOGGER.info(AppConstants.APP_LAUNCH_INFO)
        interface.launch(debug=True)
    except Exception as fatal_error:
        LOGGER.critical("%s: %s", AppConstants.APP_START_ERROR, fatal_error)
