"""Visualization helpers for formulaic financial analysis results."""

import math
from typing import Any, Dict, Mapping

import plotly.graph_objects as go  # type: ignore[import-untyped]
from plotly.subplots import make_subplots  # type: ignore[import-untyped]

from src.analysis.formulaic_analysis import Formula


class FormulaicVisualizer:
    """Visualize formulas and relationships from financial analysis."""

    def __init__(self) -> None:
        """
        Initialize the visualizer and set a fixed color mapping for formula categories.

        The instance attribute `color_scheme` maps canonical formula category names to hex color codes used consistently across all charts in the visualizer:

        - "Valuation": "#FF6B6B"
        - "Income": "#4ECDC4"
        - "Fixed Income": "#45B7D1"
        - "Risk Management": "#96CEB4"
        - "Portfolio Theory": "#FFEAA7"
        - "Statistical Analysis": "#DDA0DD"
        - "Currency Markets": "#98D8C8"
        - "Cross-Asset": "#F7DC6F"
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

    def create_formula_dashboard(
        self,
        analysis_results: Dict[str, Any],
    ) -> go.Figure:
        """
        Create a multi-panel Plotly dashboard visualizing formula analysis results.

        Parameters:
            analysis_results (Dict[str, Any]): Analysis payload expected to contain:
                - "formulas": an iterable of formula-like objects (with attributes such as
                  `name`, `category`, and `r_squared`) used to populate category, reliability,
                  sector, and example tables.
                - "empirical_relationships": a mapping that may include correlation data
                  (e.g., a "correlation_matrix" or "strongest_correlations") used for the
                  empirical correlation heatmap and correlation network.

        Returns:
            go.Figure: A Plotly Figure containing a 3x2 dashboard of visualizations:
                category distribution, reliability by category, empirical correlation heatmap,
                asset-class relationship counts, sector reliability, and key formula examples.
        """
        formulas = analysis_results.get("formulas", [])
        empirical_relationships = analysis_results.get(
            "empirical_relationships",
            {},
        )

        # Pre-aggregate formula statistics to prevent redundant iterations
        category_stats = self._aggregate_category_stats(formulas)

        fig = self._initialize_dashboard_figure()

        self._plot_category_distribution(fig, category_stats)
        self._plot_reliability(fig, category_stats)
        self._plot_empirical_correlation(fig, empirical_relationships)
        self._plot_asset_class_relationships(fig, category_stats)
        self._plot_sector_analysis(fig, category_stats)
        self._plot_key_formula_examples(fig, formulas)

        self._apply_dashboard_layout(fig)

        return fig

    @staticmethod
    def _initialize_dashboard_figure() -> go.Figure:
        """
        Create and return a pre-configured 3x2 subplot Figure for the formula dashboard.

        The figure contains titled subplots arranged as:
        - Row 1: pie, bar
        - Row 2: heatmap, bar
        - Row 3: bar, table
        Spacing and subplot titles are set to match the dashboard layout.

        Returns:
            go.Figure: A Plotly Figure with the dashboard subplot grid and layout specs.
        """
        return make_subplots(
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

    @staticmethod
    def _apply_dashboard_layout(fig: go.Figure) -> None:
        """Apply final layout configurations to the dashboard figure."""
        fig.update_layout(
            title="📊 Financial Formulaic Analysis Dashboard",
            height=1000,
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="#F8F9FA",
        )

    # ------------------------------------------------------------------
    # Dashboard plotting methods
    # ------------------------------------------------------------------

    def _aggregate_category_stats(self, formulas: Any) -> Dict[str, Dict[str, float]]:
        """
        Aggregate formula counts and average R-squared grouped by category.

        For each formula, the category is read from its `category` attribute (defaults to "Unknown" when missing or falsy)
        and the R-squared value is read from its `r_squared` attribute (defaults to 0.0 when missing or non-convertible).
        Returns a mapping from category name to a dictionary containing:
        - `count` (float): number of formulas in the category,
        - `total_r2` (float): sum of R-squared values for the category,
        - `avg_r2` (float): average R-squared for the category (0.0 if count is zero).

        Parameters:
            formulas (Any): An iterable of objects (or dict-like) that may have `category` and `r_squared` attributes.

        Returns:
            Dict[str, Dict[str, float]]: Per-category statistics with keys `count`, `total_r2`, and `avg_r2`.
        """
        stats: Dict[str, Dict[str, float]] = {}
        if not formulas:
            return stats

        for formula in formulas:
            cat = getattr(formula, "category", None) or "Unknown"
            r2 = getattr(formula, "r_squared", 0.0) or 0.0
            if cat not in stats:
                stats[cat] = {"count": 0.0, "total_r2": 0.0}
            stats[cat]["count"] += 1.0
            stats[cat]["total_r2"] += r2

        for data in stats.values():
            data["avg_r2"] = data["total_r2"] / data["count"] if data["count"] > 0 else 0.0

        return stats

    def _plot_category_distribution(self, fig: go.Figure, category_stats: Dict[str, Dict[str, float]]) -> None:
        """
        Render a pie chart showing formula counts by category into the provided Plotly figure.

        Parameters:
            fig (go.Figure): The target Plotly figure to which the pie trace will be added.
            category_stats (Dict[str, Dict[str, float]]): Mapping from category name to a stats dictionary; each stats dictionary must include a numeric "count" used as the slice size.
        """
        if not category_stats:
            return

        categories = list(category_stats.keys())
        counts = [data["count"] for data in category_stats.values()]
        colors = [self.color_scheme.get(cat, "#888888") for cat in categories]

        fig.add_trace(
            go.Pie(
                labels=categories,
                values=counts,
                hole=0.4,
                marker={"colors": colors},
            ),
            row=1,
            col=1,
        )

    def _plot_reliability(self, fig: go.Figure, category_stats: Dict[str, Dict[str, float]]) -> None:
        """
        Plot average R-squared per formula category as a bar chart in the dashboard subplot (row 1, col 2).

        Parameters:
            fig (go.Figure): Figure to which the bar trace will be added.
            category_stats (Dict[str, Dict[str, float]]): Mapping of category name to statistics; each value must include an 'avg_r2' numeric entry used for bar heights.
        """
        if not category_stats:
            return

        categories = list(category_stats.keys())
        avgs = [data["avg_r2"] for data in category_stats.values()]
        colors = [self.color_scheme.get(cat, "#888888") for cat in categories]

        fig.add_trace(
            go.Bar(
                x=categories,
                y=avgs,
                marker={"color": colors},
            ),
            row=1,
            col=2,
        )

    @staticmethod
    def _plot_empirical_correlation(
        fig: go.Figure,
        empirical_relationships: Mapping[str, Any],
    ) -> None:
        """
        Add an empirical correlation heatmap to the provided subplot
        figure when a valid correlation matrix is available.

        If ``empirical_relationships`` contains a
        ``correlation_matrix`` mapping of asset names to numeric
        correlations, this function adds a heatmap trace to row 2,
        column 1 showing correlations for the ordered asset list. If
        no valid correlation matrix is present, the function returns
        without modifying the figure.

        Parameters:
            fig (go.Figure): The Plotly Figure (with subplots) to
                receive the heatmap trace.
            empirical_relationships (Mapping[str, Any]): Mapping
                expected to contain a "correlation_matrix" key whose
                value is a dict mapping asset names to dictionaries
                of asset-to-correlation values.
        """
        correlation_matrix = FormulaicVisualizer._extract_correlation_matrix(empirical_relationships)
        if not correlation_matrix:
            return

        assets, z = FormulaicVisualizer._build_correlation_grid(correlation_matrix)
        if not assets:
            return

        fig.add_trace(
            go.Heatmap(
                z=z,
                x=assets,
                y=assets,
                colorscale="RdYlBu_r",
                zmin=-1,
                zmax=1,
            ),
            row=2,
            col=1,
        )

    @staticmethod
    def _extract_correlation_matrix(
        empirical_relationships: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """
        Retrieve the `correlation_matrix` mapping from an empirical relationships mapping.

        Returns:
            The `correlation_matrix` dictionary if present and is a mapping, otherwise an empty dict.
        """
        if not isinstance(empirical_relationships, dict):
            return {}
        matrix = empirical_relationships.get("correlation_matrix")
        return matrix if isinstance(matrix, dict) else {}

    @staticmethod
    def _build_correlation_grid(
        correlation_matrix: Mapping[str, Any],
    ) -> tuple[list[str], list[list[float]]]:
        """
        Build an ordered list of asset identifiers and a numeric correlation grid for heatmap rendering.

        Returns:
            tuple[list[str], list[list[float]]]: A pair where the first element is the ordered list of asset IDs (limited to at most 8) and the second is a square numeric matrix (rows correspond to the first list) containing correlation values as floats.
        """
        first_val = next(iter(correlation_matrix.values()), None)
        if isinstance(first_val, (int, float)):
            return FormulaicVisualizer._build_flat_correlation_grid(correlation_matrix)
        return FormulaicVisualizer._build_nested_correlation_grid(correlation_matrix)

    @staticmethod
    def _build_flat_correlation_grid(
        correlation_matrix: Mapping[str, Any],
    ) -> tuple[list[str], list[list[float]]]:
        """
        Constructs ordered asset labels and a 2D correlation grid suitable for a heatmap from a flat pair-keyed correlation mapping.

        Parameters:
            correlation_matrix (Mapping[str, Any]): Mapping whose keys are pair-keys in the form "SOURCE-TARGET" and whose values are numeric correlations.

        Returns:
            tuple[list[str], list[list[float]]]: A tuple (assets, z) where `assets` is an ordered list of asset identifiers (up to eight) and `z` is a square numeric matrix (list of rows) such that z[i][j] is the correlation value between assets[i] and assets[j].
        """
        assets = FormulaicVisualizer._collect_flat_assets(correlation_matrix)
        z = [
            FormulaicVisualizer._build_flat_correlation_row(
                source,
                assets,
                correlation_matrix,
            )
            for source in assets
        ]
        return assets, z

    @staticmethod
    def _collect_flat_assets(correlation_matrix: Mapping[str, Any]) -> list[str]:
        """
        Collect unique asset identifiers from a flat pair-keyed correlation mapping.

        Parameters:
            correlation_matrix (Mapping[str, Any]): Mapping whose keys encode asset pairs in the form "SOURCE-TARGET".

        Returns:
            list[str]: Sorted list of unique asset IDs extracted from valid pair keys, limited to at most 8 entries.
        """
        assets_set: set[str] = set()
        for key in correlation_matrix:
            source, target = FormulaicVisualizer._split_pair_key(key)
            if source and target:
                assets_set.add(source)
                assets_set.add(target)
        return sorted(assets_set)[:8]

    @staticmethod
    def _build_flat_correlation_row(
        source: str,
        assets: list[str],
        correlation_matrix: Mapping[str, Any],
    ) -> list[float]:
        """
        Builds a row of correlation values for a source asset aligned with an ordered list of target assets.

        Parameters:
            source (str): Asset identifier used as the row source.
            assets (list[str]): Ordered list of asset identifiers defining the column order.
            correlation_matrix (Mapping[str, Any]): Mapping containing pair-keyed correlation values; missing or invalid entries are treated as absent.

        Returns:
            list[float]: Correlation values in the same order as `assets`. The value for `source` vs itself is `1.0`; missing or non-numeric correlations are returned as `0.0`.
        """
        return [
            FormulaicVisualizer._flat_correlation_value(
                source,
                target,
                correlation_matrix,
            )
            for target in assets
        ]

    @staticmethod
    def _flat_correlation_value(
        source: str,
        target: str,
        correlation_matrix: Mapping[str, Any],
    ) -> float:
        """
        Get the correlation coefficient for an asset pair, treating the pair as unordered.

        Parameters:
            source (str): Source asset identifier.
            target (str): Target asset identifier.
            correlation_matrix (Mapping[str, Any]): Mapping of pair keys (e.g., "ASSET1-ASSET2") to numeric correlation values.

        Returns:
            float: Correlation value for the pair; returns 1.0 when source equals target, 0.0 if no entry exists for either ordering, otherwise the mapped value converted to float.
        """
        if source == target:
            return 1.0
        key1 = f"{source}-{target}"
        key2 = f"{target}-{source}"
        raw = correlation_matrix.get(key1, correlation_matrix.get(key2, 0.0))
        return FormulaicVisualizer._to_float(raw)

    @staticmethod
    def _split_pair_key(key: str) -> tuple[str, str]:
        """
        Split a string of the form "SOURCE-TARGET" into (source, target).

        Parameters:
            key (str): The input pair key expected to contain a hyphen separator.

        Returns:
            tuple[str, str]: A (source, target) pair extracted by splitting at the first hyphen;
            returns ("", "") if no hyphen is present.
        """
        if "-" not in key:
            return "", ""
        source, target = key.split("-", 1)
        return source, target

    @staticmethod
    def _build_nested_correlation_grid(
        correlation_matrix: Mapping[str, Any],
    ) -> tuple[list[str], list[list[float]]]:
        """
        Builds a square correlation grid from a nested mapping of asset → (asset → correlation).

        Parameters:
            correlation_matrix (Mapping[str, Any]): Mapping where each key is an asset id and each value is a mapping
                from target asset id to correlation value. Non-dict values are treated as empty mappings.

        Returns:
            tuple[list[str], list[list[float]]]: A tuple (assets, z) where `assets` is a sorted list of up to 8 asset ids,
            and `z` is a list of rows (one per asset in `assets`) containing float correlation values aligned to `assets`.
            Missing or invalid entries are converted to 0.0.
        """
        assets = sorted(correlation_matrix.keys())[:8]
        z: list[list[float]] = []
        for source in assets:
            source_map = correlation_matrix.get(source, {})
            source_map = source_map if isinstance(source_map, dict) else {}
            row = [FormulaicVisualizer._to_float(source_map.get(target, 0.0)) for target in assets]
            z.append(row)
        return assets, z

    @staticmethod
    def _to_float(value: Any) -> float:
        """Safely coerce input values to float."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _plot_asset_class_relationships(self, fig: go.Figure, category_stats: Dict[str, Dict[str, float]]) -> None:
        """
        Add a bar chart of formula counts per category to the provided Plotly figure.

        This modifies the given figure by adding a bar trace to subplot row 2, column 2 where each bar represents the number of formulas in a category. Bar colors are taken from the instance's color_scheme with a gray fallback.

        Parameters:
            fig (go.Figure): The Plotly figure to which the bar trace will be added.
            category_stats (Dict[str, Dict[str, float]]): Mapping from category name to stats dict; each dict must contain a numeric 'count' entry used as the bar height.
        """
        if not category_stats:
            return

        categories = list(category_stats.keys())
        counts = [data["count"] for data in category_stats.values()]
        colors = [self.color_scheme.get(cat, "#888888") for cat in categories]

        fig.add_trace(
            go.Bar(
                x=categories,
                y=counts,
                marker={"color": colors},
            ),
            row=2,
            col=2,
        )

    def _plot_sector_analysis(self, fig: go.Figure, category_stats: Dict[str, Dict[str, float]]) -> None:
        """
        Visualizes average R-squared by formula category as a bar chart and
        adds it to the dashboard.

        Parameters:
            fig (go.Figure): Plotly Figure containing
                the subplot grid where the
                bar trace will be added (row 3, col 1).
            category_stats (Dict[str, Dict[str, float]]): Pre-aggregated
                statistics per category containing 'avg_r2' values.
        """
        if not category_stats:
            return

        categories = list(category_stats.keys())
        avgs = [data["avg_r2"] for data in category_stats.values()]
        colors = [self.color_scheme.get(cat, "#888888") for cat in categories]

        fig.add_trace(
            go.Bar(
                x=categories,
                y=avgs,
                marker={"color": colors},
            ),
            row=3,
            col=1,
        )

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def _plot_key_formula_examples(
        self,
        fig: go.Figure,
        formulas: Any,
    ) -> None:
        """
        Add a "Key Formula Examples" table to the figure showing the
        top 10 formulas ranked by R-squared.

        The table is placed at row 3, column 2 and lists each formula's
        name, category, and formatted R-squared.
        If `formulas` is falsy, no trace is added.

        Parameters:
            fig (go.Figure): Plotly Figure with a subplot grid to which
                the table trace will be added.
            formulas (Any): Iterable of formula objects or mappings;
                items should provide `name`, `category`, and `r_squared`
                (missing or invalid fields are handled).
        """
        if not formulas:
            return

        sorted_formulas = self._get_sorted_formulas(formulas)
        top_formulas = sorted_formulas[:10]

        names, categories, r_squared_values = self._extract_formula_table_data(top_formulas)

        fig.add_trace(
            go.Table(
                header={
                    "values": ["Formula", "Category", "R-squared"],
                    "fill_color": "#f2f2f2",
                    "align": "left",
                },
                cells={
                    "values": [names, categories, r_squared_values],
                    "fill_color": "#ffffff",
                    "align": "left",
                },
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
                    from which `name`, `category`, and
                    `r_squared` attributes are read.
                    Missing values are handled gracefully.

        Returns:
                tuple[list[str], list[str], list[str]]: Three lists in order:
                        - names: Display-ready formula names
                            (truncated with ellipsis when long or
                             "N/A" if unavailable).
                        - categories: Formula category strings
                            or "N/A" if missing.
                        - r_squared_values: R-squared values formatted as
                            strings (four decimals) or "N/A" if not numeric.
        """
        names = [FormulaicVisualizer._format_name(getattr(f, "name", None)) for f in formulas]
        categories = [getattr(f, "category", "N/A") for f in formulas]
        r_squared_values = [FormulaicVisualizer._format_r_squared(getattr(f, "r_squared", None)) for f in formulas]
        return names, categories, r_squared_values

    # ------------------------------------------------------------------
    # Detail & comparison views
    # ------------------------------------------------------------------

    @staticmethod
    def create_formula_detail_view(formula: Formula) -> go.Figure:
        """
        Builds an annotated Plotly figure
        presenting full details for a Formula.

        The figure contains a single annotation that displays the formula's
        mathematical expression, LaTeX representation, descriptive text,
        category, R² reliability, variables with descriptions, and an example
        calculation.

        Parameters:
            formula (Formula): The formula object to render;
                expected to provide
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
                + ("<br>".join(f"• {var}: {desc}" for var, desc in formula.variables.items()))
                + "<br><br><b>Example Calculation:</b><br>"
                f"{formula.example_calculation}"
            ),
            showarrow=False,
        )

        fig.update_layout(
            title=f"Formula Details: {formula.name}",
            height=600,
            plot_bgcolor="white",
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
            empirical_relationships (Mapping[str, Any]):
                Mapping that may include:
                - "strongest_correlations": an iterable of
                  correlation items (each item can be a dict or sequence
                  describing an asset pair and their correlation value).
                - "correlation_matrix": optional matrix or mapping of pairwise
                  correlations used for reference or weighting.

        Returns:
            go.Figure: A Plotly Figure showing a network of the
                strongest asset correlations, or an empty placeholder Figure
                with an explanatory title when no strongest correlations are
                provided.
        """
        strongest_correlations = empirical_relationships.get("strongest_correlations", [])
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})

        if not strongest_correlations:
            return FormulaicVisualizer._create_empty_correlation_figure()

        return FormulaicVisualizer._build_and_render_correlation_network(
            strongest_correlations,
            correlation_matrix,
        )

    @staticmethod
    def _create_empty_correlation_figure() -> go.Figure:
        """Return an empty placeholder correlation figure."""
        fig = go.Figure()
        fig.add_annotation(
            text="No correlation data available",
            showarrow=False,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
        )
        fig.update_layout(title="No Correlation Data")
        return fig

    @staticmethod
    def _build_and_render_correlation_network(
        strongest_correlations: Any,
        _correlation_matrix: Any,
    ) -> go.Figure:
        """
        Builds and returns a Plotly network figure showing the strongest asset correlations.

        Processes up to the first 10 correlation items from `strongest_correlations`, extracts unique asset identifiers, places nodes on a circle, and draws edges for each correlation; if no valid assets are found, returns a figure titled "No valid asset correlations found".

        Parameters:
            strongest_correlations (Any): Iterable of correlation items (dicts or sequences) describing pairwise relationships. Each item should encode two asset identifiers and an optional correlation value.
            _correlation_matrix (Any): Optional full correlation matrix provided for context or future use; currently ignored by this function.

        Returns:
            go.Figure: A Plotly Figure containing edge traces and a node trace representing the asset correlation network, or a Figure titled "No valid asset correlations found" when no assets could be extracted.
        """
        top_correlations = (
            strongest_correlations[:10]
            if isinstance(strongest_correlations, (list, tuple))
            else list(strongest_correlations)[:10]
        )

        assets = FormulaicVisualizer._extract_assets_from_correlations(top_correlations)
        if not assets:
            fig = go.Figure()
            fig.update_layout(title="No valid asset correlations found")
            return fig

        positions = FormulaicVisualizer._create_circular_positions(assets)
        edge_traces = FormulaicVisualizer._create_edge_traces(top_correlations, positions)
        node_trace = FormulaicVisualizer._create_node_trace(assets, positions)

        fig = go.Figure(data=edge_traces + [node_trace])
        fig.update_layout(
            title="Asset Correlation Network",
            showlegend=False,
            hovermode="closest",
            xaxis={
                "showgrid": False,
                "zeroline": False,
                "showticklabels": False,
            },
            yaxis={
                "showgrid": False,
                "zeroline": False,
                "showticklabels": False,
            },
        )
        return fig

    @staticmethod
    def _extract_assets_from_correlations(correlations: Any) -> list[str]:
        """Extract unique sorted assets from correlation data."""
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
        """Parse a correlation item into (asset1, asset2, value)."""
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
        Compute evenly spaced coordinates on the unit circle for each asset.

        Positions start at angle 0 (point (1.0, 0.0)) and proceed
        counterclockwise, placing assets evenly by index.

        Parameters:
            assets (list[str]): Ordered list of asset identifiers.

        Returns:
            Dict[str, tuple[float, float]]:
                Mapping from asset identifier to its (x, y)
                coordinate on the unit circle.
        """
        n = len(assets)
        positions = {}
        for i, asset in enumerate(assets):
            angle = 2 * math.pi * i / n
            positions[asset] = (math.cos(angle), math.sin(angle))
        return positions

    @staticmethod
    def _create_edge_traces(
        correlations: Any,
        positions: Dict[str, tuple[float, float]],
    ) -> list[go.Scatter]:
        """
        Builds Plotly line traces for correlations between positioned assets.

        Parameters:
            correlations (Any):
                An iterable of correlation items; each item should provide two asset identifiers and a numeric correlation value.
            positions (Dict[str, tuple[float, float]]):
                Mapping from asset identifier to (x, y) coordinates used to place nodes.

        Returns:
            list[go.Scatter]: Scatter traces for each correlation where both assets have defined positions.
        """
        edge_traces = []
        if not isinstance(correlations, (list, tuple)):
            return []
        for corr in correlations:
            asset1, asset2, value = FormulaicVisualizer._parse_correlation_item(corr)
            if asset1 in positions and asset2 in positions:
                trace = FormulaicVisualizer._create_single_edge_trace(asset1, asset2, value, positions)
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
        Create a Plotly line trace that visualizes the correlation between two assets.

        The trace connects the provided asset coordinates; line color is red for negative correlations and green for zero-or-positive correlations, and line width scales as max(1, abs(value) * 5). Hover text shows "asset1 - asset2: value" with the value formatted to three decimals.

        Parameters:
            asset1 (str): Identifier of the first asset.
            asset2 (str): Identifier of the second asset.
            value (float): Correlation value between the two assets; sign controls color and magnitude controls width.
            positions (Dict[str, tuple[float, float]]): Mapping from asset identifiers to (x, y) coordinates.

        Returns:
            go.Scatter: A Plotly line trace connecting the two asset positions with color and width reflecting the correlation value.
        """
        x0, y0 = positions[asset1]
        x1, y1 = positions[asset2]
        color = "red" if value < 0 else "green"
        width = max(1, abs(value) * 5)

        return go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line={"color": color, "width": width},
            hoverinfo="text",
            text=f"{asset1} - {asset2}: {value:.3f}",
            showlegend=False,
        )

    @staticmethod
    def _create_node_trace(
        assets: list[str],
        positions: Dict[str, tuple[float, float]],
    ) -> go.Scatter:
        """
        Create a Plotly scatter trace representing
        asset nodes positioned on a plane.

        Each asset is rendered as a labeled marker placed at the
        (x, y) coordinates from `positions`; markers include hover text and
        display the asset name above the marker.

        Parameters:
            assets (list[str]): Ordered list of
                asset names to include in the trace.
            positions (Dict[str, tuple[float, float]]):
                Mapping from asset name to its
                (x, y) coordinates.

        Returns:
            go.Scatter: A Scatter trace with markers and text labels
                for the provided assets.
        """
        node_x = [positions[asset][0] for asset in assets]
        node_y = [positions[asset][1] for asset in assets]

        return go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=assets,
            textposition="top center",
            marker={
                "size": 20,
                "color": "lightblue",
                "line": {
                    "color": "black",
                    "width": 2,
                },
            },
            hoverinfo="text",
            showlegend=False,
        )

    # ------------------------------------------------------------------
    # Metric comparison
    # ------------------------------------------------------------------

    def create_metric_comparison_chart(
        self,
        analysis_results: Dict[str, Any],
    ) -> go.Figure:
        """
        Create a grouped bar chart comparing formula reliability and prevalence by category.

        Parameters:
            analysis_results (Dict[str, Any]): Analysis output that may include a "formulas"
                key with an iterable of Formula-like objects. Each item should expose
                a `category` attribute and an `r_squared` attribute or property.

        Returns:
            go.Figure: A Plotly Figure containing two grouped bar traces:
                - "Average R-squared" (per category)
                - "Formula Count" (per category).
                Returns an empty Figure if no formulas are present.
        """
        formulas = analysis_results.get("formulas", [])
        fig = go.Figure()

        if not formulas:
            return fig

        stats = self._aggregate_category_stats(formulas)
        category_names = list(stats.keys())
        r_squared_by_category = [data["avg_r2"] for data in stats.values()]
        count_by_category = [data["count"] for data in stats.values()]
        colors = [self.color_scheme.get(cat, "#888888") for cat in category_names]

        fig.add_trace(
            go.Bar(
                name="Average R-squared",
                x=category_names,
                y=r_squared_by_category,
                marker={"color": colors},
            )
        )

        fig.add_trace(
            go.Bar(
                name="Formula Count",
                x=category_names,
                y=count_by_category,
                marker={"color": colors},
            )
        )

        self._apply_metric_comparison_layout(fig)

        return fig

    @staticmethod
    def _apply_metric_comparison_layout(fig: go.Figure) -> None:
        """
        Configure layout for the metric comparison chart.

        Sets the chart title, x/y axis labels, grouped bar mode, and the plot background color on the provided Plotly figure.
        """
        fig.update_layout(
            title="Formula Categories: Reliability vs Count",
            xaxis_title="Formula Category",
            yaxis_title="Value",
            barmode="group",
            plot_bgcolor="white",
        )
