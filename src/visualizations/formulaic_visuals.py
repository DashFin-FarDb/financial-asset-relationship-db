from typing import Any, Dict, Mapping

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.formulaic_analysis import Formula


class FormulaicVisualizer:
    """Visualizes mathematical formulas and relationships from financial analysis."""

    def __init__(self) -> None:
        """
        Initialize the visualizer and set the default color mapping for formula categories.

        This constructs self.color_scheme as a dictionary that maps recognizable formula/category names to their display hex color values (e.g., "Valuation" -> "#FF6B6B").
        """
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

    def create_formula_dashboard(self, analysis_results: Dict[str, Any]) -> go.Figure:
        """
        Build a 3x2 dashboard figure visualizing formulas and their relationships.

        Parameters:
            analysis_results (Dict[str, Any]): Analysis output containing visualization inputs. Expected keys:
                - "formulas": iterable of Formula-like objects (each may provide attributes such as `name`, `category`, `r_squared`, `variables`, etc.).
                - "empirical_relationships": mapping that may include a correlation matrix and related data used for the empirical correlation heatmap and network.

        Returns:
            go.Figure: A Plotly Figure with six subplots: category distribution (pie), reliability by category (bar), empirical correlation matrix (heatmap),
            asset class relationships (bar), sector analysis (bar), and a table of key formula examples.
        """
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

        return fig

    # ------------------------------------------------------------------
    # Dashboard plotting methods
    # ------------------------------------------------------------------

    @staticmethod
    def _plot_category_distribution(fig: go.Figure, formulas: Any) -> None:
        """Plot distribution of formulas across categories."""
        if not formulas:
            return

        categories = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            categories[category] = categories.get(category, 0) + 1

        fig.add_trace(
            go.Pie(
                labels=list(categories.keys()),
                values=list(categories.values()),
                hole=0.3,
            ),
            row=1,
            col=1,
        )

    @staticmethod
    def _plot_reliability(fig: go.Figure, formulas: Any) -> None:
        """
        Add a bar chart of average R-squared per formula category to the provided figure.

        If `formulas` is falsy the function does nothing. Otherwise it groups r_squared
        values by each formula's `category` (uses "Unknown" if missing) and treats a
        missing `r_squared` as 0.0, computes the average per category, and adds a Bar
        trace to the subplot at row 1, column 2.

        Parameters:
            fig (go.Figure): Plotly figure to which the bar trace will be added.
            formulas (Iterable[Any]): Iterable of objects that may provide `category`
                and `r_squared` attributes.
        """
        if not formulas:
            return

        categories = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            r_squared = getattr(formula, "r_squared", 0.0)
            if category not in categories:
                categories[category] = []
            categories[category].append(r_squared)

        avg_r_squared = {
            cat: sum(vals) / len(vals) if vals else 0.0
            for cat, vals in categories.items()
        }

        fig.add_trace(
            go.Bar(
                x=list(avg_r_squared.keys()),
                y=list(avg_r_squared.values()),
                marker=dict(color="lightcoral"),
            ),
            row=1,
            col=2,
        )

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

        if isinstance(correlation_matrix, dict):
            assets = sorted(correlation_matrix.keys())
            z = [
                [correlation_matrix.get(a1, {}).get(a2, 0.0) for a2 in assets]
                for a1 in assets
            ]
        else:
            # Assume it's already a matrix-like structure
            return

        fig.add_trace(
            go.Heatmap(
                z=z,
                x=assets,
                y=assets,
                colorscale="RdBu",
                zmid=0,
            ),
            row=2,
            col=1,
        )

    @staticmethod
    def _plot_asset_class_relationships(fig: go.Figure, formulas: Any) -> None:
        """
        Add a bar chart showing the count of formulas per category to the dashboard (subplot row 2, col 2).

        Parameters:
            fig (go.Figure): The Plotly figure to which the bar trace will be added.
            formulas (Iterable): Iterable of formula-like objects; each item is expected to have a `category` attribute or property. If `formulas` is falsy, the function does nothing.
        """
        if not formulas:
            return

        # Group formulas by category and count relationships
        categories = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            categories[category] = categories.get(category, 0) + 1

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
        Visualize average R-squared by formula category as a bar chart and add it to the dashboard.

        Aggregates formulas by their `category`, computes the mean `r_squared` per category (treating missing category as "Unknown" and missing r_squared as 0.0), and appends a bar trace to `fig` (intended for subplot row 3, column 1).

        Parameters:
            fig (go.Figure): Plotly Figure containing the subplot grid to receive the bar trace.
            formulas (Iterable): Iterable of formula-like objects; each item should expose `category` (str) and `r_squared` (numeric). Missing attributes are handled as described above.
        """
        if not formulas:
            return

        # Simple sector distribution based on categories
        categories = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            r_squared = getattr(formula, "r_squared", 0.0)
            if category not in categories:
                categories[category] = {"count": 0, "total_r2": 0.0}
            categories[category]["count"] += 1
            categories[category]["total_r2"] += r_squared

        sector_performance = {
            cat: data["total_r2"] / data["count"] if data["count"] > 0 else 0.0
            for cat, data in categories.items()
        }

        fig.add_trace(
            go.Bar(
                x=list(sector_performance.keys()),
                y=list(sector_performance.values()),
                marker=dict(color="lightblue"),
            ),
            row=3,
            col=1,
        )

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def _plot_key_formula_examples(self, fig: go.Figure, formulas: Any) -> None:
        """
        Render a "Key Formula Examples" table showing up to the top 10 formulas by R-squared into the provided Figure.

        If `formulas` is falsy, no trace is added.

        Parameters:
            fig (go.Figure): Plotly Figure with a subplot grid; the table is added at row 3, column 2.
            formulas (Any): Iterable of formula-like objects or mappings. The function selects up to 10 formulas
                ranked by descending `r_squared` and displays each formula's name, category, and formatted R-squared.
        """
        if not formulas:
            return

        sorted_formulas = self._get_sorted_formulas(formulas)
        top_formulas = sorted_formulas[:10]

        names, categories, r_squared_values = self._extract_formula_table_data(
            top_formulas
        )

        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Formula", "Category", "R-squared"],
                    fill_color="#f2f2f2",
                    align="left",
                ),
                cells=dict(
                    values=[names, categories, r_squared_values],
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
        """
        Return a list of formulas sorted by descending `r_squared`, or the input converted to a list if sorting is not possible.

        Parameters:
            formulas (Iterable): Iterable of objects that may have an `r_squared` attribute.

        Returns:
            list[Any]: Formulas sorted by `r_squared` in descending order; if a TypeError occurs during sorting, returns `list(formulas)` preserving original order.
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
        """
        Normalize and truncate a formula name for display.

        Parameters:
            name (Any): The value to format as a formula name. Non-string or empty values yield "N/A".
            max_length (int): Maximum allowed length of the returned name including the ellipsis (default 30).

        Returns:
            str: The original name if its length is <= max_length; otherwise a truncated version with a trailing ellipsis. "N/A" is returned for non-string or empty inputs.
        """
        if not isinstance(name, str) or not name:
            return "N/A"
        return name if len(name) <= max_length else f"{name[: max_length - 3]}..."

    @staticmethod
    def _format_r_squared(r_value: Any) -> str:
        """
        Format an R-squared value for display.

        Parameters:
            r_value (Any): The value to format as R-squared.

        Returns:
            str: The value formatted to four decimal places if `r_value` is an int or float, otherwise `"N/A"`.
        """
        if isinstance(r_value, (int, float)):
            return f"{r_value:.4f}"
        return "N/A"

    @staticmethod
    def _extract_formula_table_data(
        formulas: Any,
    ) -> tuple[list[str], list[str], list[str]]:
        """
        Prepare parallel lists of display-ready formula names, categories, and formatted R-squared strings for table rendering.

        Parameters:
            formulas (Iterable): Iterable of objects (typically Formula instances) whose
                `name`, `category`, and `r_squared` attributes will be read; missing or
                invalid values are represented as "N/A".

        Returns:
            tuple[list[str], list[str], list[str]]: Three lists in order:
                - names: Truncated or normalized formula names for display, or "N/A".
                - categories: Category strings or "N/A" when missing.
                - r_squared_values: R-squared values formatted to four decimals as strings,
                  or "N/A" when the value is not numeric.
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
            text=(
                f"<b>{formula.name}</b><br><br>"
                "<b>Mathematical Expression:</b><br>"
                f"{formula.expression}<br><br>"
                "<b>LaTeX:</b><br>"
                f"{formula.latex}<br><br>"
                "<b>Description:</b><br>"
                f"{formula.description}<br><br>"
                f"<b>Category:</b> {formula.category}<br>"
                f"<b>Reliability (R²):</b> {formula.r_squared:.3f}<br><br>"
                "<b>Variables:</b><br>"
                + "<br>".join(
                    f"• {var}: {desc}" for var, desc in formula.variables.items()
                )
                + "<br><br><b>Example Calculation:</b><br>"
                f"{formula.example_calculation}"
            ),
            showarrow=False,
        )

        return fig

    # ------------------------------------------------------------------
    # Correlation network (stubbed safely)
    # ------------------------------------------------------------------

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
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})

        if not strongest_correlations:
            return FormulaicVisualizer._create_empty_correlation_figure()

        return FormulaicVisualizer._build_and_render_correlation_network(
            strongest_correlations,
            correlation_matrix,
        )

    @staticmethod
    def _create_empty_correlation_figure() -> go.Figure:
        """
        Create a placeholder Plotly Figure used when no correlation data is available.

        Returns:
            figure (go.Figure): A Figure configured with the title "No correlation data available".
        """
        fig = go.Figure()
        fig.update_layout(title="No correlation data available")
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
    def _extract_assets_from_correlations(correlations: Any) -> list[str]:
        """
        Extract a sorted list of unique asset names found in the provided correlation entries.

        Parameters:
            correlations (Iterable): Iterable of correlation entries; each entry can be a mapping or sequence that contains one or two asset identifiers.

        Returns:
            list[str]: Sorted list of unique, non-empty asset names extracted from the correlations.
        """
        assets = set()
        for corr in correlations:
            asset1, asset2, _ = FormulaicVisualizer._parse_correlation_item(corr)
            if asset1:
                assets.add(asset1)
            if asset2:
                assets.add(asset2)
        return sorted([a for a in assets if a])

    @staticmethod
    def _parse_correlation_item(corr: Any) -> tuple[str, str, float]:
        """
        Normalize a correlation entry into a canonical (asset1, asset2, value) tuple.

        Accepts a dict with keys "asset1", "asset2", and optional "correlation", or a list/tuple of length 2 or 3. Missing asset names default to an empty string and a missing correlation defaults to 0.0.

        Parameters:
            corr (Any): Correlation item to parse — expected formats:
                - dict: {"asset1": str, "asset2": str, "correlation": float}
                - sequence of length 3: [asset1, asset2, value]
                - sequence of length 2: [asset1, asset2]

        Returns:
            tuple[str, str, float]: `(asset1, asset2, value)` where `asset1` and `asset2` are asset names (empty string if absent) and `value` is the correlation (0.0 if absent or unspecified).
        """
        if isinstance(corr, dict):
            return (
                corr.get("asset1", ""),
                corr.get("asset2", ""),
                corr.get("correlation", 0.0),
            )
        if isinstance(corr, (list, tuple)) and len(corr) >= 3:
            return (corr[0], corr[1], corr[2])
        if isinstance(corr, (list, tuple)) and len(corr) >= 2:
            return (corr[0], corr[1], 0.0)
        return ("", "", 0.0)

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
        """
        import math

        n = len(assets)
        positions = {}
        for i, asset in enumerate(assets):
            angle = 2 * math.pi * i / n
            positions[asset] = (math.cos(angle), math.sin(angle))
        return positions

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
            asset1, asset2, value = FormulaicVisualizer._parse_correlation_item(corr)
            if asset1 in positions and asset2 in positions:
                trace = FormulaicVisualizer._create_single_edge_trace(
                    asset1, asset2, value, positions
                )
                edge_traces.append(trace)
        return edge_traces

    @staticmethod
    def _create_single_edge_trace(
        asset1: str,
        asset2: str,
        value: float,
        positions: Dict[str, tuple[float, float]],
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
        color = "red" if value < 0 else "green"
        width = max(1, abs(value) * 5)

        return go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line=dict(color=color, width=width),
            hoverinfo="text",
            text=f"{asset1} - {asset2}: {value:.3f}",
            showlegend=False,
        )

    @staticmethod
    def _create_node_trace(
        assets: list[str], positions: Dict[str, tuple[float, float]]
    ) -> go.Scatter:
        """
        Create a Plotly scatter trace that renders asset nodes at specified (x, y) coordinates with labels.

        Parameters:
            assets (list[str]): Ordered asset names to render as markers.
            positions (Dict[str, tuple[float, float]]): Mapping from asset name to its (x, y) coordinates.

        Returns:
            go.Scatter: A scatter trace containing markers and top-centered text labels for each asset; hover text shows the asset name.
        """
        node_x = [positions[asset][0] for asset in assets]
        node_y = [positions[asset][1] for asset in assets]

        return go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=assets,
            textposition="top center",
            marker=dict(
                size=20,
                color="lightblue",
                line=dict(
                    color="black",
                    width=2,
                ),
            ),
            hoverinfo="text",
            showlegend=False,
        )

    # ------------------------------------------------------------------
    # Metric comparison
    # ------------------------------------------------------------------

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

        if not formulas:
            return fig

        categories: Dict[str, list[float]] = {}
        for formula in formulas:
            categories.setdefault(formula.category, []).append(formula.r_squared)

        category_names = list(categories.keys())
        r_squared_by_category = [
            sum(values) / len(values) if values else 0.0
            for values in categories.values()
        ]

        fig.add_trace(
            go.Bar(
                name="Average R-squared",
                x=category_names,
                y=r_squared_by_category,
            )
        )

        fig.update_layout(
            title="Formula Reliability Distribution by Category",
            xaxis_title="Formula Category",
            yaxis_title="R-Squared Score",
            showlegend=False,
            template="plotly_white",
        )

        return fig
