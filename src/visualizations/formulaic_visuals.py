import math
from typing import Any, Dict, List, Mapping, Tuple

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.formulaic_analysis import Formula

_MAX_HEATMAP_ASSETS = 8
_MAX_CORRELATION_EDGES = 10


class FormulaicVisualizer:
    """Visualizes mathematical formulas and relationships from financial analysis."""

    def __init__(self) -> None:
        self.color_scheme = {
            "Valuation": "#FF6B6B",
            "Income": "#4ECDC4",
            "Fixed Income": "#45B7D1",
            "Risk Management": "#96CEB4",
            "Portfolio Theory": "#FFEAA7",
            "Statistical Analysis": "#DDA0DD",
            "Currency Markets": "#98D8C8",
            "Cross-Asset": "#F7DC6F",
        }

    # ------------------------------------------------------------------ #
    # Dashboard                                                            #
    # ------------------------------------------------------------------ #

    def create_formula_dashboard(self, analysis_results: Dict[str, Any]) -> go.Figure:
        """Create comprehensive dashboard showing all formulaic relationships."""
        formulas = analysis_results.get("formulas", [])
        empirical_relationships = analysis_results.get("empirical_relationships", {})

        fig = make_subplots(
            rows=3,
            cols=2,
            subplot_titles=(
                "Formula Categories Distribution",
                "Formula Reliability (R-squared)",
                "Empirical Correlation Matrix",
                "Asset Class Relationships",
                "Sector Analysis",
                "Key Formula Examples",
            ),
            specs=[
                [{"type": "pie"}, {"type": "bar"}],
                [{"type": "heatmap"}, {"type": "bar"}],
                [{"type": "bar"}, {"type": "table"}],
            ],
            vertical_spacing=0.12,
            horizontal_spacing=0.1,
        )

        self._plot_category_distribution(fig, formulas)
        self._plot_reliability(fig, formulas)
        self._plot_empirical_correlation(fig, empirical_relationships)
        self._plot_asset_class_relationships(fig, formulas)
        self._plot_sector_analysis(fig, formulas)
        self._plot_key_formula_examples(fig, formulas)

        fig.update_layout(
            title="📊 Financial Formulaic Analysis Dashboard",
            height=1000,
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="#F8F9FA",
        )
        return fig

    @staticmethod
    def _plot_category_distribution(fig: go.Figure, formulas: Any) -> None:
        if not formulas:
            return
        categories: Dict[str, int] = {}
        for formula in formulas:
            cat = getattr(formula, "category", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1
        fig.add_trace(
            go.Pie(
                labels=list(categories.keys()),
                values=list(categories.values()),
                hole=0.4,
            ),
            row=1,
            col=1,
        )

    @staticmethod
    def _plot_reliability(fig: go.Figure, formulas: Any) -> None:
        """
        Add a bar chart of average R-squared by formula category to the given
        figure.

        Aggregates R-squared values from `formulas` grouped by each formula's
        `category`, computes the average R-squared for each category, and
        adds a bar trace to the subplot at row 1, column 2. If `formulas` is
        empty or falsy, the function does nothing.

        Parameters:
            fig (go.Figure): Plotly figure to which the bar trace will be added.
            formulas (Iterable[Any]): Iterable of formula-like objects.
                Each item may provide a `category` attribute
                (defaults to "Unknown" if missing)
                and an `r_squared` attribute (defaults to `0.0` if missing).
        """
        if not formulas:
            return
        categories: Dict[str, List[float]] = {}
        for formula in formulas:
            cat = getattr(formula, "category", "Unknown")
            categories.setdefault(cat, []).append(getattr(formula, "r_squared", 0.0))
        avg_r2 = {
            cat: sum(vals) / len(vals) for cat, vals in categories.items() if vals
        }
        fig.add_trace(
            go.Bar(
                x=list(avg_r2.keys()),
                y=list(avg_r2.values()),
                marker=dict(color="lightcoral"),
            ),
            row=1,
            col=2,
        )

    @staticmethod
    def _parse_correlation_matrix(
        correlation_matrix: Dict[str, Any],
    ) -> Tuple[List[str], List[List[float]]]:
        """Parse a flat {"asset1-asset2": value} dict into (assets, z_matrix)."""
        pair_values: Dict[Tuple[str, str], float] = {}
        asset_set: set = set()
        for key, value in correlation_matrix.items():
            parts = key.split("-")
            if len(parts) < 2:
                continue
            a1, a2 = parts[0], "-".join(parts[1:])
            pair_values[(a1, a2)] = float(value)
            pair_values[(a2, a1)] = float(value)
            asset_set.add(a1)
            asset_set.add(a2)
        assets = sorted(asset_set)[:_MAX_HEATMAP_ASSETS]
        z = [
            [pair_values.get((a1, a2), 1.0 if a1 == a2 else 0.0) for a2 in assets]
            for a1 in assets
        ]
        return assets, z

    @staticmethod
    def _plot_empirical_correlation(
        fig: go.Figure, empirical_relationships: Mapping[str, Any]
    ) -> None:
        """
        Add an empirical correlation heatmap to the provided subplot figure.

        Extracts the "correlation_matrix" entry from `empirical_relationships`.
        If the entry is a dict, builds a square matrix of correlation values ordered by
        asset name and adds a Heatmap trace to row 2, column 1 with the "RdBu"
        colorscale centered at 0.
        If the correlation matrix is missing or not a dict,
        no trace is added.

        Parameters:
            fig (go.Figure): The Plotly Figure (with subplots)
                to receive the heatmap trace.
            empirical_relationships (Mapping[str, Any]): Mapping expected to contain a
                "correlation_matrix" key whose value is a dict mapping asset to asset to
                correlation value.
        """
        correlation_matrix = (
            empirical_relationships.get("correlation_matrix")
            if isinstance(empirical_relationships, dict)
            else {}
        )

        if not correlation_matrix:
            return
        assets, z = FormulaicVisualizer._parse_correlation_matrix(correlation_matrix)
        if not assets:
            return
        fig.add_trace(
            go.Heatmap(z=z, x=assets, y=assets, colorscale="RdYlBu_r", zmin=-1, zmax=1),
            row=2,
            col=1,
        )

    @staticmethod
    def _plot_asset_class_relationships(fig: go.Figure, formulas: Any) -> None:
        if not formulas:
            return
        categories: Dict[str, int] = {}
        for formula in formulas:
            cat = getattr(formula, "category", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1
        fig.add_trace(
            go.Bar(
                x=list(categories.keys()),
                y=list(categories.values()),
                marker=dict(color="lightgreen"),
            ),
            row=2,
            col=2,
        )

    @staticmethod
    def _plot_sector_analysis(fig: go.Figure, formulas: Any) -> None:
        """
        Visualizes average R-squared by formula category as a bar chart and
        adds it to the dashboard.

        Parameters:
            fig (go.Figure): Plotly Figure containing the subplot grid where the
                bar trace will be added (row 3, col 1).
            formulas (Iterable): Iterable of formula-like objects; each item
                should expose `category` (str) and `r_squared` (numeric).
                Items missing these attributes are treated as category "Unknown"
                and r_squared 0.0.
        """
        if not formulas:
            return
        categories: Dict[str, Dict[str, Any]] = {}
        for formula in formulas:
            cat = getattr(formula, "category", "Unknown")
            entry = categories.setdefault(cat, {"count": 0, "total_r2": 0.0})
            entry["count"] += 1
            entry["total_r2"] += getattr(formula, "r_squared", 0.0)
        performance = {
            cat: d["total_r2"] / d["count"]
            for cat, d in categories.items()
            if d["count"] > 0
        }
        fig.add_trace(
            go.Bar(
                x=list(performance.keys()),
                y=list(performance.values()),
                marker=dict(color="lightblue"),
            ),
            row=3,
            col=1,
        )

    def _plot_key_formula_examples(self, fig: go.Figure, formulas: Any) -> None:
        """
        Add a "Key Formula Examples" table to the provided Figure
        showing the top 10 formulas by R-squared.

        Parameters:
            fig (go.Figure): The Plotly Figure (with subplot grid)
                to which the table trace will be added;
                the table is placed at row 3, column 2.
            formulas (Any): Iterable or sequence of formula objects
                or mappings.
                If truthy, the function selects up to 10 formulas
                ranked by descending
                `r_squared` and displays each formula's name,
                category, and formatted
                R-squared value.
                If falsy, no trace is added.
        """
        if not formulas:
            return
        top = self._get_sorted_formulas(formulas)[:10]
        names, categories, r2_values = self._extract_formula_table_data(top)
        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Formula", "Category", "R-squared"],
                    fill_color="#f2f2f2",
                    align="left",
                ),
                cells=dict(
                    values=[names, categories, r2_values],
                    fill_color="#ffffff",
                    align="left",
                ),
            ),
            row=3,
            col=2,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_sorted_formulas(formulas: Any) -> list[Any]:
        """Sort formulas by descending r_squared with safe fallback."""
        try:
            return sorted(
                formulas,
                key=lambda f: getattr(f, "r_squared", float("-inf")),
                reverse=True,
            )
        except TypeError:
            return list(formulas)

    @staticmethod
    def _format_name(name: Any, max_length: int = 30) -> str:
        """Format formula name with truncation."""
        if not isinstance(name, str) or not name:
            return "N/A"
        return name if len(name) <= max_length else f"{name[: max_length - 3]}..."

    @staticmethod
    def _format_r_squared(r_value: Any) -> str:
        """Format r_squared value to four decimal places or N/A."""
        if isinstance(r_value, (int, float)):
            return f"{r_value:.4f}"
        return "N/A"

    @staticmethod
    def _extract_formula_table_data(
        formulas: Any,
    ) -> tuple[list[str], list[str], list[str]]:
        """
        Prepare parallel lists of formula display names, categories, and
        formatted R-squared values for table rendering.

        Parameters:
                formulas (Iterable): An iterable of objects
                    (typically Formula instances)
                    from which `name`, `category`, and `r_squared` attributes are read.
                    Missing values are handled gracefully.

        Returns:
                tuple[list[str], list[str], list[str]]: Three lists in order:
                        - names: Display-ready formula names
                            (truncated with ellipsis when long or
                             "N/A" if unavailable).
                        - categories: Formula category strings or "N/A" if missing.
                        - r_squared_values: R-squared values formatted as
                            strings (four decimals) or "N/A" if not numeric.
        """
        names = [
            FormulaicVisualizer._format_name(getattr(f, "name", None)) for f in formulas
        ]
        categories = [getattr(f, "category", "N/A") for f in formulas]
        r_squared_values = [
            FormulaicVisualizer._format_r_squared(getattr(f, "r_squared", None))
            for f in formulas
        ]
        return names, categories, r_squared_values

    # ------------------------------------------------------------------
    # Detail & comparison views
    # ------------------------------------------------------------------

    @staticmethod
    def create_formula_detail_view(formula: Formula) -> go.Figure:
        """
        Builds an annotated Plotly figure presenting full details for a Formula.

        The figure contains a single annotation that displays the formula's
        mathematical expression, LaTeX representation, descriptive text,
        category, R² reliability, variables with descriptions, and an example
        calculation.

        Parameters:
            formula (Formula): The formula object to render; expected to provide
                attributes name, formula, latex, description, category,
                r_squared, variables (mapping of variable name to
                description), and example_calculation.

        Returns:
            go.Figure: A Plotly Figure with a formatted annotation summarizing
                the provided formula.
        """
        fig = go.Figure()
        fig.add_annotation(
            text=annotation_text,
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            align="left",
            font=dict(size=12),
        )
        fig.update_layout(
            title=f"Formula Details: {formula.name}",
            height=600,
            plot_bgcolor="white",
        )
        return fig

    # ------------------------------------------------------------------ #
    # Correlation network                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_correlation_network(
        empirical_relationships: Mapping[str, Any],
    ) -> go.Figure:
        """
        Builds a network visualization of asset correlations.

        Parameters:
            empirical_relationships (Mapping[str, Any]): Mapping that may include:
                - "strongest_correlations": an iterable of correlation items (each
                  item can be a dict or sequence describing an asset pair and
                  their correlation value).
                - "correlation_matrix": optional matrix or mapping of pairwise
                  correlations used for reference or weighting.

        Returns:
            go.Figure: A Plotly Figure showing a network of the strongest asset
                correlations, or an empty placeholder Figure
                with an explanatory title when no strongest correlations are
                provided.
        """
        strongest_correlations = empirical_relationships.get(
            "strongest_correlations", []
        )
        if not strongest_correlations:
            return FormulaicVisualizer._create_empty_correlation_figure()
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})
        return FormulaicVisualizer._build_and_render_correlation_network(
            strongest_correlations[:_MAX_CORRELATION_EDGES],
            correlation_matrix,
        )

    @staticmethod
    def _create_empty_correlation_figure() -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(text="No correlation data available", showarrow=False)
        return fig

    @staticmethod
    def _build_and_render_correlation_network(
        strongest_correlations: Any,
        correlation_matrix: Any,
    ) -> go.Figure:
        """
        Create a network graph visualizing asset correlations.

        If no valid assets can be extracted from
        `strongest_correlations`, returns a Figure with the title
        "No valid asset correlations found".

        Parameters:
            strongest_correlations (Any): Iterable of correlation items (e.g.,
                dicts or sequences) describing strong pairwise relationships to
                render as edges.
            correlation_matrix (Any): Full correlation matrix or mapping
                of pairwise correlations used as contextual data for the
                network.
        Returns:
            fig (go.Figure): A Plotly Figure containing edge traces and a
                node trace representing the correlation network, or an empty
                Figure with an explanatory title when no assets are available.
        """
        assets = FormulaicVisualizer._extract_assets_from_correlations(
            strongest_correlations
        )
        if not assets:
            fig = go.Figure()
            fig.update_layout(title="No valid asset correlations found")
            return fig

        positions = FormulaicVisualizer._create_circular_positions(assets)
        edge_traces = FormulaicVisualizer._create_edge_traces(
            strongest_correlations, positions
        )
        node_trace = FormulaicVisualizer._create_node_trace(assets, positions)

        fig = go.Figure(data=edge_traces + [node_trace])
        fig.update_layout(
            title="Asset Correlation Network",
            showlegend=False,
            hovermode="closest",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )
        return fig

    @staticmethod
    def _extract_assets_from_correlations(correlations: Any) -> List[str]:
        assets: set = set()
        for corr in correlations:
            a1, a2, _ = FormulaicVisualizer._parse_correlation_item(corr)
            if a1:
                assets.add(a1)
            if a2:
                assets.add(a2)
        return sorted(a for a in assets if a)

    @staticmethod
    def _parse_correlation_item(corr: Any) -> Tuple[str, str, float]:
        if isinstance(corr, dict):
            return (
                corr.get("asset1", ""),
                corr.get("asset2", ""),
                corr.get("correlation", 0.0),
            )
        if isinstance(corr, (list, tuple)) and len(corr) >= 3:
            return corr[0], corr[1], corr[2]
        if isinstance(corr, (list, tuple)) and len(corr) >= 2:
            return corr[0], corr[1], 0.0
        return "", "", 0.0

    @staticmethod
    def _create_circular_positions(assets: list[str]) -> Dict[str, tuple[float, float]]:
        """
        Compute evenly spaced unit-circle coordinates for each asset.

        Positions are placed on the unit circle, evenly distributed by index and
        starting at angle 0 (point (1.0, 0.0)), proceeding counterclockwise.

        Parameters:
            assets (list[str]): Ordered list of asset identifiers.

        Returns:
            positions (Dict[str, tuple[float, float]]):
            Mapping from asset identifier to its (x, y) coordinate
            on the unit circle.

        Returns:
            positions (Dict[str, tuple[float, float]]):
            Mapping from asset identifier to its (x, y) coordinate
            on the unit circle.
        """
        import math

        n = len(assets)
        return {
            asset: (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n))
            for i, asset in enumerate(assets)
        }

    @staticmethod
    def _create_edge_traces(
        correlations: Any, positions: Dict[str, tuple[float, float]]
    ) -> list[go.Scatter]:
        """
        Generate Plotly edge traces for each correlation linking two
        positioned assets.

        Parameters:
            correlations (Any): Iterable of correlation items parsable by
                _parse_correlation_item; each item should yield
                (asset1, asset2, value).
            positions (Dict[str, tuple[float, float]]): Mapping from asset name
                to (x, y) coordinates used to place nodes.

        Returns:
            list[go.Scatter]: Line Scatter traces for correlations where
                both assets have positions.
        """
        edge_traces = []
        if not isinstance(correlations, (list, tuple)):
            return []
        for corr in correlations:
            a1, a2, val = FormulaicVisualizer._parse_correlation_item(corr)
            if a1 in positions and a2 in positions:
                traces.append(
                    FormulaicVisualizer._create_single_edge_trace(
                        a1, a2, val, positions
                    )
                )
        return traces

    @staticmethod
    def _create_single_edge_trace(
        asset1: str,
        asset2: str,
        value: float,
        positions: Dict[str, Tuple[float, float]],
    ) -> go.Scatter:
        """
        Constructs a Plotly line trace
        representing a correlation edge between two assets.

        Parameters:
            asset1 (str): Identifier of the first asset.
            asset2 (str): Identifier of the second asset.
            value (float): Correlation value between the two assets;
                sign determines trace color.
            positions (Dict[str, tuple[float, float]]):
                Mapping of asset identifiers to (x, y) coordinates.

        Returns:
            go.Scatter: A line trace connecting the two asset positions
                with color indicating sign (red for negative, green for
                positive), line width proportional to the absolute value
                (minimum width of 1), and hover text formatted as
                "asset1 - asset2: value".
        """
        x0, y0 = positions[asset1]
        x1, y1 = positions[asset2]
        color = "red" if value > 0.7 else ("orange" if value > 0.4 else "lightgray")
        return go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line=dict(color=color, width=max(1, abs(value) * 5)),
            hoverinfo="text",
            text=f"{asset1} - {asset2}: {value:.3f}",
            showlegend=False,
        )

    @staticmethod
    def _create_node_trace(
        assets: List[str], positions: Dict[str, Tuple[float, float]]
    ) -> go.Scatter:
        """
        Create a Plotly scatter trace representing asset nodes positioned on a plane.

        Each asset is rendered as a labeled marker placed at the
        (x, y) coordinates from `positions`; markers include hover text and
        display the asset name above the marker.

        Parameters:
            assets (list[str]): Ordered list of asset names to include in the trace.
            positions (Dict[str, tuple[float, float]]): Mapping from asset name to its
                (x, y) coordinates.

        Returns:
            go.Scatter: A Scatter trace with markers and text labels
                for the provided assets.
        """
        node_x = [positions[asset][0] for asset in assets]
        node_y = [positions[asset][1] for asset in assets]

        return go.Scatter(
            x=[positions[a][0] for a in assets],
            y=[positions[a][1] for a in assets],
            mode="markers+text",
            text=assets,
            textposition="top center",
            marker=dict(size=20, color="lightblue", line=dict(color="black", width=2)),
            hoverinfo="text",
            showlegend=False,
        )

    # ------------------------------------------------------------------ #
    # Metric comparison                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_metric_comparison_chart(
        analysis_results: Dict[str, Any],
    ) -> go.Figure:
        """
        Generate a bar chart comparing average R-squared per formula category.

        Parameters:
            analysis_results (Dict[str, Any]): Analysis output that may include a
                "formulas" key with a list of Formula objects.
                (each providing `category` and `r_squared` attributes).

        Returns:
            go.Figure: A Plotly Figure containing a bar chart of average R-squared by
                category; returns an empty Figure if no formulas are present.
        """
        formulas = analysis_results.get("formulas", [])
        fig = go.Figure()

        if formulas:
            categories: Dict[str, List[float]] = {}
            for formula in formulas:
                cat = getattr(formula, "category", None) or (
                    formula.get("category", "Unknown")
                    if isinstance(formula, dict)
                    else "Unknown"
                )
                r2 = (
                    getattr(formula, "r_squared", None)
                    if not isinstance(formula, dict)
                    else formula.get("r_squared", 0.0)
                )
                categories.setdefault(cat, []).append(float(r2 or 0.0))

            names = list(categories.keys())
            avg_r2 = [sum(v) / len(v) for v in categories.values()]
            counts = [len(v) for v in categories.values()]

            fig.add_trace(go.Bar(name="Average R-squared", x=names, y=avg_r2))
            fig.add_trace(go.Bar(name="Formula Count", x=names, y=counts))

        fig.update_layout(
            title="Formula Categories: Reliability vs Count",
            xaxis_title="Formula Category",
            yaxis_title="Value",
            barmode="group",
            plot_bgcolor="white",
        )

        return fig


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


@staticmethod
def _get_sorted_formulas(formulas: Any) -> List[Any]:
    """Return a list of formulas sorted by their R-squared value in descending order.

    If the formulas cannot be sorted due to a TypeError, returns the original list.
    """
    try:
        return sorted(
            formulas,
            key=lambda f: getattr(f, "r_squared", float("-inf")),
            reverse=True,
        )
    except TypeError:
        return list(formulas)


@staticmethod
def _format_name(name: Any, max_length: int = 30) -> str:
    """Format and truncate a formula name to a maximum length.

    Returns 'N/A' if the name is not a valid non-empty string.
    """
    if not isinstance(name, str) or not name:
        return "N/A"
    return name if len(name) <= max_length else f"{name[: max_length - 3]}..."


@staticmethod
def _format_r_squared(r_value: Any) -> str:
    """Format an R-squared value to four decimal places.

    Returns 'N/A' for non-numeric values.
    """
    if isinstance(r_value, (int, float)):
        return f"{r_value:.4f}"
    return "N/A"


@staticmethod
def _extract_formula_table_data(
    formulas: Any,
) -> Tuple[List[str], List[str], List[str]]:
    """Extract names, categories, and R-squared values from a list of formulas.

    Returns three lists: formatted names, categories, and formatted R-squared values
    for table visualization.
    """
    names = [
        FormulaicVisualizer._format_name(getattr(f, "name", None)) for f in formulas
    ]
    categories = [getattr(f, "category", "N/A") for f in formulas]
    r2_values = [
        FormulaicVisualizer._format_r_squared(getattr(f, "r_squared", None))
        for f in formulas
    ]
    return names, categories, r2_values
