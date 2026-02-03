from typing import Any, Dict, Mapping

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.formulaic_analysis import Formula


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

    def create_formula_dashboard(self, analysis_results: Dict[str, Any]) -> go.Figure:
        """Create a comprehensive dashboard showing all formulaic relationships."""
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
        """Plot reliability (R-squared) of formulas."""
        if not formulas:
            return

        categories = {}
        for formula in formulas:
            category = getattr(formula, "category", "Unknown")
            r_squared = getattr(formula, "r_squared", 0.0)
            if category not in categories:
                categories[category] = []
            categories[category].append(r_squared)

        avg_r_squared = {cat: sum(vals) / len(vals) if vals else 0.0 for cat, vals in categories.items()}

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
    def _plot_empirical_correlation(fig: go.Figure, empirical_relationships: Mapping[str, Any]) -> None:
        """Plot empirical correlation matrix."""
        correlation_matrix = empirical_relationships.get("correlation_matrix", {})

        if not correlation_matrix:
            return

        if isinstance(correlation_matrix, dict):
            assets = sorted(correlation_matrix.keys())
            z = [[correlation_matrix.get(a1, {}).get(a2, 0.0) for a2 in assets] for a1 in assets]
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
        """Plot relationships between asset classes."""
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
        """Plot sector analysis."""
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
            cat: data["total_r2"] / data["count"] if data["count"] > 0 else 0.0 for cat, data in categories.items()
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
        """Populate the 'Key Formula Examples' table."""
        if not formulas:
            return

        sorted_formulas = self._get_sorted_formulas(formulas)
        top_formulas = sorted_formulas[:10]

        names, categories, r_squared_values = self._extract_formula_table_data(top_formulas)

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
        """Extract table values for formula name, category, and r-squared."""
        names = [FormulaicVisualizer._format_name(getattr(f, "name", None)) for f in formulas]
        categories = [getattr(f, "category", "N/A") for f in formulas]
        r_squared_values = [FormulaicVisualizer._format_r_squared(getattr(f, "r_squared", None)) for f in formulas]
        return names, categories, r_squared_values

    # ------------------------------------------------------------------
    # Detail & comparison views
    # ------------------------------------------------------------------

    @staticmethod
    def create_formula_detail_view(formula: Formula) -> go.Figure:
        """Create a detailed view of a specific formula."""
        fig = go.Figure()

        fig.add_annotation(
            text=(
                f"<b>{formula.name}</b><br><br>"
                "<b>Mathematical Expression:</b><br>"
                f"{formula.formula}<br><br>"
                "<b>LaTeX:</b><br>"
                f"{formula.latex}<br><br>"
                "<b>Description:</b><br>"
                f"{formula.description}<br><br>"
                f"<b>Category:</b> {formula.category}<br>"
                f"<b>Reliability (R²):</b> {formula.r_squared:.3f}<br><br>"
                "<b>Variables:</b><br>"
                + "<br>".join(f"• {var}: {desc}" for var, desc in formula.variables.items())
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
        """Create a network graph showing asset correlations."""
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
        fig.update_layout(title="No correlation data available")
        return fig

    @staticmethod
    def _build_and_render_correlation_network(
        strongest_correlations: Any,
        correlation_matrix: Any,
    ) -> go.Figure:
        """Build and render a correlation network visualization."""
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
        """Create circular layout positions for assets."""
        import math

        n = len(assets)
        positions = {}
        for i, asset in enumerate(assets):
            angle = 2 * math.pi * i / n
            positions[asset] = (math.cos(angle), math.sin(angle))
        return positions

    @staticmethod
    def _create_edge_traces(correlations: Any, positions: Dict[str, tuple[float, float]]) -> list[go.Scatter]:
        """Create edge traces for all correlations."""
        edge_traces = []
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
        """Create a single edge trace between two assets."""
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
    def _create_node_trace(assets: list[str], positions: Dict[str, tuple[float, float]]) -> go.Scatter:
        """Create node trace for all assets."""
        node_x = [positions[asset][0] for asset in assets]
        node_y = [positions[asset][1] for asset in assets]

        return go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=assets,
            textposition="top center",
            marker=dict(size=20, color="lightblue", line=dict(color="black", width=2)),
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
        """Create a chart comparing different metrics derived from formulas."""
        formulas = analysis_results.get("formulas", [])
        fig = go.Figure()

        if not formulas:
            return fig

        categories: Dict[str, list[float]] = {}
        for formula in formulas:
            categories.setdefault(formula.category, []).append(formula.r_squared)

        category_names = list(categories.keys())
        r_squared_by_category = [sum(values) / len(values) if values else 0.0 for values in categories.values()]

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
