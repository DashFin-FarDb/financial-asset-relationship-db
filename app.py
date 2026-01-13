import json
import logging
from dataclasses import asdict
from typing import Dict, Optional, Tuple

import gradio as gr
import plotly.graph_objects as go

from src.analysis.formulaic_analysis import FormulaicdAnalyzer
from src.data.real_data_fetcher import create_real_database
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Asset
from src.reports.schema_report import generate_schema_report
from src.visualizations.formulaic_visuals import FormulaicVisualizer
from src.visualizations.graph_2d_visuals import visualize_2d_graph
from src.visualizations.graph_visuals import visualize_3d_graph, visualize_3d_graph_with_filters
from src.visualizations.metric_visuals import visualize_metrics

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ------------- Constants -------------
class AppConstants:
    TITLE = "Financial Asset Relationship Database Visualization"
    MARKDOWN_HEADER = """
    # 🏦 Financial Asset Relationship Network

    A comprehensive 3D visualization of interconnected financial assets across all major classes:
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
    SELECT_ASSET_LABEL = "Select Asset"
    ASSET_DETAILS_LABEL = "Asset Details"
    RELATED_ASSETS_LABEL = "Related Assets"
    NETWORK_STATISTICS_LABEL = "Network Statistics"
    SCHEMA_REPORT_LABEL = "Schema Report"
    INITIAL_GRAPH_ERROR = "Failed to create sample database"
    REFRESH_OUTPUTS_ERROR = "Error refreshing outputs"
    APP_START_INFO = "Starting Financial Asset Relationship Database application"
    APP_LAUNCH_INFO = "Launching Gradio interface"
    APP_START_ERROR = "Failed to start application"

    # Missing markdown constants
    INTERACTIVE_3D_GRAPH_MD = """
    ## Interactive 3D Network Graph

    Explore the relationships between financial assets in three dimensions. Each node represents an asset,
    and edges show the strength and type of relationships between them.

    **Asset Colors:**
    - 🔵 Blue: Equities (Stocks)
    - 🟢 Green: Fixed Income (Bonds)
    - 🟠 Orange: Commodities
    - 🔴 Red: Currencies
    - 🟣 Purple: Derivatives
    """

    NETWORK_METRICS_ANALYSIS_MD = """
    ## Network Metrics & Analytics

    Comprehensive analysis of asset relationships, distributions, and regulatory event impacts.
    """

    SCHEMA_RULES_GUIDE_MD = """
    ## Database Schema & Business Rules

    View the automatically generated schema documentation including relationship types, business rules, and validation constraints.
    """

    DETAILED_ASSET_INFO_MD = """
    ## Asset Explorer

    Select any asset to view detailed information including financial metrics, relationships, and connected assets.
    """

    DOC_MARKDOWN = """
    ## Documentation & Help

    ### Quick Start
    1. **3D Visualization**: Explore the interactive network graph
    2. **Metrics**: View quantitative analysis of relationships
    3. **Schema**: Understand the data model and business rules
    4. **Explorer**: Drill down into individual asset details

    ### Features
    - **Cross-Asset Analysis**: Automatic relationship discovery
    - **Regulatory Integration**: Corporate events impact modeling
    - **Real-time Metrics**: Network statistics and strength analysis
    - **Deterministic Layout**: Consistent 3D positioning across sessions

    ### Asset Classes
    - Equities, Bonds, Commodities, Currencies, Derivatives
    - Relationship types: sector affinity, corporate links, currency exposure, regulatory events

    For technical details, see the GitHub repository documentation.
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
    def __init__(self):
        self.graph: Optional[AssetRelationshipGraph] = None
        self._initialize_graph()

    def _initialize_graph(self) -> None:
        """Initializes the asset graph, creating a sample database if necessary."""
        try:
            logger.info("Initializing with real financial data from Yahoo Finance")
            self.graph = create_real_database()
            logger.info("Database initialized with %s real assets", len(self.graph.assets))
            logger.info("Initialized sample database with %s assets", len(self.graph.assets))
        except Exception as e:
            logger.error("%s: %s", AppConstants.INITIAL_GRAPH_ERROR, e)
            # Depending on desired behavior, could set self.graph to an empty graph
            # or re-raise the exception to prevent the app from starting.
            raise

    def ensure_graph(self) -> AssetRelationshipGraph:
        """Ensures the graph is initialized, re-creating sample data if it's None."""
        if self.graph is None:
            logger.warning("Graph is None, re-creating sample database.")
            self._initialize_graph()
        return self.graph

    @staticmethod
    def _update_metrics_text(graph: AssetRelationshipGraph) -> str:
        """Generates the formatted text for network statistics."""
        metrics = graph.calculate_metrics()
        text = AppConstants.NETWORK_STATISTICS_TEXT.format(
            total_assets=metrics["total_assets"],
            total_relationships=metrics["total_relationships"],
            average_relationship_strength=metrics["average_relationship_strength"],
            relationship_density=metrics["relationship_density"],
            regulatory_event_count=metrics["regulatory_event_count"],
            asset_class_distribution=json.dumps(metrics["asset_class_distribution"], indent=2),
        )
        for idx, (s, t, rel, strength) in enumerate(metrics["top_relationships"], 1):
            text += f"{idx}. {s} → {t} ({rel}): {strength:.1%}\n"
        return text

    def update_all_metrics_outputs(self, graph: AssetRelationshipGraph):
        """Updates all metric-related visualizations and text."""
        f1, f2, f3 = visualize_metrics(graph)
        text = self._update_metrics_text(graph)
        return f1, f2, f3, text

    @staticmethod
    def update_asset_info(selected_asset: Optional[str], graph: AssetRelationshipGraph) -> Tuple[Dict, Dict]:
        """Retrieves and formats detailed information for a selected asset."""
        if not selected_asset or selected_asset not in graph.assets:
            return {}, {"outgoing": {}, "incoming": {}}

        asset: Asset = graph.assets[selected_asset]
        asset_dict = asdict(asset)
        asset_dict["asset_class"] = asset.asset_class.value

        outgoing = {
            target_id: {"relationship_type": rel_type, "strength": strength}
            for target_id, rel_type, strength in graph.relationships.get(selected_asset, [])
        }
        incoming = {
            src_id: {"relationship_type": rel_type, "strength": strength}
            for src_id, rel_type, strength in graph.incoming_relationships.get(selected_asset, [])
        }
        return asset_dict, {"outgoing": outgoing, "incoming": incoming}

    def refresh_all_outputs(self, graph_state: AssetRelationshipGraph):
        """Refreshes all visualizations and reports in the Gradio interface."""
        try:
            graph = self.ensure_graph()  # Use self.ensure_graph to get the latest graph state
            logger.info("Refreshing all visualization outputs")
            viz_3d = visualize_3d_graph(graph)
            f1, f2, f3, metrics_txt = self.update_all_metrics_outputs(graph)
            schema_rpt = generate_schema_report(graph)
            asset_choices = list(graph.assets.keys())
            logger.info("Successfully refreshed outputs for %s assets", len(asset_choices))
            return (
                viz_3d,
                f1,
                f2,
                f3,
                metrics_txt,
                schema_rpt,
                gr.update(choices=asset_choices, value=None),
                gr.update(value="", visible=False),
            )
        except Exception as e:
            logger.error("%s: %s", AppConstants.REFRESH_OUTPUTS_ERROR, e)
            return (
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(choices=[], value=None),
                gr.update(value=f"Error: {str(e)}", visible=True),
            )

    def refresh_visualization(
        self,
        graph_state,
        view_mode,
        layout_type,
        show_same_sector,
        show_market_cap,
        show_correlation,
        show_corporate_bond,
        show_commodity_currency,
        show_income_comparison,
        show_regulatory,
        show_all_relationships,
        toggle_arrows,
    ):
        """Refresh visualization with 2D/3D mode support and relationship filtering."""
        try:
            graph = self.ensure_graph()

            if view_mode == "2D":
                graph_viz = visualize_2d_graph(
                    graph,
                    show_same_sector=show_same_sector,
                    show_market_cap=show_market_cap,
                    show_correlation=show_correlation,
                    show_corporate_bond=show_corporate_bond,
                    show_commodity_currency=show_commodity_currency,
                    show_income_comparison=show_income_comparison,
                    show_regulatory=show_regulatory,
                    show_all_relationships=show_all_relationships,
                    layout_type=layout_type,
                )
            else:  # 3D mode
                graph_viz = visualize_3d_graph_with_filters(
                    graph,
                    show_same_sector=show_same_sector,
                    show_market_cap=show_market_cap,
                    show_correlation=show_correlation,
                    show_corporate_bond=show_corporate_bond,
                    show_commodity_currency=show_commodity_currency,
                    show_income_comparison=show_income_comparison,
                    show_regulatory=show_regulatory,
                    show_all_relationships=show_all_relationships,
                    toggle_arrows=toggle_arrows,
                )

            return graph_viz, gr.update(visible=False)

        except Exception as e:
            logger.error("Error refreshing visualization: %s", e)
            empty_fig = go.Figure()
            error_msg = f"Error refreshing visualization: {str(e)}"
            return empty_fig, gr.update(value=error_msg, visible=True)

    def generate_formulaic_analysis(self, graph_state: AssetRelationshipGraph):
        """Generate comprehensive formulaic analysis of the asset graph."""
        try:
            logger.info("Generating formulaic analysis")
            graph = self.ensure_graph() if graph_state is None else graph_state

            # Initialize analyzers
            formulaic_analyzer = FormulaicdAnalyzer()
            formulaic_visualizer = FormulaicVisualizer()

            # Perform analysis
            analysis_results = formulaic_analyzer.analyze_graph(graph)

            # Generate visualizations
            dashboard_fig = formulaic_visualizer.create_formula_dashboard(analysis_results)
            correlation_network_fig = formulaic_visualizer.create_correlation_network(
                analysis_results.get("empirical_relationships", {})
            )
            metric_comparison_fig = formulaic_visualizer.create_metric_comparison_chart(analysis_results)

            # Generate formula selector options
            formulas = analysis_results.get("formulas", [])
            formula_choices = [f.name for f in formulas]

            # Generate summary
            summary = analysis_results.get("summary", {})
            summary_text = self._format_formula_summary(summary, analysis_results)

            logger.info("Generated formulaic analysis with %d formulas", len(formulas))
            return (
                dashboard_fig,
                correlation_network_fig,
                metric_comparison_fig,
                gr.update(choices=formula_choices, value=formula_choices[0] if formula_choices else None),
                summary_text,
                gr.update(visible=False),  # Hide error message
            )

        except Exception as e:
            logger.error("Error generating formulaic analysis: %s", e)
            empty_fig = go.Figure()
            error_msg = f"Error generating formulaic analysis: {str(e)}"
            return (
                empty_fig,
                empty_fig,
                empty_fig,
                gr.update(choices=[], value=None),
                error_msg,
                gr.update(value=error_msg, visible=True),
            )

    def show_formula_details(self, formula_name: str, graph_state: AssetRelationshipGraph):
        """Show detailed view of a specific formula."""
        except Exception as e:
            logger.error("Error showing formula details: %s", e)
            return go.Figure(), gr.update(value=f"Error: {str(e)}", visible=True)

    @staticmethod
    def _format_formula_summary(summary: Dict, analysis_results: Dict) -> str:
        """Format the formula analysis summary for display."""
        formulas = analysis_results.get("formulas", [])
        empirical = analysis_results.get("empirical_relationships", {})

        summary_lines = [
            "🔍 **Formulaic Analysis Summary**",
            "",
            f"📊 **Total Formulas Identified:** {len(formulas)}",
            f"📈 **Average Reliability (R²):** {summary.get('avg_r_squared', 0):.3f}",
            f"🔗 **Empirical Data Points:** {summary.get('empirical_data_points', 0)}",
            "",
            "📋 **Formula Categories:**",
        ]

        categories = summary.get("formula_categories", {})
        for category, count in categories.items():
            summary_lines.append(f"  • {category}: {count} formulas")

        summary_lines.extend(["", "🎯 **Key Insights:**"])

        insights = summary.get("key_insights", [])
        for insight in insights:
            summary_lines.append(f"  • {insight}")

        # Add correlation insights
        correlations = empirical.get("strongest_correlations", [])
        if correlations:
            summary_lines.extend(["", "🔗 **Strongest Asset Correlations:**"])
            for corr in correlations[:3]:
                summary_lines.append(f"  • {corr['pair']}: {corr['correlation']:.3f} ({corr['strength']})")

        return "\n".join(summary_lines)

    def create_interface(self):
        """Creates the Gradio interface for the Financial Asset Relationship Database."""
        with gr.Blocks(title=AppConstants.TITLE) as demo:
            gr.Markdown(AppConstants.MARKDOWN_HEADER)

            error_message = gr.Textbox(
                label=AppConstants.ERROR_LABEL, visible=False, interactive=False, elem_id="error_message"
            )

            with gr.Tabs():
                with gr.Tab("🌐 Network Visualization (2D/3D)"):
                    gr.Markdown(AppConstants.INTERACTIVE_3D_GRAPH_MD)

                    # Visualization mode and layout controls
                    with gr.Row():
                        gr.Markdown("### 🎛️ Visualization Controls")
                    with gr.Row():
                        with gr.Column(scale=1):
                            view_mode = gr.Radio(label="Visualization Mode", choices=["3D", "2D"], value="3D")
                        with gr.Column(scale=1):
                            layout_type = gr.Radio(
                                label="2D Layout Type",
                                choices=["spring", "circular", "grid"],
                                value="spring",
                                visible=False,
                            )

                    # Relationship visibility controls
                    with gr.Row():
                        gr.Markdown("### 🔗 Relationship Visibility Controls")
                    with gr.Row():
                        with gr.Column(scale=1):
                            show_same_sector = gr.Checkbox(label="Same Sector (↔)", value=True)
                            show_market_cap = gr.Checkbox(label="Market Cap Similar (↔)", value=True)
                            show_correlation = gr.Checkbox(label="Correlation (↔)", value=True)
                        with gr.Column(scale=1):
                            show_corporate_bond = gr.Checkbox(label="Corporate Bond → Equity (→)", value=True)
                            show_commodity_currency = gr.Checkbox(label="Commodity ↔ Currency", value=True)
                            show_income_comparison = gr.Checkbox(label="Income Comparison (↔)", value=True)
                        with gr.Column(scale=1):
                            show_regulatory = gr.Checkbox(label="Regulatory Impact (→)", value=True)
                            show_all_relationships = gr.Checkbox(label="Show All Relationships", value=True)
                            toggle_arrows = gr.Checkbox(label="Show Direction Arrows", value=True)

                    with gr.Row():
                        visualization_3d = gr.Plot()
                    with gr.Row():
                        with gr.Column(scale=1):
                            refresh_btn = gr.Button(AppConstants.REFRESH_BUTTON_LABEL, variant="primary")
                        with gr.Column(scale=1):
                            reset_view_btn = gr.Button("Reset View & Show All", variant="secondary")
                        with gr.Column(scale=2):
                            gr.Markdown("**Legend:** ↔ = Bidirectional, → = Unidirectional")

                with gr.Tab(AppConstants.TAB_METRICS_ANALYTICS):
                    gr.Markdown(AppConstants.NETWORK_METRICS_ANALYSIS_MD)
                    with gr.Row():
                        asset_dist_chart = gr.Plot()
                        rel_types_chart = gr.Plot()
                    with gr.Row():
                        events_timeline_chart = gr.Plot()
                    with gr.Row():
                        metrics_text = gr.Textbox(
                            label=AppConstants.NETWORK_STATISTICS_LABEL, lines=10, interactive=False
                        )
                    with gr.Row():
                        refresh_metrics_btn = gr.Button(AppConstants.REFRESH_BUTTON_LABEL, variant="primary")

                with gr.Tab(AppConstants.TAB_SCHEMA_RULES):
                    gr.Markdown(AppConstants.SCHEMA_RULES_GUIDE_MD)
                    with gr.Row():
                        schema_report = gr.Textbox(
                            label=AppConstants.SCHEMA_REPORT_LABEL,
                            lines=25,
                            interactive=False,
                        )
                    with gr.Row():
                        refresh_schema_btn = gr.Button(AppConstants.GENERATE_SCHEMA_BUTTON_LABEL, variant="primary")

                with gr.Tab(AppConstants.TAB_ASSET_EXPLORER):
                    gr.Markdown(AppConstants.DETAILED_ASSET_INFO_MD)
                    with gr.Row():
                        with gr.Column(scale=1):
                            asset_selector = gr.Dropdown(
                                label=AppConstants.SELECT_ASSET_LABEL, choices=[], interactive=True
                            )
                        with gr.Column(scale=3):
                            gr.Markdown("")

                    with gr.Row():
                        asset_info = gr.JSON(label=AppConstants.ASSET_DETAILS_LABEL)

                    with gr.Row():
                        asset_relationships = gr.JSON(label=AppConstants.RELATED_ASSETS_LABEL)

                    with gr.Row():
                        refresh_explorer_btn = gr.Button(AppConstants.REFRESH_BUTTON_LABEL, variant="primary")

                with gr.Tab(AppConstants.TAB_DOCUMENTATION):
                    gr.Markdown(AppConstants.DOC_MARKDOWN)

                with gr.Tab("📊 Formulaic Analysis"):
                    gr.Markdown(
                        """
                    ## Mathematical Relationships & Formulas

                    This section extracts and visualizes mathematical formulas and relationships between financial variables.
                    It includes fundamental financial ratios, correlation patterns, valuation models, and empirical relationships
                    derived from the asset database.
                    """
                    )

                    with gr.Row():
                        with gr.Column(scale=2):
                            formulaic_dashboard = gr.Plot(label="Formulaic Analysis Dashboard")
                        with gr.Column(scale=1):
                            formula_selector = gr.Dropdown(
                                label="Select Formula for Details", choices=[], value=None, interactive=True
                            )
                            formula_detail_view = gr.Plot(label="Formula Details")

                    with gr.Row():
                        with gr.Column(scale=1):
                            correlation_network = gr.Plot(label="Asset Correlation Network")
                        with gr.Column(scale=1):
                            metric_comparison = gr.Plot(label="Metric Comparison Chart")

                    with gr.Row():
                        with gr.Column(scale=1):
                            refresh_formulas_btn = gr.Button("🔄 Refresh Formulaic Analysis", variant="primary")
                        with gr.Column(scale=2):
                            formula_summary = gr.Textbox(label="Formula Analysis Summary", lines=5, interactive=False)

            graph_state = gr.State(value=self.graph)

            # Event handlers
            all_refresh_outputs = [
                visualization_3d,
                asset_dist_chart,
                rel_types_chart,
                events_timeline_chart,
                metrics_text,
                schema_report,
                asset_selector,
                error_message,
            ]

            # Group all refresh buttons and assign the same handler
            refresh_buttons = [refresh_metrics_btn, refresh_schema_btn, refresh_explorer_btn]
            for btn in refresh_buttons:
                btn.click(self.refresh_all_outputs, inputs=[graph_state], outputs=all_refresh_outputs)

            # Visualization mode event handlers
            visualization_inputs = [
                graph_state,
                view_mode,
                layout_type,
                show_same_sector,
                show_market_cap,
                show_correlation,
                show_corporate_bond,
                show_commodity_currency,
                show_income_comparison,
                show_regulatory,
                show_all_relationships,
                toggle_arrows,
            ]
            visualization_outputs = [visualization_3d, error_message]

            # Main refresh button for visualization
            refresh_btn.click(self.refresh_visualization, inputs=visualization_inputs, outputs=visualization_outputs)

            # View mode change handler
            view_mode.change(
                lambda *args: (
                    gr.update(visible=args[1] == "2D"),
                    *self.refresh_visualization(*args)[0:1],
                    gr.update(visible=False),
                ),
                inputs=visualization_inputs,
                outputs=[layout_type, visualization_3d, error_message],
            )

            # Formulaic analysis event handlers
            formulaic_outputs = [
                formulaic_dashboard,
                correlation_network,
                metric_comparison,
                formula_selector,
                formula_summary,
                error_message,
            ]

            refresh_formulas_btn.click(
                self.generate_formulaic_analysis, inputs=[graph_state], outputs=formulaic_outputs
            )

            formula_selector.change(
                self.show_formula_details,
                inputs=[formula_selector, graph_state],
                outputs=[formula_detail_view, error_message],
            )

            # Add event handlers for relationship filtering (moved to main visualization handlers above)
            # Legacy handlers removed - now using unified refresh_visualization function

            # Wire up each checkbox to refresh the visualization
            for checkbox in [
                show_same_sector,
                show_market_cap,
                show_correlation,
                show_corporate_bond,
                show_commodity_currency,
                show_income_comparison,
                show_regulatory,
                show_all_relationships,
                toggle_arrows,
            ]:
                checkbox.change(self.refresh_visualization, inputs=visualization_inputs, outputs=visualization_outputs)

            # Layout type change handler for 2D mode
            layout_type.change(self.refresh_visualization, inputs=visualization_inputs, outputs=visualization_outputs)

            # Reset view button to show all relationships
            reset_view_btn.click(
                lambda graph_state, view_mode, layout_type: self.refresh_visualization(
                    graph_state, view_mode, layout_type, True, True, True, True, True, True, True, True, True
                ),
                inputs=[graph_state, view_mode, layout_type],
                outputs=visualization_outputs,
            )

            asset_selector.change(
                self.update_asset_info, inputs=[asset_selector, graph_state], outputs=[asset_info, asset_relationships]
            )

            demo.load(self.refresh_all_outputs, inputs=[graph_state], outputs=all_refresh_outputs)
        return demo


if __name__ == "__main__":
    try:
        logger.info(AppConstants.APP_START_INFO)
        app = FinancialAssetApp()
        demo = app.create_interface()
        logger.info(AppConstants.APP_LAUNCH_INFO)
        demo.launch()
    except Exception as e:
        logger.error("%s: %s", AppConstants.APP_START_ERROR, e)
        raise
