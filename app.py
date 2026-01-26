import json
import logging
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple, Union

import gradio as gr
import plotly.graph_objects as go

from src.analysis.formulaic_analysis import FormulaicAnalyzer
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
LOGGER = logging.getLogger(__name__)


class AppConstants:
    """Holds all application constants including labels, markdown, and messages."""

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

    INITIAL_GRAPH_ERROR: str = "Failed to create sample database"
    REFRESH_OUTPUTS_ERROR: str = "Error refreshing outputs"
    APP_START_INFO: str = "Starting Financial Asset Relationship Database application"
    APP_LAUNCH_INFO: str = "Launching Gradio interface"
    APP_START_ERROR: str = "Failed to start application"

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


class FinancialAssetApp:
    """Main application class for the Financial Asset Relationship Database."""

    graph: Optional[AssetRelationshipGraph]

    def __init__(self) -> None:
        """Initialize the application and its asset graph."""
        self.graph = None
        self._initialize_graph()

    def _initialize_graph(self) -> None:
        """
        Builds and assigns the asset relationship graph from real financial data.

        Attempts to initialize the application's asset graph by loading real
        financial data via create_real_database and storing the result on
        self.graph. If initialization fails, the original exception is
        propagated.
        """
        try:
            LOGGER.info("Initializing with real financial data from Yahoo Finance")
            self.graph = create_real_database()
            LOGGER.info(
                "Database initialized with %s real assets", len(self.graph.assets)
            )
        except Exception as e:
            LOGGER.error("%s: %s", AppConstants.INITIAL_GRAPH_ERROR, e)
            raise

    def ensure_graph(self) -> AssetRelationshipGraph:
        """
        Ensure the application's asset relationship graph is initialized.

        Returns:
            AssetRelationshipGraph: The initialized asset relationship graph.

        Raises:
            RuntimeError: If initialization fails and the graph remains None.
        """
        if self.graph is None:
            LOGGER.warning("Graph is None, re-initializing with real financial data.")
            self._initialize_graph()
            if self.graph is None:
                # Critical invariant: graph must not be None after initialization.
                raise RuntimeError("Asset graph initialization failed: graph is None")
        assert self.graph is not None
        return self.graph

    @staticmethod
    def _update_metrics_text(graph: AssetRelationshipGraph) -> str:
        """
        Format network statistics and top relationships from the asset graph into
        a human-readable text block.

        The output includes total assets, total relationships,
        average relationship strength, relationship density, regulatory event count,
        a JSON-formatted asset class distribution,
        and a numbered list of top relationships
        with their relationship type and strength.

        Returns:
            str: Formatted metrics text ready for display.
        """
        metrics: RelationshipMetrics = graph.calculate_metrics()
        text: str = AppConstants.NETWORK_STATISTICS_TEXT.format(
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
        """
        Generate metric visualizations and the formatted network metrics text
        for the given asset graph.

        Parameters:
            graph (AssetRelationshipGraph): The asset relationship graph used to compute
                metrics and visualizations.

        Returns:
            Tuple[go.Figure, go.Figure, go.Figure, str]: A tuple containing three Plotly
                figures (metric visualizations) and a string with the formatted network
                metrics report.
        """
        f1, f2, f3 = visualize_metrics(graph)
        text: str = self._update_metrics_text(graph)
        return f1, f2, f3, text

    @staticmethod
    def update_asset_info(
        selected_asset: Optional[str], graph: AssetRelationshipGraph
    ) -> Tuple[
        Dict[str, Union[str, float, int]],
        Dict[str, Dict[str, Dict[str, Union[str, float]]]],
    ]:
        """
        Return detailed information and related relationships
        for the specified asset.

        Parameters:
            selected_asset (Optional[str]): Asset identifier to look up
                in `graph.assets`.
                If `None` or not present,
                no asset is returned.
            graph (AssetRelationshipGraph): Graph containing assets
                and their relationships.

        Returns:
            Tuple[
                Dict[str, Union[str, float, int]],
                Dict[str, Dict[str, Dict[str, Union[str, float]]]],
            ]:
                - First element: a dictionary of the asset's fields
                  (converted from the dataclass)
                  with an added `"asset_class"` key
                  containing the asset class value.
                - Second element: an AssetRelationshipView with two keys,
                  `"outgoing"` and `"incoming"`,
                  each mapping counterparty asset ids to
                  dictionaries of the form
                  `{`"relationship_type"`: <str>, `"strength"`: <float>}`.
                  If the asset is missing, returns an empty dict
                  and `{`"outgoing"`: {}, `"incoming"`: {}}`.
        """
        if not selected_asset or selected_asset not in graph.assets:
            return {}, {"outgoing": {}, "incoming": {}}
        asset: Asset = graph.assets[selected_asset]
        asset_dict: Dict[str, Union[str, float, int]] = asdict(asset)
        asset_dict["asset_class"] = asset.asset_class.value

        outgoing: Dict[str, Dict[str, Union[str, float]]] = {
            target_id: {"relationship_type": rel_type, "strength": strength}
            for target_id, rel_type, strength in graph.relationships.get(
                selected_asset, []
            )
        }

        incoming: Dict[str, Dict[str, Union[str, float]]] = {
            src_id: {"relationship_type": rel_type, "strength": strength}
            for src_id, rel_type, strength in graph.incoming_relationships.get(
                selected_asset, []
            )
        }
        return asset_dict, {"outgoing": outgoing, "incoming": incoming}

    def refresh_all_outputs(
        self, graph_state: AssetRelationshipGraph
    ) -> Tuple[
        gr.Plot,
        gr.Plot,
        gr.Plot,
        gr.Plot,
        gr.Textbox,
        gr.Textbox,
        gr.Dropdown,
        gr.Textbox,
    ]:
        """
        Refreshes all UI visuals, metrics, schema report,
        and asset selector options.

        @returns Tuple containing:
            - 3D network visualization figure for the main plot.
            - Metric figure 1 (Plotly figure) for metrics visualization.
            - Metric figure 2 (Plotly figure) for metrics visualization.
            - Metric figure 3 (Plotly figure) for metrics visualization.
            - Metrics text report (string) summarizing network statistics.
            - Schema report text (string)
              describing the current graph schema and rules.
            - Updated asset dropdown state with available asset choices
              and no selection.
            - Error textbox state (hidden when successful,
              visible with an error message when refresh fails).
        """
        try:
            graph = self.ensure_graph()
            LOGGER.info("Refreshing all visualization outputs")

            viz_3d: go.Figure = visualize_3d_graph(graph)
            f1, f2, f3, metrics_txt = self.update_all_metrics_outputs(graph)
            schema_rpt: str = generate_schema_report(graph)
            asset_choices: List[str] = list(graph.assets.keys())

            LOGGER.info(
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

        except Exception as e:
            LOGGER.error("%s: %s", AppConstants.REFRESH_OUTPUTS_ERROR, e)
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
    ) -> go.Figure:
        """
        Generate a network visualization of the asset relationship graph with optional
        2D/3D mode and relationship filters.

        The visualization respects the supplied view mode (e.g., "2D" for planar
        layouts; any other value selects the 3D renderer) and applies boolean filter
        flags to control which relationship types and node attributes are shown.

        Returns:
            A Plotly Figure containing the requested visualization. Returns an empty
            Figure if visualization fails.
        """
        try:
            LOGGER.info("Refreshing network visualization")
            graph = self.ensure_graph() if graph_state is None else graph_state

            if view_mode == "2D":
                graph_viz: go.Figure = visualize_2d_graph(
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

        except Exception as e:
            LOGGER.error("Error refreshing visualization: %s", e)
            return go.Figure()

    def generate_formulaic_analysis(
        self, graph_state: Optional[AssetRelationshipGraph]
    ) -> Tuple[go.Figure, go.Figure, go.Figure, gr.Dropdown, str, gr.Textbox]:
        """
        Produce a formulaic analysis dashboard and companion visualizations
        derived from the asset graph.

        Parameters:
            graph_state (Optional[AssetRelationshipGraph]): Asset graph to analyze; if
                None, the app's initialized graph is used.

        Returns:
            Tuple containing:
            - dashboard_fig (go.Figure): Main formula dashboard summarizing identified
                formulas and metrics.
            - correlation_network_fig (go.Figure): Network figure showing empirical
                relationships and correlations between assets/metrics.
            - metric_comparison_fig (go.Figure): Figure comparing metrics used by the
                discovered formulas.
            - formula_selector_update (gr.Dropdown): Gradio update for the formula
                selector populated with discovered formula names (selected value set to
                the first formula when available, otherwise cleared).
            - summary_text (str): Human-readable summary of the formulaic analysis
                and key insights.
            - error_textbox_update (gr.Textbox): Gradio update for the error textbox
                (hidden on success; when an error occurs contains the error message and
                is visible).
        """
        try:
            LOGGER.info("Generating formulaic analysis")
            graph: AssetRelationshipGraph = (
                self.ensure_graph() if graph_state is None else graph_state
            )

            formulaic_visualizer: FormulaicVisualizer = FormulaicVisualizer()

            analysis_results: Dict = formulaic_analyzer.analyze_graph(graph)

            dashboard_fig: go.Figure = formulaic_visualizer.create_formula_dashboard(
                analysis_results
            )

            correlation_network_fig: go.Figure = (
                formulaic_visualizer.create_correlation_network(
                    analysis_results.get("empirical_relationships", {})
                )
            )

            metric_comparison_fig: go.Figure = (
                formulaic_visualizer.create_metric_comparison_chart(analysis_results)
            )

            formulas: List = analysis_results.get("formulas", [])
            formula_choices: List[str] = [f.name for f in formulas]

            summary: Dict = analysis_results.get("summary", {})
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

        except Exception as e:
            LOGGER.error("Error generating formulaic analysis: %s", e)
            empty_fig: go.Figure = go.Figure()
            error_msg: str = f"Error generating formulaic analysis: {str(e)}"
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
        formula_name: str, graph_state: AssetRelationshipGraph
    ) -> Tuple[go.Figure, gr.Textbox]:
        """
        Provide a placeholder detail view for a selected formula
        and hide the detail textbox while the feature is not implemented.

        Parameters:
            formula_name (str):
                The name of the formula whose details would be shown.
            graph_state (AssetRelationshipGraph):
                The current asset relationship graph used for analysis.

        Returns:
            Tuple[go.Figure, gr.Textbox]:
                A pair where the first element is an empty Plotly Figure as a
                placeholder, and the second is a Gradio textbox update
                with no value and visibility set to False.
        """
        LOGGER.warning("Formula detail view is not yet implemented.")
        return go.Figure(), gr.update(value=None, visible=False)

    @staticmethod
    def _format_formula_summary(summary: Dict, analysis_results: Dict) -> str:
        """
        Builds a human-readable, markdown-formatted summary of formulaic analysis
        and empirical relationships.

        Parameters:
            summary (Dict): Aggregated summary metrics with keys such as
                - "avg_r_squared" (float): average R² across formulas,
                - "empirical_data_points" (int): number of empirical observations,
                - "formula_categories" (Dict[str, int]): counts per category,
                - "key_insights" (List[str]): notable insights to highlight.
            analysis_results (Dict): Detailed analysis payload containing at least
                - "formulas" (List): list of discovered formulas,
                - "empirical_relationships" (Dict): empirical data including
                  "strongest_correlations" (List[Dict]) where each dict has keys
                  "pair", "correlation", and "strength".

        Returns:
            str: A multi-line markdown string summarizing totals, average reliability,
                 empirical data points, categorized formula counts, key insights, and
                 top asset correlations suitable for display in the UI.
        """
        formulas: List = analysis_results.get("formulas", [])
        empirical: Dict = analysis_results.get("empirical_relationships", {})

        summary_lines: List[str] = [
            "🔍 **Formulaic Analysis Summary**",
            "",
            f"📊 **Total Formulas Identified:** {len(formulas)}",
            f"📈 **Average Reliability (R²):** {summary.get('avg_r_squared', 0):.3f}",
            f"🔗 **Empirical Data Points:** {summary.get('empirical_data_points', 0)}",
        ]

        # Add formula categories, if available
        formula_categories: Optional[Dict] = summary.get("formula_categories")
        if formula_categories:
            summary_lines.extend(
                [
                    "",
                    "## 🧮 Formula Categories",
                ]
            )
            for category, count in formula_categories.items():
                summary_lines.append(f"- **{category}**: {count}")

        # Add key insights, if available
        key_insights: Optional[List[str]] = summary.get("key_insights")
        if key_insights:
            summary_lines.extend(
                [
                    "",
                    "## 💡 Key Insights",
                ]
            )
            for idx, insight in enumerate(key_insights, start=1):
                summary_lines.append(f"{idx}. {insight}")

        # Add top empirical correlations, if available
        strongest_correlations: List[Dict] = empirical.get("strongest_correlations", [])
        if strongest_correlations:
            summary_lines.extend(
                [
                    "",
                    "## 🔗 Top Empirical Asset Correlations",
                ]
            )
            for item in strongest_correlations:
                pair = item.get("pair")
                correlation = item.get("correlation")
                strength = item.get("strength")
                if pair is None or correlation is None:
                    continue
                summary_lines.append(
                    f"- **{pair}**: correlation={correlation:.3f}, strength={strength}"
                )

        return "\n".join(summary_lines)

    def create_interface(self) -> gr.Blocks:
        """
        Builds the Gradio Blocks user interface for the
        Financial Asset Relationship Database application.

        Creates a multi-tab UI containing:
        - Network Visualization (2D/3D) with visualization controls,
          relationship visibility toggles, a 3D/2D plot, and
          refresh/reset actions.
        - Metrics & Analytics with metric charts
          and a network statistics textbox.
        - Schema & Rules with a generated schema report and
          refresh action.
        - Asset Explorer with an asset selector,
          asset details and related-assets JSON views,
          and refresh action.
        - Documentation with static markdown.
        - Formulaic Analysis with a dashboard,
          formula selector, detail view,
          correlation network, metric comparison chart, and summary.

        Event handlers and state:
        - Initializes a gr.State holding the application's graph.
        - Wires refresh buttons, visualization controls, layout selection, and
          formula-related controls to the corresponding FinancialAssetApp methods
          so UI components update based on the current graph state.
        - Provides an error message textbox that is updated by
          event handlers.

        Returns:
            demo_ui (gr.Blocks): The constructed Gradio Blocks instance
                representing the complete application UI.
        """
        demo_ui: gr.Blocks = gr.Blocks(title=AppConstants.TITLE)

        with demo_ui:
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

                    # Visualization mode controls
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

                    # Relationship visibility controls
                    with gr.Row():
                        gr.Markdown("### 🔗 Relationship Visibility Controls")
                    with gr.Row():
                        with gr.Column(scale=1):
                            show_same_sector: gr.Checkbox = gr.Checkbox(
                                label="Same Sector (↔)", value=True
                            )
                            show_market_cap: gr.Checkbox = gr.Checkbox(
                                label="Market Cap Similar (↔)", value=True
                            )
                            show_correlation: gr.Checkbox = gr.Checkbox(
                                label="Correlation (↔)", value=True
                            )
                        with gr.Column(scale=1):
                            show_corporate_bond: gr.Checkbox = gr.Checkbox(
                                label="Corporate Bond → Equity (→)", value=True
                            )
                            show_commodity_currency: gr.Checkbox = gr.Checkbox(
                                label="Commodity ↔ Currency", value=True
                            )
                            show_income_comparison: gr.Checkbox = gr.Checkbox(
                                label="Income Comparison (↔)", value=True
                            )
                        with gr.Column(scale=1):
                            show_regulatory: gr.Checkbox = gr.Checkbox(
                                label="Regulatory Impact (→)", value=True
                            )
                            show_all_relationships: gr.Checkbox = gr.Checkbox(
                                label="Show All Relationships", value=True
                            )
                            toggle_arrows: gr.Checkbox = gr.Checkbox(
                                label="Show Direction Arrows", value=True
                            )

                    with gr.Row():
                        visualization_3d: gr.Plot = gr.Plot()
                    with gr.Row():
                        with gr.Column(scale=1):
                            refresh_btn: gr.Button = gr.Button(
                                AppConstants.REFRESH_BUTTON_LABEL, variant="primary"
                            )
                        with gr.Column(scale=1):
                            reset_view_btn: gr.Button = gr.Button(
                                "Reset View & Show All", variant="secondary"
                            )
                        with gr.Column(scale=2):
                            gr.Markdown(
                                "**Legend:** ↔ = Bidirectional, → = Unidirectional"
                            )

                # Metrics & Analytics Tab
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
                        refresh_metrics_btn: gr.Button = gr.Button(
                            AppConstants.REFRESH_BUTTON_LABEL, variant="primary"
                        )

                # Schema & Rules Tab
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

                # Asset Explorer Tab
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
                        gr.JSON(label=AppConstants.ASSET_DETAILS_LABEL)
                    with gr.Row():
                        asset_relationships: gr.JSON = gr.JSON(
                            label=AppConstants.RELATED_ASSETS_LABEL
                        )
                    with gr.Row():
                        refresh_explorer_btn: gr.Button = gr.Button(
                            AppConstants.REFRESH_BUTTON_LABEL, variant="primary"
                        )

                # Documentation Tab
                with gr.Tab(AppConstants.TAB_DOCUMENTATION):
                    gr.Markdown(AppConstants.DOC_MARKDOWN)

                # Formulaic Analysis Tab
                with gr.Tab("📊 Formulaic Analysis"):
                    gr.Markdown(
                        """
                        # Mathematical Relationships & Formulas

                        This section extracts and visualizes mathematical
                        formulas and relationships between financial variables.
                        It includes fundamental financial ratios,
                        correlation patterns, valuation models, and empirical
                        relationships derived from the asset database.
                        """
                    )

                    with gr.Row():
                        with gr.Column(scale=2):
                            formulaic_dashboard: gr.Plot = gr.Plot(
                                label="Formulaic Analysis Dashboard"
                            )
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
                            correlation_network: gr.Plot = gr.Plot(
                                label="Asset Correlation Network"
                            )
                        with gr.Column(scale=1):
                            metric_comparison: gr.Plot = gr.Plot(
                                label="Metric Comparison Chart"
                            )

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

            # State object for the graph
            graph_state: gr.State = gr.State(value=self.graph)

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

            refresh_buttons = [
                refresh_metrics_btn,
                refresh_schema_btn,
                refresh_explorer_btn,
                refresh_btn,
            ]

            for btn in refresh_buttons:
                btn.click(
                    self.refresh_all_outputs,
                    inputs=[graph_state],
                    outputs=all_refresh_outputs,
                )

            # Visualization checkbox inputs
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

            # Wire checkboxes and layout type to visualization refresh
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

            layout_type.change(
                self.refresh_visualization,
                inputs=visualization_inputs,
                outputs=visualization_outputs,
            )

            # Reset view button
            reset_view_btn.click(
                lambda *args: self.refresh_visualization(*args),
                inputs=visualization_inputs,
                outputs=visualization_outputs,
            )

            # Formulaic analysis handlers
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

        return demo


if __name__ == "__main__":
    try:
        LOGGER.info(AppConstants.APP_START_INFO)
        app: FinancialAssetApp = FinancialAssetApp()
        demo: gr.Blocks = app.create_interface()
        LOGGER.info(AppConstants.APP_LAUNCH_INFO)
        demo.launch()
    except Exception as e:
        LOGGER.error("%s: %s", AppConstants.APP_START_ERROR, e)
