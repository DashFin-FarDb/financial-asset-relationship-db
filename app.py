from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple, TypedDict, cast

import gradio as gr
import plotly.graph_objects as go

from src.analysis.formulaic_analysis import FormulaicdAnalyzer
from src.data.real_data_fetcher import create_real_database
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Asset
from src.reports.schema_report import generate_schema_report
from src.visualizations.formulaic_visuals import FormulaicVisualizer
from src.visualizations.graph_2d_visuals import visualize_2d_graph
from src.visualizations.graph_visuals import (
    visualize_3d_graph,
    visualize_3d_graph_with_filters,
)
from src.visualizations.metric_visuals import visualize_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
LOGGER: logging.Logger = logging.getLogger(__name__)


class GraphMetrics(TypedDict):
    total_assets: int
    total_relationships: int
    average_relationship_strength: float
    relationship_density: float
    regulatory_event_count: int
    asset_class_distribution: Dict[str, int]
    top_relationships: List[Tuple[str, str, str, float]]


class AssetRelationshipPayload(TypedDict):
    outgoing: Dict[str, Dict[str, Any]]
    incoming: Dict[str, Dict[str, Any]]


GradioUpdate = Any


class AppConstants:
    TITLE: str = "Financial Asset Relationship Database Visualization"
    MARKDOWN_HEADER: str = """
    # 🏦 Financial Asset Relationship Network

    A comprehensive 3D visualization of interconnected financial
    assets across all major classes:
    **Equities, Bonds, Commodities, Currencies, and Regulatory
    Events**
    """

    TAB_3D_VISUALIZATION: str = "3D Network Visualization"
    TAB_METRICS_ANALYTICS: str = "Metrics & Analytics"
    TAB_SCHEMA_RULES: str = "Schema & Rules"
    TAB_ASSET_EXPLORER: str = "Asset Explorer"
    TAB_DOCUMENTATION: str = "Documentation"

    ERROR_LABEL: str = "Error"
    REFRESH_BUTTON_LABEL: str = "Refresh Visualization"
    GENERATE_SCHEMA_BUTTON_LABEL: str = "Generate Schema Report"
    SELECT_ASSET_LABEL: str = "Select Asset"
    ASSET_DETAILS_LABEL: str = "Asset Details"
    RELATED_ASSETS_LABEL: str = "Related Assets"
    NETWORK_STATISTICS_LABEL: str = "Network Statistics"
    SCHEMA_REPORT_LABEL: str = "Schema Report"

    INITIAL_GRAPH_ERROR: str = "Failed to create sample database"
    REFRESH_OUTPUTS_ERROR: str = "Error refreshing outputs"

    APP_START_INFO: str = "Starting Financial Asset Relationship Database application"
    APP_LAUNCH_INFO: str = "Launching Gradio interface"
    APP_START_ERROR: str = "Failed to start application"

    NETWORK_STATISTICS_TEXT: str = """Network Statistics:

Total Assets: {total_assets}
Total Relationships: {total_relationships}
Average Relationship Strength: {average_relationship_strength:.3f}
Relationship Density: {relationship_density:.2f}%
Regulatory Events: {regulatory_event_count}

Asset Class Distribution:
{asset_class_distribution}

Top Relationships:
"""
    INTERACTIVE_3D_GRAPH_MD: str = """
    ## Interactive 3D Network Graph

    Explore the relationships between financial assets in three dimensions.
    Each node represents an asset, and edges show the strength and type of
    relationships between them.

    **Asset Colors:**
    - 🔵 Blue: Equities (Stocks)
    - 🟢 Green: Fixed Income (Bonds)
    - 🟠 Orange: Commodities
    - 🔴 Red: Currencies
    - 🟣 Purple: Derivatives
    """

    NETWORK_METRICS_ANALYSIS_MD: str = """
    ## Network Metrics & Analytics

    Comprehensive analysis of asset relationships, distributions, and
    regulatory event impacts.
    """

    SCHEMA_RULES_GUIDE_MD: str = """
    ## Database Schema & Business Rules

    View the automatically generated schema documentation including
    relationship types, business rules, and validation constraints.
    """

    DETAILED_ASSET_INFO_MD: str = """
    ## Asset Explorer

    Select any asset to view detailed information including financial
    metrics, relationships, and connected assets.
    """

    DOC_MARKDOWN: str = """
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


class FinancialAssetApp:
    def __init__(self) -> None:
        self.graph: Optional[AssetRelationshipGraph] = None
        self._initialize_graph()

    def _initialize_graph(self) -> None:
        """Initializes the asset graph."""
        try:
            LOGGER.info("Initializing with real financial data")
            self.graph = create_real_database()
            LOGGER.info("Database initialized with %d assets", len(self.graph.assets))
        except Exception as exc:
            LOGGER.exception("%s: %s", AppConstants.INITIAL_GRAPH_ERROR, exc)
            raise

    def ensure_graph(self) -> AssetRelationshipGraph:
        """Ensure graph exists."""
        if self.graph is None:
            LOGGER.warning("Graph missing; reinitializing")
            self._initialize_graph()
        assert self.graph is not None
        return self.graph

    @staticmethod
    def _update_metrics_text(graph: AssetRelationshipGraph) -> str:
        metrics = cast(GraphMetrics, graph.calculate_metrics())
        text = AppConstants.NETWORK_STATISTICS_TEXT.format(
            total_assets=metrics["total_assets"],
            total_relationships=metrics["total_relationships"],
            average_relationship_strength=metrics["average_relationship_strength"],
            relationship_density=metrics["relationship_density"],
            regulatory_event_count=metrics["regulatory_event_count"],
            asset_class_distribution=json.dumps(metrics["asset_class_distribution"], indent=2),
        )
        for idx, (src, tgt, rel, strength) in enumerate(
            metrics["top_relationships"], 1
        ):
            text += f"{idx}. {src} → {tgt} ({rel}): {strength:.1%}\n"
        return text

    def update_all_metrics_outputs(self, graph: AssetRelationshipGraph) -> Tuple[go.Figure, go.Figure, go.Figure, str]:
        fig1, fig2, fig3 = visualize_metrics(graph)
        metrics_text = self._update_metrics_text(graph)
        return fig1, fig2, fig3, metrics_text

    @staticmethod
    def update_asset_info(
        selected_asset: Optional[str], graph: AssetRelationshipGraph
    ) -> Tuple[Dict[str, Any], AssetRelationshipPayload]:
        if not selected_asset or selected_asset not in graph.assets:
            return {}, {"outgoing": {}, "incoming": {}}
        asset: Asset = graph.assets[selected_asset]
        asset_dict: Dict[str, Any] = asdict(asset)
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

    def refresh_all_outputs(self, graph_state: AssetRelationshipGraph) -> Tuple[
        go.Figure,
        go.Figure,
        go.Figure,
        go.Figure,
        str,
        str,
        GradioUpdate,
        GradioUpdate,
    ]:
        """Refresh all Gradio outputs."""
        try:
            graph = self.ensure_graph()
            viz_3d = visualize_3d_graph(graph)
            f1, f2, f3, metrics_txt = self.update_all_metrics_outputs(graph)
            schema_rpt = generate_schema_report(graph)
            asset_choices = list(graph.assets.keys())
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
        except Exception as exc:
            LOGGER.exception("%s: %s", AppConstants.REFRESH_OUTPUTS_ERROR, exc)
            return (
                go.Figure(),
                go.Figure(),
                go.Figure(),
                go.Figure(),
                "",
                "",
                gr.update(choices=[], value=None),
                gr.update(value=str(exc), visible=True),
            )

    def refresh_visualization(
        self,
        graph_state: AssetRelationshipGraph,
        view_mode: str,
        layout_type: str,
        show_same_sector: bool,
        show_market_cap: bool,
        show_correlation: bool,
        show_corporate_bond: bool,
        show_commodity_currency: bool,
        show_income_comparison: bool,
        show_regulatory: bool,
        show_all_relationships: bool,
        toggle_arrows: bool,
    ) -> GradioUpdate:
        """Refresh 2D/3D visualization with filters."""
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
            else:
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
            return graph_viz
        except Exception as exc:
            LOGGER.exception("Visualization refresh failed: %s", exc)
            return gr.update(value=f"Error: {str(exc)}", visible=True)

    def generate_formulaic_analysis(self, graph_state: Optional[AssetRelationshipGraph]) -> Tuple[
        go.Figure,
        go.Figure,
        go.Figure,
        GradioUpdate,
        str,
        GradioUpdate,
    ]:
        """Generate formulaic analysis and visualizations."""
        try:
            LOGGER.info("Generating formulaic analysis")
            graph = self.ensure_graph() if graph_state is None else graph_state
            formulaic_analyzer = FormulaicdAnalyzer()
            formulaic_visualizer = FormulaicVisualizer()

            analysis_results: Dict[str, Any] = formulaic_analyzer.analyze_graph(graph)

            dashboard_fig: go.Figure = formulaic_visualizer.create_formula_dashboard(analysis_results)
            correlation_network_fig: go.Figure = formulaic_visualizer.create_correlation_network(
                analysis_results.get("empirical_relationships", {})
            )
            metric_comparison_fig: go.Figure = formulaic_visualizer.create_metric_comparison_chart(analysis_results)

            formulas: List[Any] = analysis_results.get("formulas", [])
            formula_choices: List[str] = [f.name for f in formulas]

            summary: Dict[str, Any] = analysis_results.get("summary", {})
            summary_text: str = self._format_formula_summary(summary, analysis_results)

            LOGGER.info("Generated formulaic analysis with %d formulas", len(formulas))
            return (
                dashboard_fig,
                correlation_network_fig,
                metric_comparison_fig,
                gr.update(
                    choices=formula_choices,
                    value=formula_choices[0] if formula_choices else None,
                ),
                summary_text,
                gr.update(visible=False),
            )
        except Exception as exc:
            LOGGER.exception("Error generating formulaic analysis: %s", exc)
            empty_fig = go.Figure()
            error_msg = f"Error generating formulaic analysis: {str(exc)}"
            return (
                empty_fig,
                empty_fig,
                empty_fig,
                gr.update(choices=[], value=None),
                error_msg,
                gr.update(value=error_msg, visible=True),
            )

    @staticmethod
    def show_formula_details(formula_name: str, graph_state: AssetRelationshipGraph) -> Tuple[go.Figure, GradioUpdate]:
        """Show detailed view of a specific formula."""
        try:
            return go.Figure(), gr.update(value=None, visible=False)
        except Exception as exc:
            LOGGER.exception("Error showing formula details: %s", exc)
            return go.Figure(), gr.update(value=f"Error: {exc}", visible=True)

    @staticmethod
    def _format_formula_summary(
        summary: Dict[str, Any], analysis_results: Dict[str, Any]
    ) -> str:
        """Format formula analysis summary for display."""
        formulas: List[Any] = analysis_results.get("formulas", [])
        empirical: Dict[str, Any] = analysis_results.get("empirical_relationships", {})

        summary_lines: List[str] = [
            "🔍 **Formulaic Analysis Summary**",
            "",
            f"📊 **Total Formulas Identified:** {len(formulas)}",
            f"📈 **Average Reliability (R²):** {summary.get('avg_r_squared', 0):.3f}",
            f"🔗 **Empirical Data Points:** {summary.get('empirical_data_points', 0)}",
            "",
            "📋 **Formula Categories:**",
        ]

        categories: Dict[str, int] = summary.get("formula_categories", {})
        for category, count in categories.items():
            summary_lines.append(f"  • {category}: {count} formulas")

        summary_lines.extend(["", "🎯 **Key Insights:**"])
        insights: List[str] = summary.get("key_insights", [])
        for insight in insights:
            summary_lines.append(f"  • {insight}")

        correlations: List[Dict[str, Any]] = empirical.get("strongest_correlations", [])
        if correlations:
            summary_lines.extend(["", "🔗 **Strongest Asset Correlations:**"])
            for corr in correlations[:3]:
                summary_lines.append(f"  • {corr['pair']}: {corr['correlation']:.3f} ({corr['strength']})")

        return "\n".join(summary_lines)

    def create_interface(self) -> gr.Blocks:
        """Create the Gradio interface for the Financial Asset Relationship Database."""
        demo: gr.Blocks = gr.Blocks(title=AppConstants.TITLE)

        with demo:
            gr.Markdown(AppConstants.MARKDOWN_HEADER)

            error_message: gr.Textbox = gr.Textbox(
                label=AppConstants.ERROR_LABEL,
                visible=False,
                interactive=False,
                elem_id="error_message",
            )

            with gr.Tabs():
                with gr.Tab("🌐 Network Visualization (2D/3D)"):
                    gr.Markdown(AppConstants.INTERACTIVE_3D_GRAPH_MD)

                    with gr.Row():
                        gr.Markdown("### 🎛️ Visualization Controls")
                    with gr.Row():
                        with gr.Column(scale=1):
                            view_mode: gr.Radio = gr.Radio(
                                label="Visualization Mode",
                                choices=["3D", "2D"],
                                value="3D",
                            )
                        with gr.Column(scale=1):
                            layout_type: gr.Radio = gr.Radio(
                                label="2D Layout Type",
                                choices=["spring", "circular", "grid"],
                                value="spring",
                                visible=False,
                            )

                    with gr.Row():
                        gr.Markdown("### 🔗 Relationship Visibility Controls")
                    with gr.Row():
                        with gr.Column(scale=1):
                            show_same_sector: gr.Checkbox = gr.Checkbox(label="Same Sector (↔)", value=True)
                            show_market_cap: gr.Checkbox = gr.Checkbox(label="Market Cap Similar (↔)", value=True)
                            show_correlation: gr.Checkbox = gr.Checkbox(label="Correlation (↔)", value=True)
                        with gr.Column(scale=1):
                            show_corporate_bond: gr.Checkbox = gr.Checkbox(
                                label="Corporate Bond → Equity (→)", value=True
                            )
                            show_commodity_currency: gr.Checkbox = gr.Checkbox(label="Commodity ↔ Currency", value=True)
                            show_income_comparison: gr.Checkbox = gr.Checkbox(label="Income Comparison (↔)", value=True)
                        with gr.Column(scale=1):
                            show_regulatory: gr.Checkbox = gr.Checkbox(label="Regulatory Impact (→)", value=True)
                            show_all_relationships: gr.Checkbox = gr.Checkbox(
                                label="Show All Relationships", value=True
                            )
                            toggle_arrows: gr.Checkbox = gr.Checkbox(label="Show Direction Arrows", value=True)

                    with gr.Row():
                        visualization_3d: gr.Plot = gr.Plot()
                    with gr.Row():
                        with gr.Column(scale=1):
                            refresh_btn: gr.Button = gr.Button(AppConstants.REFRESH_BUTTON_LABEL, variant="primary")
                        with gr.Column(scale=1):
                            reset_view_btn: gr.Button = gr.Button("Reset View & Show All", variant="secondary")
                        with gr.Column(scale=2):
                            gr.Markdown(
                                "**Legend:** ↔ = Bidirectional, → = Unidirectional"
                            )

                with gr.Tab(AppConstants.TAB_METRICS_ANALYTICS):
                    gr.Markdown(AppConstants.NETWORK_METRICS_ANALYSIS_MD)
                    with gr.Row():
                        asset_dist_chart: gr.Plot = gr.Plot()
                        rel_types_chart: gr.Plot = gr.Plot()
                    with gr.Row():
                        events_timeline_chart: gr.Plot = gr.Plot()
                    with gr.Row():
                        metrics_text: gr.Textbox = gr.Textbox(
                            label=AppConstants.NETWORK_STATISTICS_LABEL,
                            lines=10,
                            interactive=False,
                        )
                    with gr.Row():
                        refresh_metrics_btn: gr.Button = gr.Button(AppConstants.REFRESH_BUTTON_LABEL, variant="primary")

                with gr.Tab(AppConstants.TAB_SCHEMA_RULES):
                    gr.Markdown(AppConstants.SCHEMA_RULES_GUIDE_MD)
                    with gr.Row():
                        schema_report: gr.Textbox = gr.Textbox(
                            label=AppConstants.SCHEMA_REPORT_LABEL,
                            lines=25,
                            interactive=False,
                        )
                    with gr.Row():
                        refresh_schema_btn: gr.Button = gr.Button(
                            AppConstants.GENERATE_SCHEMA_BUTTON_LABEL, variant="primary"
                        )

                with gr.Tab(AppConstants.TAB_ASSET_EXPLORER):
                    gr.Markdown(AppConstants.DETAILED_ASSET_INFO_MD)
                    with gr.Row():
                        with gr.Column(scale=1):
                            asset_selector: gr.Dropdown = gr.Dropdown(
                                label=AppConstants.SELECT_ASSET_LABEL,
                                choices=[],
                                interactive=True,
                            )
                        with gr.Column(scale=3):
                            gr.Markdown("")
                    with gr.Row():
                        asset_info: gr.JSON = gr.JSON(
                            label=AppConstants.ASSET_DETAILS_LABEL
                        )
                    with gr.Row():
                        asset_relationships: gr.JSON = gr.JSON(label=AppConstants.RELATED_ASSETS_LABEL)
                    with gr.Row():
                        refresh_explorer_btn: gr.Button = gr.Button(
                            AppConstants.REFRESH_BUTTON_LABEL, variant="primary"
                        )

                with gr.Tab(AppConstants.TAB_DOCUMENTATION):
                    gr.Markdown(AppConstants.DOC_MARKDOWN)

                with gr.Tab("📊 Formulaic Analysis"):
                    gr.Markdown("""
            ## Mathematical Relationships & Formulas

            This section extracts and visualizes mathematical
            formulas and relationships between financial variables.
            """)
                    with gr.Row():
                        with gr.Column(scale=2):
                            formulaic_dashboard: gr.Plot = gr.Plot(label="Formulaic Analysis Dashboard")
                        with gr.Column(scale=1):
                            formula_selector: gr.Dropdown = gr.Dropdown(
                                label="Select Formula for Details",
                                choices=[],
                                value=None,
                                interactive=True,
                            )
                            formula_detail_view: gr.Plot = gr.Plot(
                                label="Formula Details"
                            )

                    with gr.Row():
                        with gr.Column(scale=1):
                            correlation_network: gr.Plot = gr.Plot(label="Asset Correlation Network")
                        with gr.Column(scale=1):
                            metric_comparison: gr.Plot = gr.Plot(label="Metric Comparison Chart")

                    with gr.Row():
                        with gr.Column(scale=1):
                            refresh_formulas_btn: gr.Button = gr.Button(
                                "🔄 Refresh Formulaic Analysis", variant="primary"
                            )
                        with gr.Column(scale=2):
                            formula_summary: gr.Textbox = gr.Textbox(
                                label="Formula Analysis Summary",
                                lines=5,
                                interactive=False,
                            )

            graph_state: gr.State = gr.State(value=self.graph)

            all_refresh_outputs: List[GradioUpdate] = [
                visualization_3d,
                asset_dist_chart,
                rel_types_chart,
                events_timeline_chart,
                metrics_text,
                schema_report,
                asset_selector,
                error_message,
            ]

            refresh_buttons: List[gr.Button] = [
                refresh_metrics_btn,
                refresh_schema_btn,
                refresh_explorer_btn,
            ]
            for btn in refresh_buttons:
                btn.click(
                    self.refresh_all_outputs,
                    inputs=[graph_state],
                    outputs=all_refresh_outputs,
                )

            visualization_inputs: List[GradioUpdate] = [
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
            visualization_outputs: List[GradioUpdate] = [
                visualization_3d,
                error_message,
            ]

            refresh_btn.click(
                self.refresh_visualization,
                inputs=visualization_inputs,
                outputs=visualization_outputs,
            )

            layout_type.change(
                self.refresh_visualization,
                inputs=visualization_inputs,
                outputs=visualization_outputs,
            )

            view_mode.change(
                lambda *args: (
                    gr.update(visible=args[1] == "2D"),
                    self.refresh_visualization(*args)[0],
                    gr.update(visible=False),
                ),
                inputs=visualization_inputs,
                outputs=[layout_type, visualization_3d, error_message],
            )

            formulaic_outputs: List[GradioUpdate] = [
                formulaic_dashboard,
                correlation_network,
                metric_comparison,
                formula_selector,
                formula_summary,
                error_message,
            ]
            refresh_formulas_btn.click(
                self.generate_formulaic_analysis,
                inputs=[graph_state],
                outputs=formulaic_outputs,
            )

            formula_selector.change(
                self.show_formula_details,
                inputs=[formula_selector, graph_state],
                outputs=[formula_detail_view, error_message],
            )

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
                checkbox.change(
                    self.refresh_visualization,
                    inputs=visualization_inputs,
                    outputs=visualization_outputs,
                )

            reset_view_btn.click(
                lambda g, v, l: self.refresh_visualization(
                    g, v, l, True, True, True, True, True, True, True, True, True
                ),
                inputs=[graph_state, view_mode, layout_type],
                outputs=visualization_outputs,
            )

            asset_selector.change(
                self.update_asset_info,
                inputs=[asset_selector, graph_state],
                outputs=[asset_info, asset_relationships],
            )

        return demo


if __name__ == "__main__":
    try:
        LOGGER.info(AppConstants.APP_START_INFO)
        app = FinancialAssetApp()
        demo_app = app.create_interface()
        LOGGER.info(AppConstants.APP_LAUNCH_INFO)
        demo_app.launch()
    except Exception as exc:
        LOGGER.exception("%s: %s", AppConstants.APP_START_ERROR, exc)
