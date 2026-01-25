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
from src.visualizations.graph_visuals import (
    visualize_3d_graph,
    visualize_3d_graph_with_filters,
)
from src.visualizations.metric_visuals import visualize_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AppConstants:
    TITLE = "Financial Asset Relationship Database Visualization"
    ERROR_LABEL = "Error"
    REFRESH_BUTTON_LABEL = "Refresh Visualization"
    GENERATE_SCHEMA_BUTTON_LABEL = "Generate Schema Report"

    TAB_METRICS_ANALYTICS = "Metrics & Analytics"
    TAB_SCHEMA_RULES = "Schema & Rules"
    TAB_ASSET_EXPLORER = "Asset Explorer"
    TAB_DOCUMENTATION = "Documentation"

    SELECT_ASSET_LABEL = "Select Asset"
    ASSET_DETAILS_LABEL = "Asset Details"
    RELATED_ASSETS_LABEL = "Related Assets"
    NETWORK_STATISTICS_LABEL = "Network Statistics"
    SCHEMA_REPORT_LABEL = "Schema Report"

    INITIAL_GRAPH_ERROR = "Failed to create sample database"
    REFRESH_OUTPUTS_ERROR = "Error refreshing outputs"
    APP_START_INFO = "Starting application"
    APP_LAUNCH_INFO = "Launching Gradio interface"
    APP_START_ERROR = "Failed to start application"

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
    def __init__(self) -> None:
        self.graph: Optional[AssetRelationshipGraph] = None
        self._initialize_graph()

    def _initialize_graph(self) -> None:
        try:
            self.graph = create_real_database()
            logger.info("Initialized graph with %d assets", len(self.graph.assets))
        except Exception as exc:
            logger.error("%s: %s", AppConstants.INITIAL_GRAPH_ERROR, exc)
            raise

    def ensure_graph(self) -> AssetRelationshipGraph:
        if self.graph is None:
            self._initialize_graph()
        return self.graph

    @staticmethod
    def _update_metrics_text(graph: AssetRelationshipGraph) -> str:
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

        for idx, (src, tgt, rel, strength) in enumerate(
            metrics["top_relationships"], start=1
        ):
            text += f"{idx}. {src} → {tgt} ({rel}): {strength:.1%}\n"

        return text

    def update_all_metrics_outputs(self, graph: AssetRelationshipGraph):
        fig1, fig2, fig3 = visualize_metrics(graph)
        return fig1, fig2, fig3, self._update_metrics_text(graph)

    @staticmethod
    def update_asset_info(
        selected_asset: Optional[str],
        graph: AssetRelationshipGraph,
    ) -> Tuple[Dict, Dict]:
        if not selected_asset or selected_asset not in graph.assets:
            return {}, {"outgoing": {}, "incoming": {}}

        asset: Asset = graph.assets[selected_asset]
        asset_dict = asdict(asset)
        asset_dict["asset_class"] = asset.asset_class.value

        outgoing = {
            tgt: {"relationship_type": r, "strength": s}
            for tgt, r, s in graph.relationships.get(selected_asset, [])
        }
        incoming = {
            src: {"relationship_type": r, "strength": s}
            for src, r, s in graph.incoming_relationships.get(selected_asset, [])
        }

        return asset_dict, {"outgoing": outgoing, "incoming": incoming}

    def refresh_all_outputs(self, graph_state: AssetRelationshipGraph):
        try:
            graph = self.ensure_graph()
            viz_3d = visualize_3d_graph(graph)
            f1, f2, f3, metrics_text = self.update_all_metrics_outputs(graph)
            schema_report = generate_schema_report(graph)

            return (
                viz_3d,
                f1,
                f2,
                f3,
                metrics_text,
                schema_report,
                gr.update(choices=list(graph.assets.keys()), value=None),
                gr.update(value="", visible=False),
            )
        except Exception as exc:
            logger.error("%s: %s", AppConstants.REFRESH_OUTPUTS_ERROR, exc)
            return (
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(choices=[], value=None),
                gr.update(value=str(exc), visible=True),
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
        try:
            graph = self.ensure_graph()

            if view_mode == "2D":
                fig = visualize_2d_graph(
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
                fig = visualize_3d_graph_with_filters(
                    graph,
                    show_same_sector=show_same_sector,
                    show_market_cap=show_market_cap,
                    show_correlation=show_correlation,
                    show_corporate_bond=show_corporate_bond,
                    show_commodity_currency=show_commodity_currency,
                    show_income_comparison=show_income_comparison,
                    show_regulatory=show_regulatory,
                    show_all_relationships=show_all_relationships,
                )

            return fig, gr.update(visible=False)
        except Exception as exc:
            logger.error("Visualization error: %s", exc)
            return go.Figure(), gr.update(value=str(exc), visible=True)

    def generate_formulaic_analysis(self, graph_state):
        try:
            graph = self.ensure_graph()
            analyzer = FormulaicdAnalyzer()
            visualizer = FormulaicVisualizer()

            results = analyzer.analyze_graph(graph)
            formulas = results.get("formulas", [])

            return (
                visualizer.create_formula_dashboard(results),
                visualizer.create_correlation_network(
                    results.get("empirical_relationships", {})
                ),
                visualizer.create_metric_comparison_chart(results),
                gr.update(
                    choices=[f.name for f in formulas],
                    value=formulas[0].name if formulas else None,
                ),
                self._format_formula_summary(results.get("summary", {}), results),
                gr.update(visible=False),
            )
        except Exception as exc:
            logger.error("Formulaic analysis error: %s", exc)
            empty = go.Figure()
            return (
                empty,
                empty,
                empty,
                gr.update(choices=[], value=None),
                str(exc),
                gr.update(value=str(exc), visible=True),
            )

    @staticmethod
    def show_formula_details(formula_name: str, graph_state):
        return go.Figure(), gr.update(visible=False)

    @staticmethod
    def _format_formula_summary(summary: Dict, analysis_results: Dict) -> str:
        lines = [
            "Formulaic Analysis Summary",
            f"Total formulas: {len(analysis_results.get('formulas', []))}",
            f"Average R²: {summary.get('avg_r_squared', 0):.3f}",
        ]
        return "\n".join(lines)

    def create_interface(self):
        with gr.Blocks(title=AppConstants.TITLE) as demo:
            error_message = gr.Textbox(
                label=AppConstants.ERROR_LABEL,
                visible=False,
                interactive=False,
            )

            visualization_3d = gr.Plot()
            asset_dist = gr.Plot()
            rel_types = gr.Plot()
            timeline = gr.Plot()
            metrics_text = gr.Textbox(interactive=False)
            schema_report = gr.Textbox(interactive=False)
            asset_selector = gr.Dropdown(choices=[])
            asset_info = gr.JSON()
            asset_relationships = gr.JSON()

            graph_state = gr.State(self.graph)

            refresh_btn = gr.Button(AppConstants.REFRESH_BUTTON_LABEL)

            refresh_btn.click(
                self.refresh_all_outputs,
                inputs=[graph_state],
                outputs=[
                    visualization_3d,
                    asset_dist,
                    rel_types,
                    timeline,
                    metrics_text,
                    schema_report,
                    asset_selector,
                    error_message,
                ],
            )

        return demo


if __name__ == "__main__":
    try:
        logger.info(AppConstants.APP_START_INFO)
        app = FinancialAssetApp()
        demo = app.create_interface()
        logger.info(AppConstants.APP_LAUNCH_INFO)
        demo.launch()
    except Exception as exc:
        logger.error("%s: %s", AppConstants.APP_START_ERROR, exc)
