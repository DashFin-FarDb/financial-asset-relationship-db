from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any, Optional

import gradio as gr
import plotly.graph_objects as go

from src.analysis.formulaic_analysis import FormulaicAnalyzer
from src.data import real_data_fetcher
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Asset
from src.reports.schema_report import generate_schema_report
from src.visualizations.formulaic_visuals import FormulaicVisualizer
from src.visualizations.graph_2d_visuals import visualize_2d_graph
from src.visualizations.graph_visuals import visualize_3d_graph, visualize_3d_graph_with_filters

logger = logging.getLogger(__name__)


class AppConstants:
    TITLE = "Financial Asset Relationship Database Visualization"
    MARKDOWN_HEADER = """
    # 🏦 Financial Asset Relationship Network

    A comprehensive 3D visualization of interconnected financial
    assets across all major classes:
    **Equities, Bonds, Commodities, Currencies, and Regulatory
    Events**
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

    INTERACTIVE_3D_GRAPH_MD = """
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

    NETWORK_METRICS_ANALYSIS_MD = """
    ## Network Metrics & Analytics

    Comprehensive analysis of asset relationships, distributions, and
    regulatory event impacts.
    """

    SCHEMA_RULES_GUIDE_MD = """
    ## Database Schema & Business Rules

    View the automatically generated schema documentation including
    relationship types, business rules, and validation constraints.
    """

    DETAILED_ASSET_INFO_MD = """
    ## Asset Explorer

    Select any asset to view detailed information including financial
    metrics, relationships, and connected assets.
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
    - **Deterministic Layout**: Consistent 3D positioning across
      sessions

    ### Asset Classes
    - Equities, Bonds, Commodities, Currencies, Derivatives
    - Relationship types: sector affinity, corporate links,
      currency exposure, regulatory events

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


def _coerce_json_safe(value: Any) -> Any:
    """Coerce common non-JSON-safe values into safe primitives."""
    # Keep the common JSON primitives as-is.
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    # Convert enums / custom objects to string representation.
    try:
        import enum  # local import to avoid unused warnings in some setups

        if isinstance(value, enum.Enum):
            return value.value  # type: ignore[no-any-return]
    except Exception:
        # If enum is not available or detection fails, fall back below.
        pass
    return str(value)


def _asset_to_json_dict(asset: Asset) -> dict[str, Any]:
    """Convert an Asset dataclass to a JSON-serialisable dictionary."""
    data = asdict(asset)
    # Ensure common enum field is exposed as a plain value string.
    if hasattr(asset, "asset_class"):
        data["asset_class"] = getattr(asset, "asset_class").value
    for k, v in list(data.items()):
        data[k] = _coerce_json_safe(v)
    return data


class FinancialAssetApp:
    @staticmethod
    def _create_database() -> AssetRelationshipGraph:
        """Create a database/graph via a compatible factory in real_data_fetcher.

        This avoids hard failures when the project refactors the exact factory name.
        """
        candidates = (
            "create_real_database",
            "create_sample_database",
            "create_database",
            "create_real_data_database",
        )
        for name in candidates:
            fn = getattr(real_data_fetcher, name, None)
            if callable(fn):
                graph = fn()
                if isinstance(graph, AssetRelationshipGraph):
                    return graph
                raise TypeError(f"{name}() returned {type(graph)!r}, expected AssetRelationshipGraph")

        raise AttributeError(
            "No known database factory found in src.data.real_data_fetcher. " f"Tried: {', '.join(candidates)}"
        )

    @staticmethod
    def _update_metrics_text(graph: AssetRelationshipGraph) -> str:
        """Generate formatted text for network statistics."""
        metrics = graph.calculate_metrics()
        text = AppConstants.NETWORK_STATISTICS_TEXT.format(
            total_assets=metrics.get("total_assets", 0),
            total_relationships=metrics.get("total_relationships", 0),
            average_relationship_strength=metrics.get("average_relationship_strength", 0.0),
            relationship_density=metrics.get("relationship_density", 0.0),
            regulatory_event_count=metrics.get("regulatory_event_count", 0),
            asset_class_distribution=json.dumps(
                metrics.get("asset_class_distribution", {}),
                indent=2,
            ),
        )

        top_rels = metrics.get("top_relationships", [])
        if isinstance(top_rels, list):
            for idx, item in enumerate(top_rels, 1):
                if (
                    isinstance(item, tuple)
                    and len(item) == 4
                    and isinstance(item[0], str)
                    and isinstance(item[1], str)
                    and isinstance(item[2], str)
                ):
                    s, t, rel, strength = item
                    try:
                        text += f"{idx}. {s} → {t} ({rel}): {float(strength):.1%}\n"
                    except (TypeError, ValueError):
                        text += f"{idx}. {s} → {t} ({rel}): n/a\n"
        return text

    @staticmethod
    def update_asset_info(
        selected_asset: Optional[str],
        graph: AssetRelationshipGraph,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return asset details plus outgoing/incoming relationship dictionaries."""
        if not selected_asset or selected_asset not in graph.assets:
            return {}, {"outgoing": {}, "incoming": {}}

        asset: Asset = graph.assets[selected_asset]
        asset_dict = _asset_to_json_dict(asset)

        outgoing: dict[str, dict[str, Any]] = {
            target_id: {"relationship_type": rel_type, "strength": strength}
            for target_id, rel_type, strength in graph.relationships.get(selected_asset, [])
        }

        incoming_relationships = getattr(graph, "incoming_relationships", {})
        incoming: dict[str, dict[str, Any]] = {
            src_id: {"relationship_type": rel_type, "strength": strength}
            for src_id, rel_type, strength in incoming_relationships.get(selected_asset, [])
        }

        return asset_dict, {"outgoing": outgoing, "incoming": incoming}

    def update_all_metrics_outputs(
        self,
        graph: AssetRelationshipGraph,
    ) -> tuple[go.Figure, go.Figure, go.Figure, str]:
        """Build metric figures and formatted network statistics text.

        If you already have an implementation elsewhere, keep that and remove this
        placeholder.
        """
        metrics_text = self._update_metrics_text(graph)
        return go.Figure(), go.Figure(), go.Figure(), metrics_text

    def refresh_all_outputs(self, graph_state: AssetRelationshipGraph) -> tuple[Any, ...]:
        """Refresh all UI outputs derived from the current graph state."""
        try:
            graph = graph_state
            logger.info("Refreshing all visualization outputs")

            viz_3d = visualize_3d_graph(graph)
            f1, f2, f3, metrics_txt = self.update_all_metrics_outputs(graph)
            schema_rpt = generate_schema_report(graph)

            asset_choices = sorted(graph.assets.keys())
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
                gr.update(value=f"Error: {exc}", visible=True),
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
    ) -> tuple[go.Figure, Any]:
        """Refresh the graph visualisation with 2D/3D mode and filters."""
        try:
            graph = graph_state

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

            return graph_viz, gr.update(visible=False)

        except Exception as exc:
            logger.error("Error refreshing visualization: %s", exc)
            empty_fig = go.Figure()
            error_msg = f"Error refreshing visualization: {exc}"
            return empty_fig, gr.update(value=error_msg, visible=True)

    def generate_formulaic_analysis(self, graph_state: AssetRelationshipGraph) -> tuple[Any, ...]:
        """Generate formulaic analysis outputs and UI updates."""
        try:
            logger.info("Generating formulaic analysis")
            graph = graph_state

            formulaic_analyzer = FormulaicAnalyzer()
            formulaic_visualizer = FormulaicVisualizer()

            analysis_results = formulaic_analyzer.analyze_graph(graph)

            dashboard_fig = formulaic_visualizer.create_formula_dashboard(analysis_results)
            correlation_network_fig = formulaic_visualizer.create_correlation_network(
                analysis_results.get("empirical_relationships", {})
            )
            metric_comparison_fig = formulaic_visualizer.create_metric_comparison_chart(analysis_results)

            formulas = analysis_results.get("formulas", [])
            formula_choices = [f.name for f in formulas] if isinstance(formulas, list) else []

            summary = analysis_results.get("summary", {})
            summary_text = self._format_formula_summary(summary, analysis_results)

            logger.info("Generated formulaic analysis with %d formulas", len(formula_choices))
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
            logger.error("Error generating formulaic analysis: %s", exc)
            empty_fig = go.Figure()
            error_msg = f"Error generating formulaic analysis: {exc}"
            return (
                empty_fig,
                empty_fig,
                empty_fig,
                gr.update(choices=[], value=None),
                error_msg,
                gr.update(value=error_msg, visible=True),
            )

    @staticmethod
    def show_formula_details(
        formula_name: str,
        graph_state: AssetRelationshipGraph,
    ) -> tuple[go.Figure, Any]:
        """Show a detailed view of a specific formula."""
        try:
            _ = (formula_name, graph_state)
            return go.Figure(), gr.update(value=None, visible=False)
        except Exception as exc:
            logger.error("Error showing formula details: %s", exc)
            return go.Figure(), gr.update(value=f"Error: {exc}", visible=True)

    @staticmethod
    def _format_formula_summary(
        summary: dict[str, Any],
        analysis_results: dict[str, Any],
    ) -> str:
        """Build a human-readable formulaic analysis summary for display."""
        formulas = analysis_results.get("formulas", [])
        empirical = analysis_results.get("empirical_relationships", {})

        total_formulas = len(formulas) if isinstance(formulas, list) else 0
        avg_r2 = float(summary.get("avg_r_squared", 0.0))
        data_points = int(summary.get("empirical_data_points", 0))

        summary_lines: list[str] = [
            "🔍 **Formulaic Analysis Summary**",
            "",
            f"📊 **Total Formulas Identified:** {total_formulas}",
            f"📈 **Average Reliability (R²):** {avg_r2:.3f}",
            f"🔗 **Empirical Data Points:** {data_points}",
            "",
            "📋 **Formula Categories:**",
        ]

        categories = summary.get("formula_categories", {})
        if isinstance(categories, dict):
            for category, count in categories.items():
                summary_lines.append(f"  • {category}: {count} formulas")

        summary_lines.extend(["", "🎯 **Key Insights:**"])

        insights = summary.get("key_insights", [])
        if isinstance(insights, list):
            for insight in insights:
                summary_lines.append(f"  • {insight}")

        correlations = empirical.get("strongest_correlations", [])
        if isinstance(correlations, list) and correlations:
            summary_lines.extend(["", "🔗 **Strongest Asset Correlations:**"])
            for corr in correlations[:3]:
                if isinstance(corr, dict):
                    pair = corr.get("pair", "n/a")
                    correlation = corr.get("correlation", 0.0)
                    strength = corr.get("strength", "n/a")
                    try:
                        summary_lines.append(f"  • {pair}: {float(correlation):.3f} ({strength})")
                    except (TypeError, ValueError):
                        summary_lines.append(f"  • {pair}: n/a ({strength})")

        return "\n".join(summary_lines)

    def _initialize_session(self) -> tuple[Any, ...]:
        """Create a per-session graph and return initial UI outputs."""
        graph = self._create_database()
        outputs = self.refresh_all_outputs(graph)
        # prepend graph for gr.State output
        return (graph, *outputs)

    def create_interface(self) -> gr.Blocks:
        """Create and configure the Gradio Blocks interface."""
        with gr.Blocks(title=AppConstants.TITLE) as interface:
            gr.Markdown(AppConstants.MARKDOWN_HEADER)

            error_message = gr.Textbox(
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
                            view_mode = gr.Radio(
                                label="Visualization Mode",
                                choices=["3D", "2D"],
                                value="3D",
                            )
                        with gr.Column(scale=1):
                            layout_type = gr.Radio(
                                label="2D Layout Type",
                                choices=["spring", "circular", "grid"],
                                value="spring",
                                visible=False,
                            )

                    with gr.Row():
                        gr.Markdown("### 🔗 Relationship Visibility Controls")
                    with gr.Row():
                        with gr.Column(scale=1):
                            show_same_sector = gr.Checkbox(
                                label="Same Sector (↔)",
                                value=True,
                            )
                            show_market_cap = gr.Checkbox(
                                label="Market Cap Similar (↔)",
                                value=True,
                            )
                            show_correlation = gr.Checkbox(
                                label="Correlation (↔)",
                                value=True,
                            )
                        with gr.Column(scale=1):
                            show_corporate_bond = gr.Checkbox(
                                label="Corporate Bond Links (↔)",
                                value=True,
                            )
                            show_commodity_currency = gr.Checkbox(
                                label="Commodity/Currency Links (↔)",
                                value=True,
                            )
                            show_income_comparison = gr.Checkbox(
                                label="Income Comparison (↔)",
                                value=True,
                            )
                        with gr.Column(scale=1):
                            show_regulatory = gr.Checkbox(
                                label="Regulatory Events (↔)",
                                value=True,
                            )
                            show_all_relationships = gr.Checkbox(
                                label="Show All Relationships",
                                value=False,
                            )
                            toggle_arrows = gr.Checkbox(
                                label="Show Direction Arrows",
                                value=True,
                            )

                    with gr.Row():
                        refresh_btn = gr.Button(
                            AppConstants.REFRESH_BUTTON_LABEL,
                            variant="primary",
                        )

                    visualization_3d = gr.Plot(label="Network Graph")

                with gr.Tab("📊 Metrics & Analytics"):
                    gr.Markdown(AppConstants.NETWORK_METRICS_ANALYSIS_MD)
                    with gr.Row():
                        with gr.Column(scale=1):
                            asset_dist_chart = gr.Plot(label="Asset Class Distribution")
                        with gr.Column(scale=1):
                            rel_types_chart = gr.Plot(label="Relationship Types")

                    with gr.Row():
                        with gr.Column(scale=1):
                            events_timeline_chart = gr.Plot(label="Events Timeline")

                    with gr.Row():
                        with gr.Column(scale=1):
                            refresh_metrics_btn = gr.Button(
                                "🔄 Refresh Metrics",
                                variant="primary",
                            )
                            metrics_text = gr.Textbox(
                                label=AppConstants.NETWORK_STATISTICS_LABEL,
                                lines=15,
                                interactive=False,
                            )

                with gr.Tab("📋 Schema & Rules"):
                    gr.Markdown(AppConstants.SCHEMA_RULES_GUIDE_MD)

                    with gr.Row():
                        refresh_schema_btn = gr.Button(
                            AppConstants.GENERATE_SCHEMA_BUTTON_LABEL,
                            variant="primary",
                        )
                    schema_report = gr.Markdown(label=AppConstants.SCHEMA_REPORT_LABEL)

                with gr.Tab("🔍 Asset Explorer"):
                    gr.Markdown(AppConstants.DETAILED_ASSET_INFO_MD)

                    with gr.Row():
                        refresh_explorer_btn = gr.Button(
                            "🔄 Refresh Asset Explorer",
                            variant="primary",
                        )

                    with gr.Row():
                        with gr.Column(scale=1):
                            asset_selector = gr.Dropdown(
                                label=AppConstants.SELECT_ASSET_LABEL,
                                choices=[],
                                value=None,
                            )
                        with gr.Column(scale=2):
                            asset_details = gr.JSON(label=AppConstants.ASSET_DETAILS_LABEL)

                    with gr.Row():
                        related_assets = gr.JSON(label=AppConstants.RELATED_ASSETS_LABEL)

                with gr.Tab("🧮 Formulaic Analysis"):
                    gr.Markdown("## 🧮 Formulaic Financial Analysis")

                    with gr.Row():
                        with gr.Column(scale=1):
                            formula_selector = gr.Dropdown(
                                label="Select Formula",
                                choices=[],
                                value=None,
                            )
                            formula_detail_view = gr.Plot(label="Formula Details")
                        with gr.Column(scale=1):
                            refresh_formulas_btn = gr.Button(
                                "🔄 Refresh Formulaic Analysis",
                                variant="primary",
                            )

                    with gr.Row():
                        with gr.Column(scale=2):
                            formulaic_dashboard = gr.Plot(label="Formulaic Analysis Dashboard")
                        with gr.Column(scale=1):
                            formula_summary = gr.Textbox(
                                label="Formula Analysis Summary",
                                lines=5,
                                interactive=False,
                            )

                    with gr.Row():
                        with gr.Column(scale=1):
                            correlation_network = gr.Plot(label="Asset Correlation Network")
                        with gr.Column(scale=1):
                            metric_comparison = gr.Plot(label="Metric Comparison Chart")

                with gr.Tab("📖 Documentation"):
                    gr.Markdown(AppConstants.DOC_MARKDOWN)

            # Per-session graph state, created at load time.
            graph_state: gr.State = gr.State()

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

            refresh_buttons = [refresh_metrics_btn, refresh_schema_btn, refresh_explorer_btn]
            for btn in refresh_buttons:
                btn.click(
                    self.refresh_all_outputs,
                    inputs=[graph_state],
                    outputs=all_refresh_outputs,
                )

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
            refresh_btn.click(
                self.refresh_visualization,
                inputs=visualization_inputs,
                outputs=[visualization_3d, error_message],
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

            refresh_formulas_btn.click(
                self.generate_formulaic_analysis,
                inputs=[graph_state],
                outputs=[
                    formulaic_dashboard,
                    correlation_network,
                    metric_comparison,
                    formula_selector,
                    formula_summary,
                    error_message,
                ],
            )

            formula_selector.change(
                self.show_formula_details,
                inputs=[formula_selector, graph_state],
                outputs=[formula_detail_view, error_message],
            )

            asset_selector.change(
                self.update_asset_info,
                inputs=[asset_selector, graph_state],
                outputs=[asset_details, related_assets],
            )

            # Initialise per session at load.
            interface.load(
                self._initialize_session,
                inputs=[],
                outputs=[graph_state, *all_refresh_outputs],
            )

        return interface


def main() -> None:
    """Entry point for launching the Gradio app."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        logger.info(AppConstants.APP_START_INFO)
        app = FinancialAssetApp()
        interface = app.create_interface()
        logger.info(AppConstants.APP_LAUNCH_INFO)
        interface.launch()
    except Exception as exc:
        logger.error("%s: %s", AppConstants.APP_START_ERROR, exc)
        raise


if __name__ == "__main__":
    main()
