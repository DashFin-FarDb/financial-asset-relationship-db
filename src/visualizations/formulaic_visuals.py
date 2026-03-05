from typing import Any, Dict, Mapping
from numbers import Real

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.visualizations.formulaic_visuals_network import FormulaicVisualsNetworkMixin


class FormulaicVisualizer(FormulaicVisualsNetworkMixin):
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

    @staticmethod
    def _normalize_formulas(formulas: Any) -> list[Any]:
        """Return formulas as a reusable list for plotting."""
        if formulas is None:
            return []
        if isinstance(formulas, list):
            return formulas
        if isinstance(formulas, Mapping):
            return list(formulas.values())
        try:
            return list(formulas)
        except TypeError:
            return []

    @staticmethod
    def _formula_field(item: Any, field: str, default: Any = None) -> Any:
        """Read a formula field from mapping or object."""
        if isinstance(item, Mapping):
            return item.get(field, default)
        return getattr(item, field, default)

    @staticmethod
    def _float_value(value: Any, default: float = 0.0) -> float:
        """Safely parse numeric-like values to float."""
        if isinstance(value, bool):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def create_formula_dashboard(self, analysis_results: Dict[str, Any]) -> go.Figure:
        """Create a comprehensive dashboard showing all formulaic relationships."""
        formulas = self._normalize_formulas(analysis_results.get("formulas", []))
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

    # ------------------------------------------------------------------
    # Dashboard plotting methods
    # ------------------------------------------------------------------

    @staticmethod
    def _count_formulas_by_category(formulas: Any) -> dict[str, int]:
        """Return formula counts grouped by category."""
        counts: dict[str, int] = {}
        for formula in formulas:
            category = str(FormulaicVisualizer._formula_field(formula, "category", "Unknown"))
            counts[category] = counts.get(category, 0) + 1
        return counts

    @staticmethod
    def _average_r_squared_by_category(formulas: Any) -> dict[str, float]:
        """Return average r-squared grouped by category."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for formula in formulas:
            category = str(FormulaicVisualizer._formula_field(formula, "category", "Unknown"))
            r_squared = FormulaicVisualizer._float_value(
                FormulaicVisualizer._formula_field(formula, "r_squared", 0.0),
                0.0,
            )
            totals[category] = totals.get(category, 0.0) + r_squared
            counts[category] = counts.get(category, 0) + 1
        return {category: (total / counts[category] if counts[category] else 0.0) for category, total in totals.items()}

    @staticmethod
    def _add_bar_trace(
        fig: go.Figure,
        series: tuple[list[str], list[float]],
        color: str,
        subplot: tuple[int, int],
    ) -> None:
        """Add a consistent bar trace to a subplot cell."""
        x_values, y_values = series
        row, col = subplot
        fig.add_trace(
            go.Bar(
                x=x_values,
                y=y_values,
                marker={"color": color},
            ),
            row=row,
            col=col,
        )

    @staticmethod
    def _plot_category_distribution(fig: go.Figure, formulas: Any) -> None:
        """Plot distribution of formulas across categories."""
        if not formulas:
            return

        categories = FormulaicVisualizer._count_formulas_by_category(formulas)

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

        avg_r_squared = FormulaicVisualizer._average_r_squared_by_category(formulas)

        FormulaicVisualizer._add_bar_trace(
            fig,
            (list(avg_r_squared.keys()), list(avg_r_squared.values())),
            "lightcoral",
            (1, 2),
        )

    @staticmethod
    def _extract_correlation_matrix(
        empirical_relationships: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Extract a dictionary correlation matrix when present."""
        if not isinstance(empirical_relationships, dict):
            return None
        correlation_matrix = empirical_relationships.get("correlation_matrix")
        if not isinstance(correlation_matrix, dict) or not correlation_matrix:
            return None
        return correlation_matrix

    @staticmethod
    def _is_flat_correlation_matrix(correlation_matrix: Mapping[str, Any]) -> bool:
        """Detect flat pair format: {'A-B': value, ...}."""
        first_val = next(iter(correlation_matrix.values()), None)
        return isinstance(first_val, Real) and not isinstance(first_val, bool)

    @staticmethod
    def _extract_flat_correlation_assets(correlation_matrix: Mapping[str, Any]) -> list[str]:
        """Extract sorted assets from flat pair keys like 'A-B'."""
        assets_set: set[str] = set()
        for key in correlation_matrix:
            left_asset, separator, right_asset = key.partition("-")
            if separator:
                assets_set.add(left_asset)
                assets_set.add(right_asset)
        return sorted(assets_set)[:8]

    @staticmethod
    def _flat_correlation_value(
        correlation_matrix: Mapping[str, Any],
        left_asset: str,
        right_asset: str,
    ) -> float:
        """Resolve a flat correlation value for an asset pair."""
        if left_asset == right_asset:
            return 1.0
        key_forward = f"{left_asset}-{right_asset}"
        key_reverse = f"{right_asset}-{left_asset}"
        raw_value = correlation_matrix.get(key_forward, correlation_matrix.get(key_reverse, 0.0))
        return FormulaicVisualizer._float_value(raw_value, 0.0)

    @staticmethod
    def _flat_correlation_row(
        correlation_matrix: Mapping[str, Any],
        left_asset: str,
        assets: list[str],
    ) -> list[float]:
        """Build one correlation row for a given left asset."""
        return [
            FormulaicVisualizer._flat_correlation_value(correlation_matrix, left_asset, right_asset)
            for right_asset in assets
        ]

    @staticmethod
    def _build_flat_correlation_grid(
        correlation_matrix: Mapping[str, Any],
    ) -> tuple[list[str], list[list[float]]]:
        """Build assets and heatmap values from flat pairwise keys."""
        assets = FormulaicVisualizer._extract_flat_correlation_assets(correlation_matrix)
        z_values = [
            FormulaicVisualizer._flat_correlation_row(correlation_matrix, left_asset, assets) for left_asset in assets
        ]
        return assets, z_values

    @staticmethod
    def _build_nested_correlation_grid(
        correlation_matrix: Mapping[str, Any],
    ) -> tuple[list[str], list[list[float]]]:
        """Build assets and heatmap values from nested matrix keys."""
        assets = sorted(correlation_matrix.keys())[:8]
        z_values = [[correlation_matrix.get(a1, {}).get(a2, 0.0) for a2 in assets] for a1 in assets]
        return assets, z_values

    @staticmethod
    def _add_correlation_heatmap(fig: go.Figure, assets: list[str], z_values: list[list[float]]) -> None:
        """Add correlation heatmap trace to row 2, col 1."""
        if not assets:
            return
        fig.add_trace(
            go.Heatmap(
                z=z_values,
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
        if correlation_matrix is None:
            return

        if FormulaicVisualizer._is_flat_correlation_matrix(correlation_matrix):
            assets, z_values = FormulaicVisualizer._build_flat_correlation_grid(correlation_matrix)
        else:
            assets, z_values = FormulaicVisualizer._build_nested_correlation_grid(correlation_matrix)
        FormulaicVisualizer._add_correlation_heatmap(fig, assets, z_values)

    @staticmethod
    def _plot_asset_class_relationships(fig: go.Figure, formulas: Any) -> None:
        """Plot relationships between asset classes."""
        if not formulas:
            return

        categories = FormulaicVisualizer._count_formulas_by_category(formulas)

        FormulaicVisualizer._add_bar_trace(
            fig,
            (list(categories.keys()), [float(v) for v in categories.values()]),
            "lightgreen",
            (2, 2),
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

        sector_performance = FormulaicVisualizer._average_r_squared_by_category(formulas)

        FormulaicVisualizer._add_bar_trace(
            fig,
            (list(sector_performance.keys()), list(sector_performance.values())),
            "lightblue",
            (3, 1),
        )

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def _plot_key_formula_examples(self, fig: go.Figure, formulas: Any) -> None:
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
        formulas_list = FormulaicVisualizer._normalize_formulas(formulas)
        return sorted(
            formulas_list,
            key=lambda f: FormulaicVisualizer._float_value(
                FormulaicVisualizer._formula_field(f, "r_squared", float("-inf")),
                float("-inf"),
            ),
            reverse=True,
        )

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
        names: list[str] = []
        categories: list[str] = []
        r_squared_values: list[str] = []
        for formula in FormulaicVisualizer._normalize_formulas(formulas):
            names.append(FormulaicVisualizer._format_name(FormulaicVisualizer._formula_field(formula, "name", None)))
            categories.append(str(FormulaicVisualizer._formula_field(formula, "category", "N/A")))
            r_squared_values.append(
                FormulaicVisualizer._format_r_squared(FormulaicVisualizer._formula_field(formula, "r_squared", None))
            )
        return names, categories, r_squared_values
