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
        Initialize the FinancialAssetApp
        and create its initial asset relationship graph.

        Attempts to populate the instance attribute `graph`
        by calling the internal
        initializer. May raise an exception if graph creation
        or initialization fails.
        """
        self.graph: AssetRelationshipGraph | None = None
        self._initialize_graph()

    @staticmethod
    def _create_database() -> AssetRelationshipGraph:
        """
        Create an AssetRelationshipGraph by locating and invoking a
        factory function in src.data.real_data_fetcher.

        The function probes a set of known factory names and calls the first
        callable it finds to obtain the graph.

        Returns:
            AssetRelationshipGraph: The constructed asset relationship graph.

        Raises:
            TypeError: If a discovered factory is callable but returns
                a value that is not an AssetRelationshipGraph.
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
                if not hasattr(graph, "assets"):
                    raise TypeError(f"{name}() returned {type(graph)!r}, expected AssetRelationshipGraph")
                return graph
        tried_candidates = ", ".join(candidates)
        raise AttributeError(
            f"No known database factory found in src.data.real_data_fetcher. Tried: {tried_candidates}"
        )

    def _initialize_graph(self) -> None:
        """
        Ensure the application's asset graph is created and
        assigned to self.graph.

        Creates and assigns the asset graph to the instance, logging
        initialization progress. If graph creation fails, the exception is
        logged and propagated.

        Raises:
            AttributeError, ImportError, OSError, RuntimeError, TypeError,
            ValueError: Any graph creation/initialization error is re-raised.
        """
        try:
            logger.info("Initializing financial data graph")
            self.graph = self._create_database()
            logger.info("Database initialized with %s assets", len(self.graph.assets))
        except (
            AttributeError,
            ImportError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            logger.error("%s: %s", AppConstants.INITIAL_GRAPH_ERROR, exc)
            raise

    def ensure_graph(self) -> AssetRelationshipGraph:
        """
        Ensure the application's asset relationship graph
        is initialized and return it.

        Returns:
            AssetRelationshipGraph: The non-None graph instance used by the app
                if the graph was missing, it is initialized before being
                returned.
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
        Builds a human-readable network statistics summary for the given asset
        relationship graph.

        Parameters:
            graph (AssetRelationshipGraph): Graph used
                to compute network metrics.

        Returns:
            metrics_text (str): Formatted summary containing totals, averages,
                asset-class distribution, regulatory event count,
                and a ranked list of top relationships.
                Relationship strengths are rendered as percentages
                when numeric,
                otherwise shown as "n/a".
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
        """Return a validated top-relationship tuple, or None."""
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
        """Format relationship strength as percentage, fallback to 'n/a'."""
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
        Return the selected asset's properties and its incoming and
        outgoing relationships.

        If `selected_asset` is None or not present in `graph.assets`, returns
        empty structures.

        Parameters:
            selected_asset (Optional[str]): Asset identifier to look up; may be None.

        Returns:
            tuple[dict, dict]:
                - First element: a dictionary of the asset's attributes
                    (fields from the Asset dataclass),
                    with `asset_class` provided as its string value.
                - Second element: a dictionary with two keys,
                    `outgoing` and `incoming`.
                    Each maps related asset IDs to a dict containing:
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
        Create metric visualizations and a formatted network
        statistics string.

        Returns:
            fig1 (plotly.graph_objs.Figure): First metric visualization figure.
            fig2 (plotly.graph_objs.Figure): Second metric
                visualization figure.
            fig3 (plotly.graph_objs.Figure): Third metric
                visualization figure.
            metrics_text (str): Human-readable network statistics summary
                suitable for display.
        """
        fig1, fig2, fig3 = visualize_metrics(graph)
        metrics_text = self._update_metrics_text(graph)
        return fig1, fig2, fig3, metrics_text

    def refresh_all_outputs(self, _graph_state: AssetRelationshipGraph) -> tuple[Any, ...]:
        """
        Refreshes every UI output panel:
        3D visualization, three metric figures,
        metrics text, schema report, asset selector choices,
        and the refresh status
        indicator.

        Returns:
            tuple[Any, ...]: Ordered outputs matching
                the Gradio interface bindings:
                - 3D visualization figure
                - metric figure 1
                - metric figure 2
                - metric figure 3
                - formatted metrics text (str)
                - schema report text (str)
                - Gradio update for the asset selector (choices list, value)
                - Gradio update for the refresh/error status textbox
                    (value, visible)

        On error, returns a tuple of Gradio updates
        with empty figures/texts, an
        empty choices list, and a visible error message describing the failure.
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
        view_mode: str,
        layout_type: str,
        *relationship_flags: bool,
    ) -> tuple[go.Figure, gr.Update]:
        """Adapter for Gradio callbacks with unpacked relationship flags."""
        return self._refresh_visualization_core(
            _graph_state,
            view_mode,
            layout_type,
            relationship_flags,
        )

    def _refresh_visualization_core(
        self,
        _graph_state: AssetRelationshipGraph,
        view_mode: str,
        layout_type: str,
        relationship_flags: tuple[bool, ...],
    ) -> tuple[go.Figure, gr.Update]:
        """
        Refreshes the asset graph visualization according to the selected view and
        relationship filters.

        Parameters:
            graph_state (AssetRelationshipGraph): Current asset relationship graph
                used for rendering.
            view_mode (str): Either "2D" or other value indicating 3D rendering mode.
            layout_type (str): Layout style to use when rendering the 2D view.
            relationship_flags (bool): Variable-length relationship toggles in this
                order:
                show_same_sector, show_market_cap, show_correlation,
                show_corporate_bond, show_commodity_currency,
                show_income_comparison, show_regulatory,
                show_all_relationships, toggle_arrows.

        Returns:
            tuple[go.Figure, gr.Update]: A Plotly Figure for the requested
                visualization and a Gradio Update controlling the error/message
                display (hidden on success,
                visible with an error message on failure).
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

        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError) as exc:
            logger.error("Error refreshing visualization: %s", exc)
            empty_fig = go.Figure()
            error_msg = f"Error refreshing visualization: {exc}"
            return empty_fig, gr.update(value=error_msg, visible=True)

    @staticmethod
    def _normalize_relationship_flags(
        relationship_flags: tuple[bool, ...],
    ) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool]:
        """Normalize relationship toggles to the expected 9-flag tuple."""
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

    @staticmethod
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
        """Return default ON state for all relationship toggles."""
        return (True, True, True, True, True, True, True, True, True)

    def _reset_visualization_view(
        self,
        graph_state: AssetRelationshipGraph,
        view_mode: str,
        layout_type: str,
    ) -> tuple[go.Figure, gr.Update]:
        """Refresh visualization with all relationship filters enabled."""
        return self._refresh_visualization_core(
            graph_state,
            view_mode,
            layout_type,
            self._default_relationship_flags(),
        )

    @staticmethod
    def _render_visualization(
        graph: AssetRelationshipGraph,
        view_mode: str,
        layout_type: str,
        relationship_flags: tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool],
    ) -> go.Figure:
        """Render either 2D or 3D visualization with relationship filters."""
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
        """Generate formulaic analysis figures and UI updates."""
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
        """Build successful formulaic-analysis outputs."""
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

    @staticmethod
    def _build_formulaic_error_outputs(exc: Exception) -> tuple[Any, ...]:
        """Build fallback outputs when formulaic analysis fails."""
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
    def show_formula_details(_formula_name: str, graph_state: AssetRelationshipGraph) -> tuple[go.Figure, gr.Update]:
        """
        Display detailed visualization for the selected formula.

        Parameters:
            formula_name (str): Name or identifier
                of the formula to display. If
                None or not found, no detail is shown.
            graph_state (AssetRelationshipGraph):
                The asset relationship graph used to
                generate formula detail visualizations.

        Returns:
            tuple[go.Figure, gr.Update]: A Plotly Figure containing the formula
                detail view and a Gradio Update
                controlling the detail view state
                (e.g., visibility and selection value).
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

    @staticmethod
    def _format_pair(pair: Any) -> str:
        """Format an asset pair into a human-readable string."""
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            asset_a, asset_b = pair
            return f"{asset_a} ↔ {asset_b}"
        return str(pair)

    @staticmethod
    def _format_correlation_value(value: Any) -> str:
        """Format the correlation value as a string."""
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value)

    @classmethod
    def _format_correlation_line(cls, corr: Any) -> str | None:
        """Return a single formatted correlation line or None."""
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

    @classmethod
    def _format_formula_summary(
        cls,
        summary: dict[str, Any],
        analysis_results: dict[str, Any],
    ) -> str:
        """
        Create a concise, human-readable summary of formulaic analysis and
        empirical relationships.
        """
        summary_lines: list[str] = []
        cls._append_formula_categories(summary_lines, summary)
        cls._append_key_insights(summary_lines, summary)
        cls._append_strongest_correlations(summary_lines, analysis_results)

        return "\n".join(summary_lines)

    @staticmethod
    def _append_formula_categories(
        summary_lines: list[str],
        summary: dict[str, Any],
    ) -> None:
        """Append per-category formula counts to summary lines."""
        categories = summary.get("formula_categories")
        if not isinstance(categories, dict):
            return

        for category, count in categories.items():
            summary_lines.append(f"  • {category}: {count} formulas")

    @staticmethod
    def _append_key_insights(
        summary_lines: list[str],
        summary: dict[str, Any],
    ) -> None:
        """Append key insights section to summary lines."""
        summary_lines.extend(["", "🎯 **Key Insights:**"])
        insights = summary.get("key_insights")
        if not isinstance(insights, list):
            return

        for insight in insights:
            summary_lines.append(f"  • {insight}")

    @classmethod
    def _append_strongest_correlations(
        cls,
        summary_lines: list[str],
        analysis_results: dict[str, Any],
    ) -> None:
        """Append strongest correlation lines to the summary."""
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
        Build and return the Gradio Blocks UI for the FinancialAssetApp.

        The UI is organized into multiple tabs
        (network visualization, metrics and analytics, schema and rules,
        asset explorer, documentation, and formulaic analysis).
        It wires UI events to refresh/update handlers and initializes
        a non-null graph state to avoid Optional-related pitfalls.

        Returns:
            gr.Blocks:
                Configured Gradio Blocks instance for the
                application UI.
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
        """Build all tabs and return references to key components."""
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
        """Build the network-visualization tab."""
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

    @staticmethod
    def _build_visualization_controls() -> dict[str, Any]:
        """Build top-level visualization controls for mode and layout."""
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

    @staticmethod
    def _build_relationship_visibility_controls() -> dict[str, Any]:
        """Build relationship visibility toggle controls."""
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

    @staticmethod
    def _build_visualization_actions() -> dict[str, Any]:
        """Build visualization action buttons and legend."""
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
        """Build the metrics/analytics tab."""
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
        """Build the schema/rules tab."""
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
        """Build the asset-explorer tab."""
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
        """Build the static documentation tab."""
        with gr.Tab(AppConstants.TAB_DOCUMENTATION):
            gr.Markdown(AppConstants.DOC_MARKDOWN)

    def _build_formulaic_tab(self) -> dict[str, Any]:
        """Build the formulaic-analysis tab."""
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
        """Connect Gradio component events to app callbacks."""
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

    @staticmethod
    def _get_all_refresh_outputs(c: dict[str, Any]) -> list[Any]:
        """Return output components updated by global refresh actions."""
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

    @staticmethod
    def _get_visualization_inputs(
        graph_state: Any,
        c: dict[str, Any],
    ) -> list[Any]:
        """Return ordered visualization callback inputs."""
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
        """Wire generic refresh buttons to refresh-all callback."""
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
        """Wire visualization controls and view reset actions."""
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
            self._reset_visualization_view,
            inputs=[graph_state, c["view_mode"], c["layout_type"]],
            outputs=[c["visualization_3d"], c["error_message"]],
        )

    def _wire_formulaic_events(
        self,
        graph_state: Any,
        c: dict[str, Any],
    ) -> None:
        """Wire formulaic analysis refresh and selection callbacks."""
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
        """Wire asset selector interactions."""
        c["asset_selector"].change(
            self.update_asset_info,
            inputs=[c["asset_selector"], graph_state],
            outputs=[c["asset_info"], c["asset_relationships"]],
        )
