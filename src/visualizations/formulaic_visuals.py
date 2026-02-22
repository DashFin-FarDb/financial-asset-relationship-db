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
        Add a bar trace to the provided figure showing the average R-squared per formula category.

        Parameters:
            fig (go.Figure): Plotly figure to which the bar trace will be added.
            formulas (Iterable): Iterable of formula-like objects or mappings. Each item should provide a `category` (str) and an `r_squared` (numeric). Missing `category` values are treated as "Unknown" and missing `r_squared` values are treated as 0.0. If `formulas` is empty or falsy, no trace is added.
        """
        if not formulas:
            return
        categories: Dict[str, List[float]] = {}
        for formula in formulas:
            cat = getattr(formula, "category", "Unknown")
            categories.setdefault(cat, []).append(getattr(formula, "r_squared", 0.0))
        avg_r2 = {cat: sum(vals) / len(vals) for cat, vals in categories.items() if vals}
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
        """
        Convert a flat correlation mapping into an ordered list of assets and a square correlation matrix.

        Parameters:
            correlation_matrix (Dict[str, Any]): Mapping where keys are asset pair strings in the form
                "asset1-asset2" and values are numeric correlation scores.

        Returns:
            Tuple[List[str], List[List[float]]]:
                - assets: Sorted list of unique asset names, truncated to the configured maximum.
                - z_matrix: Square matrix (list of rows) aligned with `assets` where diagonal entries are `1.0`,
                  known pair correlations are filled with their numeric values, and missing off-diagonal entries are `0.0`.
        """
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
        z = [[pair_values.get((a1, a2), 1.0 if a1 == a2 else 0.0) for a2 in assets] for a1 in assets]
        return assets, z

    @staticmethod
    def _plot_empirical_correlation(fig: go.Figure, empirical_relationships: Mapping[str, Any]) -> None:
        """
        Add an empirical asset correlation heatmap to the provided figure when valid correlation data is available.

        If `empirical_relationships` contains a mapping under the key `"correlation_matrix"`, the function parses that matrix into ordered asset labels and a square correlation matrix and appends a heatmap trace to `fig` at subplot row 2, column 1. If the correlation matrix is missing, not a dict, or yields no assets, the function does nothing.

        Parameters:
            empirical_relationships (Mapping[str, Any]): Mapping expected to include a `"correlation_matrix"` dict where keys are asset-pair identifiers (e.g., `"A-B"`) and values are correlation coefficients.
        """
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})
        if not correlation_matrix or not isinstance(correlation_matrix, dict):
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
        Plot average R-squared per formula category as a bar chart and add it to the subplot at row 3, column 1.

        Parameters:
            fig (plotly.graph_objs._figure.Figure): The Plotly figure to which the bar trace will be added.
            formulas (Iterable): Iterable of formula-like objects or mappings. Each item should provide a `category`
                (attribute or key) and an `r_squared` numeric value (attribute or key). Items missing these will
                contribute to the "Unknown" category or be treated as 0.0 for R-squared.

        Notes:
            - If `formulas` is empty or falsy, the function returns without modifying `fig`.
            - The plotted value for each category is the average of the `r_squared` values for formulas in that category.
        """
        if not formulas:
            return
        categories: Dict[str, Dict[str, Any]] = {}
        for formula in formulas:
            cat = getattr(formula, "category", "Unknown")
            entry = categories.setdefault(cat, {"count": 0, "total_r2": 0.0})
            entry["count"] += 1
            entry["total_r2"] += getattr(formula, "r_squared", 0.0)
        performance = {cat: d["total_r2"] / d["count"] for cat, d in categories.items() if d["count"] > 0}
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

    # ------------------------------------------------------------------ #
    # Detail view                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_formula_detail_view(formula: Formula) -> go.Figure:
        """
        Render a Plotly figure displaying detailed information for a single formula.

        Parameters:
            formula (Formula): Formula object whose displayed fields include:
                - name: formula title
                - expression: human-readable mathematical expression
                - latex: LaTeX representation
                - description: textual description of the formula
                - category: category label
                - r_squared: numeric reliability value (R²)
                - variables: mapping of variable name to description
                - example_calculation: example illustrating the formula

        Returns:
            go.Figure: A Plotly Figure containing a centered, non-arrow annotation that presents the formula's details (name, expression, LaTeX, description, category, R², variables, and example calculation).
        """
        variables_text = "<br>".join(f"• {var}: {desc}" for var, desc in formula.variables.items())
        annotation_text = (
            f"<b>{formula.name}</b><br><br>"
            f"<b>Mathematical Expression:</b><br>{formula.expression}<br><br>"
            f"<b>LaTeX:</b><br>{formula.latex}<br><br>"
            f"<b>Description:</b><br>{formula.description}<br><br>"
            f"<b>Category:</b> {formula.category}<br>"
            f"<b>Reliability (R²):</b> {formula.r_squared:.3f}<br><br>"
            f"<b>Variables:</b><br>{variables_text}<br><br>"
            f"<b>Example Calculation:</b><br>{formula.example_calculation}"
        )
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
        Builds a network visualization of the strongest asset correlations contained in empirical relationships.

        Parameters:
            empirical_relationships (Mapping[str, Any]): Mapping that should contain:
                - "strongest_correlations": an iterable of correlation entries (each may be a dict or sequence describing two assets and their correlation strength).
                - "correlation_matrix": optional pairwise correlation mapping used to render edge values.

        Returns:
            go.Figure: A Plotly Figure containing the correlation network. If no "strongest_correlations" are present, returns an empty-correlation figure indicating no available data.
        """
        strongest_correlations = empirical_relationships.get("strongest_correlations", [])
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
        Render a network graph visualizing the strongest asset correlations.

        Parameters:
            strongest_correlations (Any): Iterable of correlation entries (e.g., dicts with keys
                "asset1", "asset2", "correlation" or sequences like [asset1, asset2, value]) used
                to determine network edges and their weights.
            correlation_matrix (Any): Optional mapping of pairwise correlation values (assetA-assetB ->
                value); provided for context or future use but not required by this renderer.

        Returns:
            go.Figure: A Plotly Figure containing a circularly arranged node-and-edge network of the
            assets. If no valid assets are found, returns a Figure with the title "No valid asset
            correlations found".
        """
        assets = FormulaicVisualizer._extract_assets_from_correlations(strongest_correlations)
        if not assets:
            fig = go.Figure()
            fig.update_layout(title="No valid asset correlations found")
            return fig

        positions = FormulaicVisualizer._create_circular_positions(assets)
        edge_traces = FormulaicVisualizer._create_edge_traces(strongest_correlations, positions)
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
    def _create_circular_positions(assets: List[str]) -> Dict[str, Tuple[float, float]]:
        """
        Compute 2D positions for each asset placed evenly on the unit circle.

        Parameters:
            assets (List[str]): Ordered list of asset identifiers to position around the circle.

        Returns:
            Dict[str, Tuple[float, float]]: Mapping from each asset to an (x, y) coordinate on the unit circle.

        Raises:
            ZeroDivisionError: If `assets` is empty.
        """
        n = len(assets)
        return {asset: (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i, asset in enumerate(assets)}

    @staticmethod
    def _create_edge_traces(correlations: Any, positions: Dict[str, Tuple[float, float]]) -> List[go.Scatter]:
        """
        Builds Plotly line traces for each correlation edge connecting two positioned assets.

        Parameters:
            correlations (Iterable): Sequence of correlation entries. Each entry may be a dict with keys "asset1", "asset2", "correlation", or a sequence like (asset1, asset2, value) or (asset1, asset2).
            positions (Dict[str, Tuple[float, float]]): Mapping from asset identifier to its (x, y) coordinates.

        Returns:
            List[go.Scatter]: A list of Plotly Scatter traces representing edges for correlations where both assets have positions.
        """
        traces = []
        for corr in correlations:
            a1, a2, val = FormulaicVisualizer._parse_correlation_item(corr)
            if a1 in positions and a2 in positions:
                traces.append(FormulaicVisualizer._create_single_edge_trace(a1, a2, val, positions))
        return traces

    @staticmethod
    def _create_single_edge_trace(
        asset1: str,
        asset2: str,
        value: float,
        positions: Dict[str, Tuple[float, float]],
    ) -> go.Scatter:
        """
        Create a Plotly Scatter trace representing an edge between two assets in the correlation network.

        Parameters:
            asset1 (str): Label of the first asset.
            asset2 (str): Label of the second asset.
            value (float): Correlation strength (typically between -1 and 1) used to set line width and color.
            positions (Dict[str, Tuple[float, float]]): Mapping of asset labels to (x, y) coordinates.

        Returns:
            go.Scatter: A line trace connecting the two asset positions with color and width reflecting `value`; hover text shows the asset pair and the numeric value.
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
    def _create_node_trace(assets: List[str], positions: Dict[str, Tuple[float, float]]) -> go.Scatter:
        """
        Create a Plotly Scatter trace representing assets as labeled nodes placed at their specified coordinates.

        Parameters:
            assets (List[str]): Ordered list of asset labels to include as nodes.
            positions (Dict[str, Tuple[float, float]]): Mapping from asset label to (x, y) coordinates.

        Returns:
            go.Scatter: A scatter trace with markers and text labels for each asset; markers are styled with a light blue fill, black border, size 20, and hover text shows the asset label.
        """
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
    def create_metric_comparison_chart(analysis_results: Dict[str, Any]) -> go.Figure:
        """
        Create a grouped bar chart comparing average R-squared and formula count for each formula category.

        Parameters:
            analysis_results (Dict[str, Any]): Mapping that should include a "formulas" key with a list of formula entries. Each entry may be an object with attributes or a dict and is expected to provide a category (string) and an r_squared value (numeric).

        Returns:
            go.Figure: Plotly Figure containing two grouped bar traces: "Average R-squared" and "Formula Count", keyed by formula category.
        """
        formulas = analysis_results.get("formulas", [])
        fig = go.Figure()

        if formulas:
            categories: Dict[str, List[float]] = {}
            for formula in formulas:
                cat = getattr(formula, "category", None) or (
                    formula.get("category", "Unknown") if isinstance(formula, dict) else "Unknown"
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
        if not isinstance(name, str) or not name:
            return "N/A"
        return name if len(name) <= max_length else f"{name[: max_length - 3]}..."

    @staticmethod
    def _format_r_squared(r_value: Any) -> str:
        if isinstance(r_value, (int, float)):
            return f"{r_value:.4f}"
        return "N/A"

    @staticmethod
    def _extract_formula_table_data(
        formulas: Any,
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Extracts parallel lists of display-ready formula names, categories, and formatted R-squared values.

        Parameters:
            formulas (Iterable): An iterable of formula-like objects or mappings. Each item may expose attributes (e.g., `.name`, `.category`, `.r_squared`) or equivalent keys; missing values are replaced with defaults.

        Returns:
            tuple: Three lists in order:
                - names: formatted formula names (strings, "N/A" or truncated when necessary).
                - categories: category strings (defaults to "N/A" when missing).
                - r2_values: R-squared values formatted as strings (e.g., "0.1234" or "N/A").
        """
        names = [FormulaicVisualizer._format_name(getattr(f, "name", None)) for f in formulas]
        categories = [getattr(f, "category", "N/A") for f in formulas]
        r2_values = [FormulaicVisualizer._format_r_squared(getattr(f, "r_squared", None)) for f in formulas]
        return names, categories, r2_values
