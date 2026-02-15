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
from src.visualizations.graph_visuals import (
    visualize_3d_graph,
    visualize_3d_graph_with_filters,
)
from src.visualizations.metric_visuals import visualize_metrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


class AppConstants:
    """
    Container for application-wide constant values such as titles, labels,
    tab names, and error messages used in the Financial Asset Relationship
    Database Visualization application.
    """
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


class FinancialAssetApp:
    """Main application class for managing and interacting with the financial asset relationship graph."""
    def __init__(self) -> None:
        """
        Create a FinancialAssetApp instance and ensure its internal asset
        relationship graph is initialized.

        Initializes the instance and sets the `graph` attribute to a ready
        AssetRelationshipGraph. If graph creation fails, the constructor will
        propagate the initialization error.
        """
        self.graph: Optional[AssetRelationshipGraph] = None
        self._initialize_graph()

    @staticmethod
    def _create_database() -> AssetRelationshipGraph:
        """
        Create an AssetRelationshipGraph by locating and invoking a factory function in
        src.data.real_data_fetcher.

        The function probes a set of known factory names and calls the first callable
        it finds to obtain the graph.

        Returns:
            AssetRelationshipGraph: The constructed asset relationship graph.

        Raises:
            TypeError: If a discovered factory is callable but returns a value that is not
                an AssetRelationshipGraph.
            AttributeError: If no recognized factory function is present in
                src.data.real_data_fetcher.
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
                logger.warning(
                    "%s() returned %r, expected AssetRelationshipGraph",
                    name,
                    type(graph),
                )
                continue

        raise AttributeError(
            "No known database factory found in "
            "src.data.real_data_fetcher. Tried: "
            f"{', '.join(candidates)}"
        )

    def _initialize_graph(self) -> None:
        """Initializes the asset graph, creating a sample database if necessary."""
        try:
            logger.info("Initializing financial data graph")
            self.graph = self._create_database()
            logger.info("Database initialized with %s assets", len(self.graph.assets))
        except Exception as exc:
            logger.error("%s: %s", AppConstants.INITIAL_GRAPH_ERROR, exc)
            raise

    def ensure_graph(self) -> AssetRelationshipGraph:
        """Ensures the graph is initialized, re-creating sample data if it's None."""
        # At this point it must be non-None
        if self.graph is None:
            raise RuntimeError("Graph initialisation failed")
        return self.graph

    @staticmethod
    def _update_metrics_text(graph: AssetRelationshipGraph) -> str:
        """
        Builds a human-readable network statistics text block for the provided asset
        relationship graph.

        The returned text contains totals (assets, relationships), average
        relationship strength, relationship density, regulatory event count, a JSON-
        formatted asset class distribution, and — when available — a numbered list
        of top relationships including pair, relationship type, and strength (shown as
        a percentage or `n/a` if not convertible).

        Parameters:
            graph (AssetRelationshipGraph): Graph from which metrics are calculated.

        Returns:
            str: Formatted multi-line metrics summary suitable for display in the UI.
        """
        metrics = graph.calculate_metrics()
        text = AppConstants.NETWORK_STATISTICS_TEXT.format(
            total_assets=metrics.get("total_assets", 0),
            total_relationships=metrics.get("total_relationships", 0),
            average_relationship_strength=metrics.get(
                "average_relationship_strength", 0.0
            ),
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
    def update_asset_info(selected_asset: Optional[str], graph: AssetRelationshipGraph) -> tuple[dict, dict]:
        """
        Return detailed information for a selected asset formatted for UI display.

        Parameters:
                selected_asset (Optional[str]): Asset identifier to look up; if `None` or not present in
                        `graph.assets` the function returns empty structures.
                graph (AssetRelationshipGraph): Asset relationship graph containing asset
                        objects and relationships.

        Returns:
                tuple[dict, dict]: A pair where the first element is `asset_dict` — a dictionary
                representation of the asset with its `asset_class` converted to the enum's
                value — and the second element is a relationships dictionary with keys
                `"outgoing"` and `"incoming"`. Each of those maps counterpart asset IDs to a
                dict containing `relationship_type` and `strength`. If the asset is not found,
                returns `{}` and `{"outgoing": {}, "incoming": {}}`.
        """
        if not selected_asset or selected_asset not in graph.assets:
            return {}, {"outgoing": {}, "incoming": {}}

        asset: Asset = graph.assets[selected_asset]
        asset_dict = asdict(asset)
        asset_dict["asset_class"] = asset.asset_class.value

        outgoing: dict[str, dict[str, Any]] = {
            target_id: {"relationship_type": rel_type, "strength": strength}
            for target_id, rel_type, strength in graph.relationships.get(
                selected_asset, []
            )
        }

        # If you later add graph.incoming_relationships, this will pick it up.
        incoming_relationships = getattr(graph, "incoming_relationships", {})
        incoming: dict[str, dict[str, Any]] = {
            src_id: {"relationship_type": rel_type, "strength": strength}
            for src_id, rel_type, strength in incoming_relationships.get(
                selected_asset, []
            )
        }

        return asset_dict, {"outgoing": outgoing, "incoming": incoming}

    def update_all_metrics_outputs(
        self,
        graph: AssetRelationshipGraph,
    ) -> tuple[go.Figure, go.Figure, go.Figure, str]:
        """
        Create three metric visualization figures and a formatted network
        statistics text summary for the given graph.

        Returns:
            tuple: A 4-tuple containing:
                - fig1 (plotly.graph_objects.Figure):
                    First metric visualization (asset distribution).
                - fig2 (plotly.graph_objects.Figure):
                    Second metric visualization (relationship types
                    or timeline).
                - fig3 (plotly.graph_objects.Figure):
                    Third metric visualization (additional metric comparison).
                - metrics_text (str):
                    Human-readable network statistics and
                    top-relationships summary.
        """
        fig1, fig2, fig3 = visualize_metrics(graph)
        metrics_text = self._update_metrics_text(graph)
        return fig1, fig2, fig3, metrics_text
    def refresh_all_outputs(
        self, graph_state: AssetRelationshipGraph
    ) -> tuple[Any, ...]:
        """
        Refresh all UI outputs: 3D visualization, metric figures and text,
        schema report, and asset selector options.

        Returns:
            tuple[Any, ...]: Ordered outputs for the Gradio UI:
                - 3D visualization figure
                - metric figure 1
                - metric figure 2
                - metric figure 3
                - formatted metrics text
                - schema report (string or markdown)
                - Gradio update for the asset selector (choices list, value reset)
                - Gradio update for the error message (hidden on success)
            On error, returns a tuple of Gradio update objects where visual outputs are empty
            updates, the asset selector is updated with an empty choices list, and the final
            update contains a visible error message describing the failure.
        """
        try:
            graph = self.ensure_graph()
            logger.info("Refreshing all visualization outputs")

            viz_3d = visualize_3d_graph(graph)
            f1, f2, f3, metrics_txt = self.update_all_metrics_outputs(graph)
            schema_rpt = generate_schema_report(graph)

            asset_choices = list(graph.assets.keys())
            logger.info(
                "Successfully refreshed outputs for %s assets", len(asset_choices)
            )

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
    ) -> tuple[go.Figure, gr.Update]:
        """
        Refresh the graph visualization according to the selected view mode and
        relationship filters.

        Parameters:
            view_mode (str): Either "2D" to produce a 2D layout or any other
                value to produce a 3D visualization.
            layout_type (str): Layout algorithm identifier used for 2D rendering.
            toggle_arrows (bool): When true (3D mode), show directional arrows on
                relationship edges.
            show_same_sector (bool): Include same-sector relationships when true.
            show_market_cap (bool): Include market-cap-based relationships when
                true.
            show_correlation (bool): Include correlation-based relationships when
                true.
            show_corporate_bond (bool): Include corporate-bond relationships when
                true.
            show_commodity_currency (bool): Include commodity/currency
                relationships when true.
            show_income_comparison (bool): Include income-comparison
                relationships when true.
            show_regulatory (bool): Include regulatory-event relationships when
                true.
            show_all_relationships (bool): When true, ignore selective filters and
                show all relationship types.
            graph_state (AssetRelationshipGraph): Current graph state (used to
                ensure graph is initialized).

        Returns:
            tuple[go.Figure, gr.Update]: A tuple with the generated Plotly figure
                for the visualization and a Gradio update object controlling the
                error message visibility/value (`visible=False` on success;
                contains an error string and `visible=True` on failure).
        """
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

            return graph_viz, gr.update(visible=False)

        except Exception as exc:
            logger.error("Error refreshing visualization: %s", exc)
            empty_fig = go.Figure()
            error_msg = f"Error refreshing visualization: {exc}"
            return empty_fig, gr.update(value=error_msg, visible=True)

    def generate_formulaic_analysis(self, graph_state: AssetRelationshipGraph) -> tuple[Any, ...]:
        """
        Run formulaic analysis on the current asset graph and prepare
        visualization and UI updates.

        Parameters:
            graph_state (AssetRelationshipGraph): Current graph or
                graph-containing state used for analysis.

        Returns:
            tuple[Any, ...]: A 6-tuple containing:
                - dashboard_fig (go.Figure): Overview dashboard visualizing
                    formulaic results.
                - correlation_network_fig (go.Figure): Network figure showing
                    empirical correlations between metrics.
                - metric_comparison_fig (go.Figure): Chart comparing metrics
                    produced by the analysis.
                - formula_choices_update (gr.Update): UI update setting
                    available formula choices and the selected value.
                - summary_text (str): Human-readable summary of the formulaic
                    analysis findings.
                - error_visibility_update (gr.Update): UI update controlling
                    visibility/state of the error message.

        On failure, returns three empty figures, an empty choices update, an
        error message string in place of the summary, and an update that
        makes the error message visible.
        """
        try:
            logger.info("Generating formulaic analysis")
            graph = self.ensure_graph()

            formulaic_analyzer = FormulaicAnalyzer()
            formulaic_visualizer = FormulaicVisualizer()

            analysis_results = formulaic_analyzer.analyze_graph(graph)

            dashboard_fig = formulaic_visualizer.create_formula_dashboard(
                analysis_results
            )
            correlation_network_fig = formulaic_visualizer.create_correlation_network(
                analysis_results.get("empirical_relationships", {})
            )
            metric_comparison_fig = formulaic_visualizer.create_metric_comparison_chart(
                analysis_results
            )

            formulas = analysis_results.get("formulas", [])
            formula_choices = (
                [f.name for f in formulas] if isinstance(formulas, list) else []
            )

            summary = analysis_results.get("summary", {})
            summary_text = self._format_formula_summary(summary, analysis_results)

            logger.info(
                "Generated formulaic analysis with %d formulas", len(formula_choices)
            )
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
    def show_formula_details(formula_name: str, graph_state: AssetRelationshipGraph) -> tuple[go.Figure, gr.Update]:
        """
        Display a detailed visualization for the selected formula and the UI
        update for the detail panel.

        Parameters:
            formula_name (str): Name of the formula to display details for.
            graph_state (AssetRelationshipGraph): Current asset relationship graph state used to derive formula details.

        Returns:
            tuple[go.Figure, gr.Update]: A Plotly Figure containing the formula detail
            visualization and a Gradio Update controlling the detail panel (e.g.,
            value and visibility). If an error occurs, the returned Update contains
            an error message and makes the panel visible.
        """
        try:
            # Placeholder implementation
            return go.Figure(), gr.update(value=None, visible=False)
        except Exception as exc:
            logger.error("Error showing formula details: %s", exc)
            return go.Figure(), gr.update(value=f"Error: {exc}", visible=True)

    @staticmethod
    def _format_formula_summary(summary: dict[str, Any], analysis_results: dict[str, Any]) -> str:
        """
        Assemble a human-readable multiline summary of formulaic analysis for display.

        Parameters:
            summary (dict[str, Any]): Summary metadata, typically including
                - "formula_categories": mapping of category name to count
                - "key_insights": list of short insight strings
            analysis_results (dict[str, Any]): Full analysis results, expected to contain
                an "empirical_relationships" mapping which may include
                "strongest_correlations" as a list of correlation records

        Returns:
            str: A formatted multiline summary containing category counts, a
            "Key Insights" section, and up to three strongest asset correlations
            when available.
        """
        empirical = analysis_results.get("empirical_relationships", {})

        summary_lines: list[str] = []

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
                        summary_lines.append(
                            f"  • {pair}: {float(correlation):.3f} ({strength})"
                        )
                    except (TypeError, ValueError):
                        summary_lines.append(f"  • {pair}: n/a ({strength})")

        return "\n".join(summary_lines)

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
                                label="Same Sector (↔)", value=True
                            )
                            show_market_cap = gr.Checkbox(
                                label="Market Cap Similar (↔)", value=True
                            )
                            show_correlation = gr.Checkbox(
                                label="Correlation (↔)", value=True
                            )
                        with gr.Column(scale=1):
                            show_corporate_bond = gr.Checkbox(
                                label="Corporate Bond → Equity (→)", value=True
                            )
                            show_commodity_currency = gr.Checkbox(
                                label="Commodity ↔ Currency", value=True
                            )
                            show_income_comparison = gr.Checkbox(
                                label="Income Comparison (↔)", value=True
                            )
                        with gr.Column(scale=1):
                            show_regulatory = gr.Checkbox(
                                label="Regulatory Impact (→)", value=True
                            )
                            show_all_relationships = gr.Checkbox(
                                label="Show All Relationships", value=True
                            )
                            toggle_arrows = gr.Checkbox(
                                label="Show Direction Arrows", value=True
                            )

                    with gr.Row():
                        visualization_3d = gr.Plot()
                    with gr.Row():
                        with gr.Column(scale=1):
                            refresh_viz_btn = gr.Button(
                                AppConstants.REFRESH_BUTTON_LABEL, variant="primary"
                            )
                        with gr.Column(scale=1):
                            reset_view_btn = gr.Button(
                                "Reset View & Show All", variant="secondary"
                            )
                        with gr.Column(scale=2):
                            gr.Markdown(
                                "**Legend:** ↔ = Bidirectional, → = Unidirectional"
                            )

                with gr.Tab(AppConstants.TAB_METRICS_ANALYTICS):
                    gr.Markdown(AppConstants.NETWORK_METRICS_ANALYSIS_MD)
                    with gr.Row():
                        asset_dist_chart = gr.Plot()
                        rel_types_chart = gr.Plot()
                    with gr.Row():
                        events_timeline_chart = gr.Plot()
                    with gr.Row():
                        metrics_text = gr.Textbox(
                            label=AppConstants.NETWORK_STATISTICS_LABEL,
                            lines=10,
                            interactive=False,
                        )
                    with gr.Row():
                        refresh_metrics_btn = gr.Button(
                            AppConstants.REFRESH_BUTTON_LABEL, variant="primary"
                        )

                with gr.Tab(AppConstants.TAB_SCHEMA_RULES):
                    gr.Markdown(AppConstants.SCHEMA_RULES_GUIDE_MD)
                    with gr.Row():
                        schema_report = gr.Textbox(
                            label=AppConstants.SCHEMA_REPORT_LABEL,
                            lines=25,
                            interactive=False,
                        )
                    with gr.Row():
                        refresh_schema_btn = gr.Button(
                            AppConstants.GENERATE_SCHEMA_BUTTON_LABEL, variant="primary"
                        )

                with gr.Tab(AppConstants.TAB_ASSET_EXPLORER):
                    gr.Markdown(AppConstants.DETAILED_ASSET_INFO_MD)
                    with gr.Row():
                        with gr.Column(scale=1):
                            asset_selector = gr.Dropdown(
                                label=AppConstants.SELECT_ASSET_LABEL,
                                choices=[],
                                interactive=True,
                            )
                        with gr.Column(scale=3):
                            gr.Markdown("")
                    with gr.Row():
                        asset_info = gr.JSON(label=AppConstants.ASSET_DETAILS_LABEL)
                    with gr.Row():
                        asset_relationships = gr.JSON(
                            label=AppConstants.RELATED_ASSETS_LABEL
                        )
                    with gr.Row():
                        refresh_explorer_btn = gr.Button(
                            AppConstants.REFRESH_BUTTON_LABEL, variant="primary"
                        )

                with gr.Tab(AppConstants.TAB_DOCUMENTATION):
                    gr.Markdown(AppConstants.DOC_MARKDOWN)

                with gr.Tab("📊 Formulaic Analysis"):
                    gr.Markdown(
                        "## Mathematical Relationships & Formulas\n\n"
                        "This section extracts and visualizes\n"
                        "mathematical formulas and relationships\n"
                        "between financial variables.\n"
                        "It includes fundamental financial ratios,\n"
                        "correlation patterns,\n"
                        "valuation models,\n"
                        "and empirical relationships derived\n"
                        "from the asset database."
                    )

                    with gr.Row():
                        with gr.Column(scale=2):
                            formulaic_dashboard = gr.Plot(
                                label="Formulaic Analysis Dashboard"
                            )
                        with gr.Column(scale=1):
                            formula_selector = gr.Dropdown(
                                label="Select Formula for Details",
                                choices=[],
                                value=None,
                                interactive=True,
                            )
                            formula_detail_view = gr.Plot(label="Formula Details")

                    with gr.Row():
                        with gr.Column(scale=1):
                            correlation_network = gr.Plot(
                                label="Asset Correlation Network"
                            )
                        with gr.Column(scale=1):
                            metric_comparison = gr.Plot(label="Metric Comparison Chart")

                    with gr.Row():
                        with gr.Column(scale=1):
                            refresh_formulas_btn = gr.Button(
                                "🔄 Refresh Formulaic Analysis", variant="primary"
                            )
                        with gr.Column(scale=2):
                            formula_summary = gr.Textbox(
                                label="Formula Analysis Summary",
                                lines=5,
                                interactive=False,
                            )

            # Keep a non-null graph in state to avoid Optional pitfalls.
            graph_state = gr.State(value=self.ensure_graph())

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

            refresh_buttons = [
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

            refresh_viz_btn.click(
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

            formulaic_outputs = [
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
                    outputs=[visualization_3d, error_message],
                )

            layout_type.change(
                self.refresh_visualization,
                inputs=visualization_inputs,
                outputs=[visualization_3d, error_message],
            )

            reset_view_btn.click(
                lambda graph_state, view_mode, layout_type: self.refresh_visualization(
                    graph_state,
                    view_mode,
                    layout_type,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                ),
                inputs=[graph_state, view_mode, layout_type],
                outputs=[visualization_3d, error_message],
            )

            asset_selector.change(
                self.update_asset_info,
                inputs=[asset_selector, graph_state],
                outputs=[asset_info, asset_relationships],
            )

            interface.load(
                self.refresh_all_outputs,
                inputs=[graph_state],
                outputs=all_refresh_outputs,
            )

        return interface


if __name__ == "__main__":
    try:
        logger.info(AppConstants.APP_START_INFO)
        app = FinancialAssetApp()
        demo = app.create_interface()
        logger.info(AppConstants.APP_LAUNCH_INFO)
        demo.launch()
    except Exception as exc:
        logger.error("%s: %s", AppConstants.APP_START_ERROR, exc)
