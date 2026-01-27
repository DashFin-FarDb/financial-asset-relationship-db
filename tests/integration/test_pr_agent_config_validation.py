# file: tests/integration/test_pr_agent_config_validation.py

import json
import logging
from dataclasses import asdict
from typing import Any, Dict, Optional, Tuple

import gradio as gr
import plotly.graph_objects as go

from src.analysis.formulaic_analysis import FormulaicAnalyzer
from src.analysis.formulaic_visualizer import FormulaicVisualizer
from src.data.real_data_fetcher import create_real_database
from src.logging import LOGGER
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Asset
from src.reports.schema_report import generate_schema_report
from src.visualizations.graph_2d_visuals import visualize_2d_graph
from src.visualizations.graph_visuals import (
    visualize_3d_graph,
    visualize_3d_graph_with_filters,
)
from src.visualizations.metric_visuals import visualize_metrics

# ... other imports for a new app ...


# Move this after class definitions or define AssetUIController first
app_inst = AssetUIController()
app_inst.create_interface().launch()


# Local source imports

# Configure logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
LOGGER = logging.getLogger(__name__)


class AppConstants:
    """Holds all application constants including labels, markdown, and messages."""

    TITLE = "Financial Asset Relationship Database Visualization"

    MARKDOWN_HEADER = """
    # 🏦 Financial Asset Relationship Network
    A comprehensive 3D visualization of interconnected financial assets.
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
    Explore relationships in 3D. Nodes represent assets; edges show strength.
    - 🔵 Blue: Equities | 🟢 Green: Bonds | 🟠 Orange: Commodities | 🔴 Red: Currencies
    """

    NETWORK_METRICS_ANALYSIS_MD = "## Network Metrics & Analytics"
    SCHEMA_RULES_GUIDE_MD = "## Database Schema & Business Rules"
    DETAILED_ASSET_INFO_MD = "## Asset Explorer"

    DOC_MARKDOWN = """
    ## Documentation & Help
    ### Features
    - **Cross-Asset Analysis**: Automatic relationship discovery
    - **Regulatory Integration**: Corporate events impact modeling
    - **Real-time Metrics**: Network statistics and strength analysis
    """

    NETWORK_STATISTICS_TEXT = """Network Statistics:
Total Assets: {total_assets}
Total Relationships: {total_relationships}
Avg Strength: {average_relationship_strength:.3f}
Density: {relationship_density:.2f}%
Regulatory Events: {regulatory_event_count}

Asset Class Distribution:
{asset_class_distribution}

Top Relationships:
"""


class FinancialAssetApp:
    """Main application logic for the Asset Database."""

    def __init__(self) -> None:
        self._initialize_graph()

    def _initialize_graph(self) -> None:
        """Builds the asset relationship graph from real financial data."""
        try:
            LOGGER.info("Initializing with data from Yahoo Finance")
            self.graph = create_real_database()
            LOGGER.info("Database initialized with %s assets", len(self.graph.assets))
        except Exception as e:
            LOGGER.error("%s: %s", AppConstants.INITIAL_GRAPH_ERROR, e)
            raise

    def ensure_graph(self) -> AssetRelationshipGraph:
        """Ensures the graph is initialized before access."""
        if self.graph is None:
            self._initialize_graph()
        if self.graph is None:
            raise RuntimeError("Asset graph initialization failed")
        return self.graph

    def _update_metrics_text(self, graph: AssetRelationshipGraph) -> str:
        """Formats network statistics into a human-readable string."""
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
    ) -> Tuple[go.Figure, go.Figure, go.Figure, str]:
        """Generates all metric charts and summary text."""
        f1, f2, f3 = visualize_metrics(graph)
        text = self._update_metrics_text(graph)
        return f1, f2, f3, text


class AssetUIController(FinancialAssetApp):
    """Controller handling UI interactions and Gradio interface construction."""

    @staticmethod
    def update_asset_info(
        selected_asset: Optional[str],
        graph: AssetRelationshipGraph,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Returns details and relationships for a selected asset."""
        if not selected_asset or selected_asset not in graph.assets:
            return {}, {"outgoing": {}, "incoming": {}}

        asset: Asset = graph.assets[selected_asset]
        asset_dict = asdict(asset)
        asset_dict["asset_class"] = asset.asset_class.value

        def get_rels(rel_map: Dict) -> Dict:
            return {
                tid: {"type": rtype, "strength": strg}
                for tid, rtype, strg in rel_map.get(selected_asset, [])
            }

        return asset_dict, {
            "outgoing": get_rels(graph.relationships),
            "incoming": get_rels(graph.incoming_relationships),
        }

    def refresh_all_outputs(self, graph_state: AssetRelationshipGraph) -> Tuple:
        """Refreshes all UI components simultaneously."""
        try:
            graph = graph_state or self.ensure_graph()
            viz_3d = visualize_3d_graph(graph)
            f1, f2, f3, m_text = self.update_all_metrics_outputs(graph)
            report = generate_schema_report(graph)
            choices = list(graph.assets.keys())

            return (
                viz_3d,
                f1,
                f2,
                f3,
                m_text,
                report,
                gr.update(choices=choices, value=None),
                gr.update(value="", visible=False),
            )
        except Exception as e:
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
                gr.update(value=f"Error: {e}", visible=True),
            )

    def refresh_visualization(
        self, graph_state: AssetRelationshipGraph, **kwargs
    ) -> Tuple:
        """Filters and updates the 2D or 3D network plot."""
        try:
            graph = graph_state or self.ensure_graph()
            mode = kwargs.pop("view_mode", "3D")
            if mode == "2D":
                fig = visualize_2d_graph(graph, **kwargs)
            else:
                fig = visualize_3d_graph_with_filters(graph, **kwargs)
            return fig, gr.update(visible=False)
        except Exception as e:
            LOGGER.exception("Viz Error")
            return go.Figure(), gr.update(value=str(e), visible=True)

    def generate_formulaic_analysis(
        self, graph_state: Optional[AssetRelationshipGraph]
    ) -> Tuple:
        """Performs mathematical relationship extraction."""
        try:
            graph = graph_state or self.ensure_graph()
            analyzer = FormulaicAnalyzer()
            visualizer = FormulaicVisualizer()
            results = analyzer.analyze_graph(graph)

            return (
                visualizer.create_formula_dashboard(results),
                visualizer.create_correlation_network(
                    results.get("empirical_relationships", {})
                ),
                visualizer.create_metric_comparison_chart(results),
                gr.update(choices=[f.name for f in results.get("formulas", [])]),
                self._format_formula_summary(results.get("summary", {}), results),
                gr.update(visible=False),
            )
        except Exception as e:
            LOGGER.exception("Formula Error")
            return (
                go.Figure(),
                go.Figure(),
                go.Figure(),
                gr.update(choices=[]),
                "Error",
                gr.update(value=str(e), visible=True),
            )

    @staticmethod
    def _format_formula_summary(summary: Dict, results: Dict) -> str:
        """Builds markdown summary of formulaic analysis."""
        lines = [
            "**Formulaic Analysis Summary**",
            f"Formulas: {len(results.get('formulas', []))}",
            f"Avg R²: {summary.get('avg_r_squared', 0.0):.3f}",
        ]
        return "\n".join(lines)

    def create_interface(self) -> gr.Blocks:
        """Constructs the Gradio UI."""
        with gr.Blocks(title=AppConstants.TITLE) as demo_ui:
            gr.Markdown(AppConstants.MARKDOWN_HEADER)
            error_box = gr.Textbox(label="Status", visible=False)
            graph_state = gr.State(value=self.graph)

            with gr.Tabs():
                with gr.Tab("🌐 Network"):
                    with gr.Row():
                        view_mode = gr.Radio(["3D", "2D"], label="Mode", value="3D")
                        layout = gr.Radio(
                            ["spring", "circular"], label="2D Layout", visible=False
                        )
                    # Mapping filters to a dict for easy passing
                    filters = {
                        "show_same_sector": gr.Checkbox(label="Sector", value=True),
                        "show_correlation": gr.Checkbox(
                            label="Correlation", value=True
                        ),
                        "show_regulatory": gr.Checkbox(label="Regulatory", value=True),
                    }
                    viz_plot = gr.Plot()
                    refresh_btn = gr.Button("Refresh", variant="primary")

                with gr.Tab("📊 Metrics"):
                    m_f1 = gr.Plot()
                    m_text = gr.Textbox(label="Stats", lines=10)

                with gr.Tab("🧮 Formulas"):
                    f_dash = gr.Plot()
                    f_sum = gr.Textbox(label="Analysis Summary")
                    f_btn = gr.Button("Analyze Formulas")

            # Event Handlers
            refresh_btn.click(
                fn=self.refresh_all_outputs,
                inputs=[graph_state],
                outputs=[...],
            )

            f_btn.click(
                self.generate_formulaic_analysis,
                inputs=[graph_state],
                outputs=[
                    f_dash,
                    f_corr_network,
                    f_metric_chart,
                    f_formula_dropdown,
                    f_sum,
                    error_box,
                ],
            )

        return demo_ui


if __name__ == "__main__":
    try:
        app_inst = AssetUIController()
        app_inst.create_interface().launch()
    except Exception as fatal_e:
        LOGGER.error("Startup failed: %s", fatal_e)
