"""Main Gradio application entrypoint for asset relationship analysis."""

# pylint: disable=import-error

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any, Optional

import gradio as gr  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
import plotly.graph_objects as go  # type: ignore[import-untyped]

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
    """Holds constants for app configuration.

    Defines titles, tab names, labels, and default messages for the
    Financial Asset Relationship Database
    visualization application.
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
    """Main application class for managing
    financial asset relationship graph.

    Initializes and maintains the AssetRelationshipGraph.
    Also offers functionality for analyzing and reporting on asset
    relationships.
    """

    def __init__(self) -> None:
        """
        Initialize the FinancialAssetApp and create its initial AssetRelationshipGraph.

        Sets self.graph and invokes the internal initializer to populate the graph; this may raise an exception if graph creation or validation fails.
        """
        self.graph: AssetRelationshipGraph | None = None
        self._initialize_graph()

    @staticmethod
    def _create_database() -> AssetRelationshipGraph:
        """
        Locate and invoke a factory in src.data.real_data_fetcher to construct an AssetRelationshipGraph.

        Probes a fixed list of candidate factory function names and calls the first callable found to obtain the graph.

        Returns:
            AssetRelationshipGraph: The constructed asset relationship graph.

        Raises:
            TypeError: If a discovered factory is callable but returns a value that does not expose an `assets` attribute.
            AttributeError: If none of the expected factory functions exist in src.data.real_data_fetcher.
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
                if not hasattr(graph, "assets"):
                    raise TypeError(f"{name}() returned {type(graph)!r}, expected AssetRelationshipGraph")
                return graph
        tried_candidates = ", ".join(candidates)
        raise AttributeError(
            f"No known database factory found in src.data.real_data_fetcher. Tried: {tried_candidates}"
        )

    def _initialize_graph(self) -> None:
        """
        Initialize the application's asset relationship graph and assign it to self.graph.

        Raises:
            Exception: Propagated if graph creation or validation fails.
        """
        try:
            logger.info("Initializing financial data graph")
            self.graph = self._create_database()
            logger.info("Database initialized with %s assets", len(self.graph.assets))
        except Exception as exc:
            logger.error("%s: %s", AppConstants.INITIAL_GRAPH_ERROR, exc)
            raise

    def ensure_graph(self) -> AssetRelationshipGraph:
        """
        Ensure the app has an initialized asset relationship graph and return the instance.

        If the internal graph is missing, an attempt is made to create and store a new graph before returning it.

        Returns:
            AssetRelationshipGraph: The initialized, non-None graph instance used by the app.

        Raises:
            RuntimeError: If graph initialization fails and no graph is available.
        """
        if self.graph is None:
            logger.warning("Graph is None, re-creating sample database.")
            self._initialize_graph()
        # At this point it must be non-None
        if self.graph is None:
            raise RuntimeError("Graph initialisation failed")
        return self.graph

    @staticmethod
    def _update_metrics_text(graph: AssetRelationshipGraph) -> str:
        """
        Builds a human-readable summary of network statistics for the provided asset relationship graph.

        Parameters:
            graph (AssetRelationshipGraph): Graph from which metrics are extracted and summarized.

        Returns:
            metrics_text (str): Formatted statistics summary including totals, averages, relationship density, regulatory event count, pretty-printed asset-class distribution, and a ranked list of top relationships where numeric strengths are shown as percentages and non-numeric strengths are shown as "n/a".
        """
        metrics = graph.calculate_metrics()
        text = AppConstants.NETWORK_STATISTICS_TEXT.format(
            total_assets=metrics.get("total_assets", 0),
            total_relationships=metrics.get("total_relationships", 0),
            average_relationship_strength=metrics.get(
                "average_relationship_strength",
                0.0,
            ),
            relationship_density=metrics.get("relationship_density", 0.0),
            regulatory_event_count=metrics.get("regulatory_event_count", 0),
            asset_class_distribution=json.dumps(
                metrics.get("asset_class_distribution", {}),
                indent=2,
            ),
        )

        top_rels = metrics.get("top_relationships", [])
        if not isinstance(top_rels, list):
            return text

        for idx, item in enumerate(top_rels, 1):
            parsed = FinancialAssetApp._parse_top_relationship(item)
            if parsed is None:
                continue

            s, t, rel, strength = parsed
            strength_text = FinancialAssetApp._format_relationship_strength(strength)
            text += f"{idx}. {s} → {t} ({rel}): {strength_text}\n"
        return text

    @staticmethod
    def _parse_top_relationship(
        item: Any,
    ) -> tuple[str, str, str, Any] | None:
        """
        Normalize and validate a candidate top-relationship entry.

        Parameters:
            item (Any): Expected to be a 4-element tuple (source, target, relationship_type, strength)
                where `source`, `target`, and `relationship_type` are strings.

        Returns:
            tuple[str, str, str, Any] | None: `(source, target, relationship_type, strength)` when the
            first three elements are strings and the item has exactly four elements; `None` otherwise.
        """
        if not isinstance(item, tuple) or len(item) != 4:
            return None

        source, target, relationship_type, strength = item
        if not isinstance(source, str):
            return None
        if not isinstance(target, str):
            return None
        if not isinstance(relationship_type, str):
            return None

        return source, target, relationship_type, strength

    @staticmethod
    def _format_relationship_strength(strength: Any) -> str:
        """
        Format a numeric relationship strength as a percentage string.

        Parameters:
            strength (Any): A numeric value or string representing a proportion (e.g., 0.12). Non-numeric inputs are not interpreted.

        Returns:
            str: Percentage formatted with one decimal place (for example, "12.3%"), or "n/a" if the input cannot be interpreted as a number.
        """
        try:
            return f"{float(strength):.1%}"
        except (TypeError, ValueError):
            return "n/a"

    @staticmethod
    def update_asset_info(
        selected_asset: Optional[str],
        graph: AssetRelationshipGraph,
    ) -> tuple[dict, dict]:
        """
        Provide the properties of a selected asset and its incoming and outgoing relationships.

        If `selected_asset` is None or not present in `graph.assets`, returns empty structures for both asset properties and relationships.

        Parameters:
            selected_asset (Optional[str]): Asset identifier to look up; may be None.

        Returns:
            tuple[dict, dict]:
                - First element: dictionary of the asset's attributes (fields from the Asset dataclass),
                  with `asset_class` represented as its string name.
                - Second element: dictionary with keys `outgoing` and `incoming`. Each maps related asset IDs
                  to a dictionary containing:
                    - `relationship_type`: the relationship type value
                    - `strength`: the relationship strength value
        """
        if not selected_asset or selected_asset not in graph.assets:
            return {}, {"outgoing": {}, "incoming": {}}

        asset: Asset = graph.assets[selected_asset]
        asset_dict = asdict(asset)
        asset_dict["asset_class"] = asset.asset_class.name

        outgoing: dict[str, dict[str, Any]] = {
            target_id: {"relationship_type": rel_type, "strength": strength}
            for target_id, rel_type, strength in graph.relationships.get(
                selected_asset,
                [],
            )
        }

        # If you later add graph.incoming_relationships, this will pick it up.
        incoming_relationships = getattr(graph, "incoming_relationships", {})
        incoming: dict[str, dict[str, Any]] = {
            src_id: {"relationship_type": rel_type, "strength": strength}
            for src_id, rel_type, strength in incoming_relationships.get(
                selected_asset,
                [],
            )
        }

        return asset_dict, {"outgoing": outgoing, "incoming": incoming}

    def update_all_metrics_outputs(
        self,
        graph: AssetRelationshipGraph,
    ) -> tuple[go.Figure, go.Figure, go.Figure, str]:
        """
        Create three metric visualization figures and a human-readable network statistics summary for the given asset graph.

        Returns:
            fig1 (plotly.graph_objs.Figure): First metric visualization.
            fig2 (plotly.graph_objs.Figure): Second metric visualization.
            fig3 (plotly.graph_objs.Figure): Third metric visualization.
            metrics_text (str): Formatted network statistics summary suitable for display.
        """
        fig1, fig2, fig3 = visualize_metrics(graph)
        metrics_text = self._update_metrics_text(graph)
        return fig1, fig2, fig3, metrics_text

    def refresh_all_outputs(self, _graph_state: AssetRelationshipGraph) -> tuple[Any, ...]:
        """
        Refresh all UI panels and produce the outputs expected by the Gradio interface bindings.

        Attempts to rebuild the visualization, three metric figures, metrics text, schema report, and asset selector choices; on success returns those outputs and a hidden status update, on failure returns empty/placeholder outputs and a visible error status.

        Returns:
            tuple[Any, ...]: Ordered outputs matching the Gradio bindings:
                - 3D visualization figure
                - metric figure 1
                - metric figure 2
                - metric figure 3
                - formatted metrics text (str)
                - schema report text (str)
                - Gradio update for the asset selector (choices list, value)
                - Gradio update for the refresh/error status (value, visible)
        """
        try:
            graph = self.ensure_graph()
            logger.info("Refreshing all visualization outputs")

            viz_3d = visualize_3d_graph(graph)
            f1, f2, f3, metrics_txt = self.update_all_metrics_outputs(graph)
            schema_rpt = generate_schema_report(graph)

            asset_choices = list(graph.assets.keys())
            logger.info(
                "Successfully refreshed outputs for %s assets",
                len(asset_choices),
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
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError) as exc:
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
        _graph_state: AssetRelationshipGraph,
    def refresh_visualization(
        self,
        _graph_state: AssetRelationshipGraph,
        view_mode: str,
        layout_type: str,
        show_same_sector: bool=True,
        show_market_cap: bool=True,
        show_correlation: bool=True,
        show_corporate_bond: bool=True,
        show_commodity_currency: bool=True,
        show_income_comparison: bool=True,
        show_regulatory: bool=True,
        show_all_relationships: bool=True,
        toggle_arrows: bool=True,
    ) -> tuple[go.Figure, gr.Update]:
        """Adapter for Gradio callbacks with unpacked relationship flags."""
        return self._refresh_visualization_core(
            _graph_state,
            view_mode,
            layout_type,
            (
                show_same_sector,
                show_market_cap,
                show_correlation,
                show_corporate_bond,
                show_commodity_currency,
                show_income_comparison,
                show_regulatory,
                show_all_relationships,
                toggle_arrows,
            ),
        )

    def _refresh_visualization_core(
        self,
        _graph_state: AssetRelationshipGraph,
        view_mode: str,
        layout_type: str,
        relationship_flags: tuple[bool, ...],
    ) -> tuple[go.Figure, gr.Update]:
        """
        Render the asset relationship graph using the selected view mode, layout, and relationship visibility flags.

        Parameters:
            _graph_state (AssetRelationshipGraph): The asset relationship graph to use for rendering.
            view_mode (str): View selector, e.g., "2D" for two-dimensional rendering; other values select 3D rendering.
            layout_type (str): Layout style to apply when rendering the 2D view (e.g., "spring", "circular", "grid").
            relationship_flags (tuple[bool, ...]): Variable-length tuple of boolean toggles controlling which relationship types are shown.
                Flags are interpreted in this order:
                (show_same_sector, show_market_cap, show_correlation, show_corporate_bond,
                 show_commodity_currency, show_income_comparison, show_regulatory,
                 show_all_relationships, toggle_arrows)

        Returns:
            tuple[go.Figure, gr.Update]: A Plotly Figure for the requested visualization and a Gradio Update controlling the error/message display
            (the Update is hidden when rendering succeeds and contains a visible error message when rendering fails).
        """
        try:
            graph = self.ensure_graph()
            normalized_flags = self._normalize_relationship_flags(relationship_flags)
            graph_viz = self._render_visualization(
                graph,
                view_mode,
                layout_type,
                normalized_flags,
            )

            return graph_viz, gr.update(visible=False)

        except Exception as exc:
            logger.error("Error refreshing visualization: %s", exc)
            empty_fig = go.Figure()
            error_msg = f"Error refreshing visualization: {exc}"
            return empty_fig, gr.update(value=error_msg, visible=True)

    @ staticmethod
    def _normalize_relationship_flags(
        relationship_flags: tuple[bool, ...],
    ) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool]:
        """
        Normalize a variable-length sequence of relationship flags to a nine-boolean tuple.

        Parameters:
            relationship_flags (tuple[bool, ...]): Sequence of truthy/falsy values representing relationship visibility toggles. Can be shorter or longer than nine elements and may contain non-bool truthy/falsy values.

        Returns:
            tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool]: A 9-tuple of booleans where input values are coerced to `bool`, missing entries are filled with `False`, and any extra entries beyond nine are ignored.
        """
        normalized_flags = tuple(bool(flag) for flag in relationship_flags)
        normalized_flags = (normalized_flags + (False,) * 9)[:9]
        return (
            normalized_flags[0],
            normalized_flags[1],
            normalized_flags[2],
            normalized_flags[3],
            normalized_flags[4],
            normalized_flags[5],
            normalized_flags[6],
            normalized_flags[7],
            normalized_flags[8],
        )

    @ staticmethod
    def _default_relationship_flags() -> tuple[
        bool,
        bool,
        bool,
        bool,
        bool,
        bool,
        bool,
        bool,
        bool,
    ]:
        """
        Return the default set of relationship visibility flags with all nine toggles enabled.

        Returns:
            tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool]: A 9-tuple where each element is True, representing the enabled default state for the nine relationship filter checkboxes in fixed order.
        """
        return (True, True, True, True, True, True, True, True, True)

    def _reset_visualization_view(
        self,
        graph_state: AssetRelationshipGraph,
        view_mode: str,
        layout_type: str,
    ) -> tuple[go.Figure, gr.Update]:
        """
        Refresh the visualization using all relationship visibility toggles enabled.

        Parameters:
            graph_state (AssetRelationshipGraph): Current asset relationship graph used to render the visualization.
            view_mode (str): Visualization mode, e.g. "2D" or "3D".
            layout_type (str): Layout type for 2D mode, e.g. "spring", "circular", or "grid".

        Returns:
            tuple: A pair `(figure, update)` where `figure` is the rendered Plotly figure for the network visualization and `update` is a Gradio Update object for the UI status/message.
        """
        return self._refresh_visualization_core(
            graph_state,
            view_mode,
            layout_type,
            self._default_relationship_flags(),
        )

    def _reset_visualization_and_controls(
        self,
        graph_state: AssetRelationshipGraph,
        view_mode: str,
        layout_type: str,
    ) -> tuple[Any, ...]:
        """
        Reset relationship toggle controls and refresh the visualization in one action.

        Returns:
            tuple[Any, ...]: Gradio updates for the nine relationship checkboxes,
            followed by the refreshed figure and error-message update.
        """
        default_flags = self._default_relationship_flags()
        figure, error_update=self._refresh_visualization_core(
            graph_state,
            view_mode,
            layout_type,
            default_flags,
        )
        checkbox_updates=tuple(gr.update(value=flag) for flag in default_flags)
        return (*checkbox_updates, figure, error_update)

    @ staticmethod
    def _render_visualization(
        graph: AssetRelationshipGraph,
        view_mode: str,
        layout_type: str,
        relationship_flags: tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool],
    ) -> go.Figure:
        """
        Render the asset relationship graph as either a 2D or 3D visualization applying relationship filters.

        Parameters:
            graph (AssetRelationshipGraph): The asset relationship graph to visualize.
            view_mode (str): Visualization mode, e.g., "2D" for a 2D layout; any other value selects the 3D renderer.
            layout_type (str): Layout style to use for 2D layouts (ignored by 3D renderer).
            relationship_flags (tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool]):
                Nine boolean flags controlling visible relationship types and arrow toggling, in order:
                (show_same_sector, show_market_cap, show_correlation, show_corporate_bond,
                 show_commodity_currency, show_income_comparison, show_regulatory,
                 show_all_relationships, toggle_arrows)

        Returns:
            go.Figure: A Plotly figure representing the rendered visualization.
        """
        (
            show_same_sector,
            show_market_cap,
            show_correlation,
            show_corporate_bond,
            show_commodity_currency,
            show_income_comparison,
            show_regulatory,
            show_all_relationships,
            toggle_arrows,
        ) = relationship_flags

        if view_mode == "2D":
            return visualize_2d_graph(
                graph,
                layout_type=layout_type,
                show_same_sector=show_same_sector,
                show_market_cap=show_market_cap,
                show_correlation=show_correlation,
                show_corporate_bond=show_corporate_bond,
                show_commodity_currency=show_commodity_currency,
                show_income_comparison=show_income_comparison,
                show_regulatory=show_regulatory,
                show_all_relationships=show_all_relationships,
            )

        # Default to 3D visualization for any non-"2D" view mode
        return visualize_3d_graph_with_filters(
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

    def generate_formulaic_analysis(self, _graph_state: AssetRelationshipGraph) -> tuple[Any, ...]:
        """
        Produce the visual and control outputs for the Formulaic Analysis tab.

        Returns:
            A tuple with six elements in this order:
            1. Dashboard figure (Plotly/visual object) showing formula overview.
            2. Correlation network figure representing empirical relationships.
            3. Metric comparison figure comparing derived metrics across formulas/assets.
            4. Gradio update or selection payload for the formula selector (choices and selected value).
            5. Formatted summary string describing key findings and categories.
            6. Gradio update controlling the visibility/value of the formula detail panel.
        """
        try:
            logger.info("Generating formulaic analysis")
            graph = self.ensure_graph()
            analysis_results = FormulaicAnalyzer().analyze_graph(graph)
            return self._build_formulaic_outputs(analysis_results)

        except (
            AttributeError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            logger.error("Error generating formulaic analysis: %s", exc)
            return self._build_formulaic_error_outputs(exc)

    def _build_formulaic_outputs(
        self,
        analysis_results: dict[str, Any],
    ) -> tuple[Any, ...]:
        """
        Assemble UI outputs for a successful formulaic analysis.

        Parameters:
            analysis_results (dict[str, Any]): Result object produced by the formulaic analyzer. Expected keys used here include:
                - "formulas": a list of formula objects (each with a `name` attribute) for selector choices,
                - "empirical_relationships": data for the correlation network,
                - "summary": summary metadata used to build the human-readable summary.
                Other analyzer output is passed through to the visualizer.

        Returns:
            tuple[Any, ...]: A 6-tuple containing:
                1. Dashboard figure produced for the analysis.
                2. Correlation/network figure derived from `empirical_relationships`.
                3. Metric comparison figure for the analyzed metrics.
                4. A Gradio update object configuring the formula selector choices and initial value.
                5. A formatted summary string describing key findings.
                6. A Gradio update object hiding the formula detail panel (visibility control).
        """
        formulaic_visualizer = FormulaicVisualizer()
        formula_choices = (
            [formula.name for formula in analysis_results.get("formulas", [])]
            if isinstance(analysis_results.get("formulas", []), list)
            else []
        )
        logger.info("Generated formulaic analysis with %d formulas", len(formula_choices))
        return (
            formulaic_visualizer.create_formula_dashboard(analysis_results),
            formulaic_visualizer.create_correlation_network(analysis_results.get("empirical_relationships", {})),
            formulaic_visualizer.create_metric_comparison_chart(analysis_results),
            gr.update(
                choices=formula_choices,
                value=formula_choices[0] if formula_choices else None,
            ),
            self._format_formula_summary(
                analysis_results.get("summary", {}),
                analysis_results,
            ),
            gr.update(visible=False),
        )

    @ staticmethod
    def _build_formulaic_error_outputs(exc: Exception) -> tuple[Any, ...]:
        """
        Produce fallback UI outputs used when formulaic analysis fails.

        Returns:
            tuple: A 6-tuple containing:
                - three empty Plotly figures for dashboard/correlation/metric comparison,
                - a Gradio Update setting the formula selector choices to empty and value to None,
                - an error message string describing the failure,
                - a Gradio Update that sets the error message text and makes the error visible.
        """
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

    @ staticmethod
    def show_formula_details(_formula_name: str, graph_state: AssetRelationshipGraph) -> tuple[go.Figure, gr.Update]:
        """
        Return a figure showing details for a selected formula and a Gradio update containing a status message/visibility instruction.

        Parameters:
            _formula_name (str): Name or identifier of the selected formula.
            graph_state (AssetRelationshipGraph): The graph used to derive visualization data.

        Returns:
            tuple[go.Figure, gr.Update]: A Plotly Figure for the formula detail view and a Gradio Update that sets the detail text and visibility.
        """
        try:
            # Placeholder implementation
            return (
                go.Figure(),
                gr.update(
                    value="Formula details are not available yet.",
                    visible=True,
                ),
            )
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.error("Error showing formula details: %s", exc)
            return go.Figure(), gr.update(value=f"Error: {exc}", visible=True)

    @ staticmethod
    def _format_pair(pair: Any) -> str:
        """
        Format a two-element asset pair as "A ↔ B".

        Parameters:
        	pair (Any): A value expected to be a 2-item list or tuple representing two assets.

        Returns:
        	str: A formatted string "A ↔ B" if `pair` is a list or tuple of length 2; otherwise the result of `str(pair)`.
        """
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            asset_a, asset_b=pair
            return f"{asset_a} ↔ {asset_b}"
        return str(pair)

    @ staticmethod
    def _format_correlation_value(value: Any) -> str:
        """
        Format a correlation value as a string with three decimal places.

        If the input can be converted to a float, returns that value formatted to three decimal places (e.g., "0.123"); otherwise returns str(value).

        Parameters:
            value: The correlation value to format; may be numeric or any object.

        Returns:
            A string representing the formatted correlation value or the original value converted to a string.
        """
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value)

    @ classmethod
    def _format_correlation_line(cls, corr: Any) -> str | None:
        """
        Format a correlation entry into a single human-readable line.

        Takes a correlation record (expected as a dict with keys "pair", "correlation", and optional "strength")
        and returns a formatted line like "  • A ↔ B: 0.123 (strong)" where the pair and correlation value are
        formatted via the class helpers. If `strength` is present it is appended in parentheses.

        Parameters:
            corr (Any): Correlation entry to format; expected to be a dict.

        Returns:
            str | None: Formatted correlation line, or `None` if `corr` is not a dict.
        """
        if not isinstance(corr, dict):
            return None

        pair = corr.get("pair", "n/a")
        correlation_value = corr.get("correlation", 0.0)
        strength = corr.get("strength")

        pair_str = cls._format_pair(pair)
        corr_str = cls._format_correlation_value(correlation_value)

        if strength:
            return f"  • {pair_str}: {corr_str} ({strength})"
        return f"  • {pair_str}: {corr_str}"

    @ classmethod
    def _format_formula_summary(
        cls,
        summary: dict[str, Any],
        analysis_results: dict[str, Any],
    ) -> str:
        """
        Builds a concise, human-readable summary that combines formula category counts, key insights, and the strongest empirical correlations.

        Parameters:
            summary (dict[str, Any]): Aggregate metadata about formula categories and extracted insights.
            analysis_results (dict[str, Any]): Detailed results from formulaic analysis, including empirical relationships and correlation data.

        Returns:
            str: A newline-separated formatted summary suitable for display in the UI.
        """
        summary_lines: list[str] = []
        cls._append_formula_categories(summary_lines, summary)
        cls._append_key_insights(summary_lines, summary)
        cls._append_strongest_correlations(summary_lines, analysis_results)

        return "\n".join(summary_lines)

    @ staticmethod
    def _append_formula_categories(
        summary_lines: list[str],
        summary: dict[str, Any],
    ) -> None:
        """
        Append per-category formula counts to an existing summary lines list.

        If `summary` contains a "formula_categories" mapping, appends one line per category in the form
        "  • {category}: {count} formulas". Does nothing when that key is missing or not a dict.

        Parameters:
            summary_lines (list[str]): Mutable list of summary lines to append to.
            summary (dict[str, Any]): Summary data expected to include a "formula_categories" dict
                mapping category names to integer counts.
        """
        categories = summary.get("formula_categories")
        if not isinstance(categories, dict):
            return

        for category, count in categories.items():
            summary_lines.append(f"  • {category}: {count} formulas")

    @ staticmethod
    def _append_key_insights(
        summary_lines: list[str],
        summary: dict[str, Any],
    ) -> None:
        """
        Append formatted "Key Insights" entries from a summary dictionary into a list of summary lines.

        If `summary` contains a "key_insights" key with a list value, this function appends a section header and each insight as a bulleted line to `summary_lines`. If the key is missing or not a list, `summary_lines` is left unchanged.

        Parameters:
            summary_lines (list[str]): Mutable list of summary lines to which the header and insights will be appended.
            summary (dict[str, Any]): Dictionary that may contain a "key_insights" entry with a list of insight strings.
        """
        summary_lines.extend(["", "🎯 **Key Insights:**"])
        insights = summary.get("key_insights")
        if not isinstance(insights, list):
            return

        for insight in insights:
            summary_lines.append(f"  • {insight}")

    @ classmethod
    def _append_strongest_correlations(
        cls,
        summary_lines: list[str],
        analysis_results: dict[str, Any],
    ) -> None:
        """
        Append up to three formatted strongest-correlation lines to an existing summary.

        If present, reads analysis_results["empirical_relationships"]["strongest_correlations"] and appends a section header plus up to three lines produced by _format_correlation_line. Missing or invalid correlation data is ignored and nothing is appended.

        Parameters:
            summary_lines (list[str]): Mutable list of summary text lines to extend; this list is modified in place.
            analysis_results (dict[str, Any]): Analysis output expected to contain an "empirical_relationships" mapping with a "strongest_correlations" list of correlation entries.
        """
        empirical = analysis_results.get("empirical_relationships") or {}
        correlations = empirical.get("strongest_correlations")
        if not isinstance(correlations, list) or not correlations:
            return

        summary_lines.extend(["", "🔗 **Strongest Asset Correlations:**"])
        for corr in correlations[:3]:
            line = cls._format_correlation_line(corr)
            if line:
                summary_lines.append(line)

    def create_interface(self) -> gr.Blocks:
        """
        Create the Gradio Blocks UI for the application.

        Constructs the tabbed interface (network visualization, metrics and analytics, schema and rules,
        asset explorer, documentation, and formulaic analysis), wires UI events to their handlers,
        and initializes a non-null graph state to store in the interface.

        Returns:
            gr.Blocks: Configured Gradio Blocks instance for the application UI.
        """
        with gr.Blocks(
            title=AppConstants.TITLE,
        ) as interface:
            gr.Markdown(AppConstants.MARKDOWN_HEADER)

            error_message = gr.Textbox(
                label=AppConstants.ERROR_LABEL,
                visible=False,
                interactive=False,
                elem_id="error_message",
            )

            components = self._build_interface_tabs()
            components["error_message"] = error_message

            # Keep a non-null graph in state to avoid Optional pitfalls.
            graph_state = gr.State(value=self.ensure_graph())
            self._wire_interface_events(interface, graph_state, components)

        return interface

    def _build_interface_tabs(self) -> dict[str, Any]:
        """
        Build the application's tabbed UI and return a mapping of key component references.

        Constructs the top-level tabs (Visualization, Metrics, Schema, Asset Explorer, Documentation,
        and Formulaic Analysis) by invoking each tab builder and aggregates their primary Gradio
        components for later wiring.

        Returns:
            components (dict[str, Any]): Mapping from component identifier names to their Gradio
            component objects or related references used for event wiring and UI updates.
        """
        components: dict[str, Any] = {}
        with gr.Tabs():
            components.update(self._build_visualization_tab())
            components.update(self._build_metrics_tab())
            components.update(self._build_schema_tab())
            components.update(self._build_asset_explorer_tab())
            self._build_documentation_tab()
            components.update(self._build_formulaic_tab())
        return components

    def _build_visualization_tab(self) -> dict[str, Any]:
        """
        Builds the Network Visualization tab and returns its UI component references.

        Creates the tab layout including introductory markdown, visualization placeholder, visualization controls,
        relationship visibility toggles, and action buttons, then aggregates their Gradio component objects.

        Returns:
            components (dict[str, Any]): Mapping of component names to Gradio components. At minimum contains
                "visualization_3d" (the Plot placeholder); also includes keys provided by the visualization
                controls, relationship toggles, and action builders.
        """
        with gr.Tab("🌐 Network Visualization (2D/3D)"):
            gr.Markdown(AppConstants.INTERACTIVE_3D_GRAPH_MD)

            controls = self._build_visualization_controls()
            relationship_toggles = self._build_relationship_visibility_controls()

            with gr.Row():
                visualization_3d = gr.Plot()

            actions = self._build_visualization_actions()

        components: dict[str, Any] = {
            "visualization_3d": visualization_3d,
        }
        components.update(controls)
        components.update(relationship_toggles)
        components.update(actions)
        return components

    @ staticmethod
    def _build_visualization_controls() -> dict[str, Any]:
        """
        Create the visualization mode and 2D layout selection controls for the visualization tab.

        Returns:
            controls (dict[str, Any]): Mapping with:
                - "view_mode": Radio component to choose between "3D" and "2D".
                - "layout_type": Radio component to choose the 2D layout ("spring", "circular", "grid"); hidden by default.
        """
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
        return {"view_mode": view_mode, "layout_type": layout_type}

    @ staticmethod
    def _build_relationship_visibility_controls() -> dict[str, Any]:
        """
        Create Gradio checkbox controls for toggling visibility of different relationship types.

        Returns:
            dict[str, Any]: Mapping of control keys to their corresponding Gradio checkbox components, e.g. keys like
                "show_same_sector", "show_market_cap", "show_correlation", "show_corporate_bond",
                "show_commodity_currency", "show_income_comparison", "show_regulatory",
                "show_all_relationships", and "toggle_arrows".
        """
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
                    label="Corporate Bond → Equity (→)",
                    value=True,
                )
                show_commodity_currency = gr.Checkbox(
                    label="Commodity ↔ Currency",
                    value=True,
                )
                show_income_comparison = gr.Checkbox(
                    label="Income Comparison (↔)",
                    value=True,
                )
            with gr.Column(scale=1):
                show_regulatory = gr.Checkbox(
                    label="Regulatory Impact (→)",
                    value=True,
                )
                show_all_relationships = gr.Checkbox(
                    label="Show All Relationships",
                    value=True,
                )
                toggle_arrows = gr.Checkbox(
                    label="Show Direction Arrows",
                    value=True,
                )

        return {
            "show_same_sector": show_same_sector,
            "show_market_cap": show_market_cap,
            "show_correlation": show_correlation,
            "show_corporate_bond": show_corporate_bond,
            "show_commodity_currency": show_commodity_currency,
            "show_income_comparison": show_income_comparison,
            "show_regulatory": show_regulatory,
            "show_all_relationships": show_all_relationships,
            "toggle_arrows": toggle_arrows,
        }

    @ staticmethod
    def _build_visualization_actions() -> dict[str, Any]:
        """
        Create the visualization action controls (refresh and reset) and a small legend row for the visualization tab.

        Returns:
            dict[str, Any]: Mapping with keys:
                - "refresh_viz_btn": the Button component that triggers a visualization refresh.
                - "reset_view_btn": the Button component that resets the view and shows all relationships.
        """
        with gr.Row():
            with gr.Column(scale=1):
                refresh_viz_btn = gr.Button(
                    AppConstants.REFRESH_BUTTON_LABEL,
                    variant="primary",
                )
            with gr.Column(scale=1):
                reset_view_btn = gr.Button(
                    "Reset View & Show All",
                    variant="secondary",
                )
            with gr.Column(scale=2):
                gr.Markdown("**Legend:** ↔ = Bidirectional, → = Unidirectional")
        return {
            "refresh_viz_btn": refresh_viz_btn,
            "reset_view_btn": reset_view_btn,
        }

    def _build_metrics_tab(self) -> dict[str, Any]:
        """
        Builds the Metrics & Analytics tab and returns its Gradio component references.

        Returns:
            dict[str, Any]: Mapping of component names to Gradio components created for the tab:
                - "asset_dist_chart": Plot for asset distribution.
                - "rel_types_chart": Plot for relationship type breakdown.
                - "events_timeline_chart": Plot for events timeline.
                - "metrics_text": Textbox containing network statistics.
                - "refresh_metrics_btn": Button that triggers metrics refresh.
        """
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
                    AppConstants.REFRESH_BUTTON_LABEL,
                    variant="primary",
                )

        return {
            "asset_dist_chart": asset_dist_chart,
            "rel_types_chart": rel_types_chart,
            "events_timeline_chart": events_timeline_chart,
            "metrics_text": metrics_text,
            "refresh_metrics_btn": refresh_metrics_btn,
        }

    def _build_schema_tab(self) -> dict[str, Any]:
        """
        Constructs the Schema & Rules tab UI and exposes its component references.

        Creates a tab containing a markdown guide, a read-only multiline textbox for the generated schema/report,
        and a primary button to trigger schema generation.

        Returns:
            dict[str, Any]: Mapping with keys:
                - "schema_report": the read-only Textbox component displaying the schema/report.
                - "refresh_schema_btn": the Button component used to regenerate the schema.
        """
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
                    AppConstants.GENERATE_SCHEMA_BUTTON_LABEL,
                    variant="primary",
                )

        return {
            "schema_report": schema_report,
            "refresh_schema_btn": refresh_schema_btn,
        }

    def _build_asset_explorer_tab(self) -> dict[str, Any]:
        """
        Create the Asset Explorer tab and its UI components for the Gradio interface.

        Returns:
            dict[str, Any]: Mapping of UI components:
                - "asset_selector": Dropdown for selecting an asset.
                - "asset_info": JSON component displaying the selected asset's properties.
                - "asset_relationships": JSON component listing related/incoming/outgoing relationships.
                - "refresh_explorer_btn": Button to refresh the asset explorer contents.
        """
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
                asset_relationships = gr.JSON(label=AppConstants.RELATED_ASSETS_LABEL)
            with gr.Row():
                refresh_explorer_btn = gr.Button(
                    AppConstants.REFRESH_BUTTON_LABEL,
                    variant="primary",
                )

        return {
            "asset_selector": asset_selector,
            "asset_info": asset_info,
            "asset_relationships": asset_relationships,
            "refresh_explorer_btn": refresh_explorer_btn,
        }

    def _build_documentation_tab(self) -> None:
        """
        Create the Documentation tab in the Gradio interface containing the static markdown from AppConstants.DOC_MARKDOWN.

        Adds a tab labeled with AppConstants.TAB_DOCUMENTATION and populates it with the module's predefined documentation content.
        """
        with gr.Tab(AppConstants.TAB_DOCUMENTATION):
            gr.Markdown(AppConstants.DOC_MARKDOWN)

    def _build_formulaic_tab(self) -> dict[str, Any]:
        """
        Create the Formulaic Analysis tab containing the dashboard, selector, detail view, correlation network, metric comparison chart, refresh control, and a read-only summary box.

        Returns:
            dict[str, Any]: Mapping of component names to their Gradio component references:
                - "formulaic_dashboard": Plot for the formulaic analysis dashboard
                - "correlation_network": Plot for the asset correlation network
                - "metric_comparison": Plot for metric comparison charts
                - "formula_selector": Dropdown for selecting a formula to inspect
                - "formula_summary": Read-only textbox containing a textual summary of analysis results
                - "refresh_formulas_btn": Button to trigger re-generation of formulaic analysis
                - "formula_detail_view": Plot displaying details for the selected formula
        """
        with gr.Tab("📊 Formulaic Analysis"):
            gr.Markdown(
                "## Mathematical Relationships & Formulas\n\n"
                "This section extracts and visualizes mathematical "
                "formulas and relationships between financial "
                "variables. "
                "It includes fundamental financial ratios, "
                "correlation patterns, valuation models, "
                "and empirical relationships derived from the asset "
                "database."
            )

            with gr.Row():
                with gr.Column(scale=2):
                    formulaic_dashboard = gr.Plot(label="Formulaic Analysis Dashboard")
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
                    correlation_network = gr.Plot(label="Asset Correlation Network")
                with gr.Column(scale=1):
                    metric_comparison = gr.Plot(label="Metric Comparison Chart")

            with gr.Row():
                with gr.Column(scale=1):
                    refresh_formulas_btn = gr.Button(
                        "🔄 Refresh Formulaic Analysis",
                        variant="primary",
                    )
                with gr.Column(scale=2):
                    formula_summary = gr.Textbox(
                        label="Formula Analysis Summary",
                        lines=5,
                        interactive=False,
                    )

        return {
            "formulaic_dashboard": formulaic_dashboard,
            "correlation_network": correlation_network,
            "metric_comparison": metric_comparison,
            "formula_selector": formula_selector,
            "formula_summary": formula_summary,
            "refresh_formulas_btn": refresh_formulas_btn,
            "formula_detail_view": formula_detail_view,
        }

    def _wire_interface_events(
        self,
        interface: gr.Blocks,
        graph_state: Any,
        c: dict[str, Any],
    ) -> None:
        """
        Wire Gradio UI components to the app's backend callbacks and register the initial load handler.

        This sets up refresh, visualization, formulaic analysis, and asset event handlers using the provided component map, and schedules an initial call to refresh_all_outputs when the interface loads.

        Parameters:
            interface (gr.Blocks): The Gradio interface container to attach the load handler to.
            graph_state (Any): Shared graph state passed to callbacks.
            c (dict[str, Any]): Mapping of component names to Gradio components used for wiring.
        """
        all_refresh_outputs = self._get_all_refresh_outputs(c)
        visualization_inputs = self._get_visualization_inputs(graph_state, c)
        self._wire_refresh_buttons(graph_state, c, all_refresh_outputs)
        self._wire_visualization_events(graph_state, c, visualization_inputs)
        self._wire_formulaic_events(graph_state, c)
        self._wire_asset_events(graph_state, c)
        interface.load(
            self.refresh_all_outputs,
            inputs=[graph_state],
            outputs=all_refresh_outputs,
        )

    @ staticmethod
    def _get_all_refresh_outputs(c: dict[str, Any]) -> list[Any]:
        """
        List UI components that should be updated by a global refresh action.

        Parameters:
            c (dict[str, Any]): Mapping of component identifiers to UI components. Must include the keys
                "visualization_3d", "asset_dist_chart", "rel_types_chart", "events_timeline_chart",
                "metrics_text", "schema_report", "asset_selector", and "error_message".

        Returns:
            list[Any]: The components to update, returned in the following order:
                1. visualization_3d
                2. asset_dist_chart
                3. rel_types_chart
                4. events_timeline_chart
                5. metrics_text
                6. schema_report
                7. asset_selector
                8. error_message
        """
        return [
            c["visualization_3d"],
            c["asset_dist_chart"],
            c["rel_types_chart"],
            c["events_timeline_chart"],
            c["metrics_text"],
            c["schema_report"],
            c["asset_selector"],
            c["error_message"],
        ]

    @ staticmethod
    def _get_visualization_inputs(
        graph_state: Any,
        c: dict[str, Any],
    ) -> list[Any]:
        """
        Collects and orders the inputs required by the visualization callbacks.

        Parameters:
            graph_state (Any): Shared application graph state object passed to callbacks.
            c (dict[str, Any]): Mapping of visualization control keys to their UI components or values.

        Returns:
            list[Any]: List containing, in this exact order:
                - graph_state
                - c["view_mode"]
                - c["layout_type"]
                - c["show_same_sector"]
                - c["show_market_cap"]
                - c["show_correlation"]
                - c["show_corporate_bond"]
                - c["show_commodity_currency"]
                - c["show_income_comparison"]
                - c["show_regulatory"]
                - c["show_all_relationships"]
                - c["toggle_arrows"]
        """
        return [
            graph_state,
            c["view_mode"],
            c["layout_type"],
            c["show_same_sector"],
            c["show_market_cap"],
            c["show_correlation"],
            c["show_corporate_bond"],
            c["show_commodity_currency"],
            c["show_income_comparison"],
            c["show_regulatory"],
            c["show_all_relationships"],
            c["toggle_arrows"],
        ]

    def _wire_refresh_buttons(
        self,
        graph_state: Any,
        c: dict[str, Any],
        all_refresh_outputs: list[Any],
    ) -> None:
        """
        Bind the metrics, schema, and explorer refresh buttons to the application's refresh_all_outputs handler.

        Parameters:
            graph_state (Any): Shared graph state passed as the single input to the callback.
            c (dict[str, Any]): Mapping of UI component names to Gradio components; must include
                'refresh_metrics_btn', 'refresh_schema_btn', and 'refresh_explorer_btn'.
            all_refresh_outputs (list[Any]): Ordered list of components to receive the outputs from refresh_all_outputs.
        """
        for btn in (
            c["refresh_metrics_btn"],
            c["refresh_schema_btn"],
            c["refresh_explorer_btn"],
        ):
            btn.click(
                self.refresh_all_outputs,
                inputs=[graph_state],
                outputs=all_refresh_outputs,
            )

    def _wire_visualization_events(
        self,
        graph_state: Any,
        c: dict[str, Any],
        visualization_inputs: list[Any],
    ) -> None:
        """
        Connect visualization UI controls to their event handlers and wire the reset action.

        Wires:
        - the refresh button to self.refresh_visualization using the provided visualization inputs;
        - the view mode selector to (a) toggle visibility of the 2D layout control and (b) invoke refresh_visualization;
        - each relationship visibility checkbox and the layout_type control to refresh_visualization on change;
        - the reset view button to self._reset_visualization_and_controls, updating all nine relationship checkboxes, the visualization figure, and the error message.

        Parameters:
            graph_state (Any): Gradio state object carrying the current graph.
            c (dict[str, Any]): Mapping of component keys to Gradio components used in the visualization tab.
            visualization_inputs (list[Any]): Ordered list of inputs passed to refresh handlers (matches _get_visualization_inputs order).
        """
        c["refresh_viz_btn"].click(
            self.refresh_visualization,
            inputs=visualization_inputs,
            outputs=[c["visualization_3d"], c["error_message"]],
        )

        c["view_mode"].change(
            lambda *args: (
                gr.update(visible=args[1] == "2D"),
                *self.refresh_visualization(*args),
            ),
            inputs=visualization_inputs,
            outputs=[c["layout_type"], c["visualization_3d"], c["error_message"]],
        )

        for checkbox in (
            c["show_same_sector"],
            c["show_market_cap"],
            c["show_correlation"],
            c["show_corporate_bond"],
            c["show_commodity_currency"],
            c["show_income_comparison"],
            c["show_regulatory"],
            c["show_all_relationships"],
            c["toggle_arrows"],
        ):
            checkbox.change(
                self.refresh_visualization,
                inputs=visualization_inputs,
                outputs=[c["visualization_3d"], c["error_message"]],
            )

        c["layout_type"].change(
            self.refresh_visualization,
            inputs=visualization_inputs,
            outputs=[c["visualization_3d"], c["error_message"]],
        )

        c["reset_view_btn"].click(
            self._reset_visualization_and_controls,
            inputs=[graph_state, c["view_mode"], c["layout_type"]],
            outputs=[
                c["show_same_sector"],
                c["show_market_cap"],
                c["show_correlation"],
                c["show_corporate_bond"],
                c["show_commodity_currency"],
                c["show_income_comparison"],
                c["show_regulatory"],
                c["show_all_relationships"],
                c["toggle_arrows"],
                c["visualization_3d"],
                c["error_message"],
            ],
        )

    def _wire_formulaic_events(
        self,
        graph_state: Any,
        c: dict[str, Any],
    ) -> None:
        """
        Wire formulaic analysis UI events to their backend callbacks.

        Wires the formulaic refresh button to regenerate formulaic analysis and
        wires the formula selector change event to show details for the selected formula.

        Parameters:
                graph_state (Any): Current graph state object passed into callbacks.
                c (dict[str, Any]): Mapping of UI component keys to Gradio component instances used for wiring.
        """
        formulaic_outputs = [
            c["formulaic_dashboard"],
            c["correlation_network"],
            c["metric_comparison"],
            c["formula_selector"],
            c["formula_summary"],
            c["error_message"],
        ]
        c["refresh_formulas_btn"].click(
            self.generate_formulaic_analysis,
            inputs=[graph_state],
            outputs=formulaic_outputs,
        )
        c["formula_selector"].change(
            self.show_formula_details,
            inputs=[c["formula_selector"], graph_state],
            outputs=[c["formula_detail_view"], c["error_message"]],
        )

    def _wire_asset_events(
        self,
        graph_state: Any,
        c: dict[str, Any],
    ) -> None:
        """
        Register the asset selector change handler to update asset details and relationships.

        When the asset selector value changes, calls `update_asset_info` with the selector value and
        the provided graph state, and populates the `asset_info` and `asset_relationships` components
        with the result.

        Parameters:
            graph_state (Any): The current graph state passed into the callback.
            c (dict[str, Any]): Mapping of UI components; must contain keys 'asset_selector',
                'asset_info', and 'asset_relationships'.
        """
        c["asset_selector"].change(
            self.update_asset_info,
            inputs=[c["asset_selector"], graph_state],
            outputs=[c["asset_info"], c["asset_relationships"]],
        )
