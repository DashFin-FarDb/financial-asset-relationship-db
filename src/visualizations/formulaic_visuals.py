from typing import Any, Dict

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.formulaic_analysis import Formula


class FormulaicVisualizer:
    """Visualizes mathematical formulas and relationships from financial analysis."""

    def __init__(self):
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
        """Create a comprehensive dashboard showing all formulaic relationships"""
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

    def _plot_category_distribution(self, fig: go.Figure, formulas: Any) -> None:
        """Plot distribution of formulas across categories using pie and
        bar charts.
        """
        raise NotImplementedError()

    def _plot_reliability(self, fig: go.Figure, formulas: Any) -> None:
        """Plot reliability (R-squared) of formulas using pie and bar charts."""
        raise NotImplementedError()

    def _plot_empirical_correlation(
        self,
        fig: go.Figure,
        empirical_relationships: Any,
    ) -> None:
        """Plot empirical correlation matrix and corresponding bar chart of
        relationships
        """
        raise NotImplementedError()

    def _plot_asset_class_relationships(self, fig: go.Figure, formulas: Any) -> None:
        """Plot relationships between asset classes based on provided formulas."""
        raise NotImplementedError()

    def _plot_sector_analysis(self, fig: go.Figure, formulas: Any) -> None:
        """Plot sector analysis charts illustrating formula performance by sector."""
        raise NotImplementedError()

    def _plot_key_formula_examples(self, fig: go.Figure, formulas: Any) -> None:
        """Populate the "Key Formula Examples" table with the top
        formulas, sorted by reliability.
        """
        # Populate the "Key Formula Examples" table in row 3, column 2.
        # Select a subset of formulas to keep the table readable.
        if not formulas:
            return None

        sorted_formulas = self._get_sorted_formulas(formulas)
        top_formulas = sorted_formulas[:10]
        names = [self._format_name(f.name) for f in top_formulas]
        categories = [f.category for f in top_formulas]
        r_squares = [f"{f.r_squared:.3f}" for f in top_formulas]

        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Formula", "Category", "R-squared"],
                    fill_color="#f2f2f2",
                    align="left",
                ),
                cells=dict(
                    values=[names, categories, r_squares],
                    fill_color="#ffffff",
                    align="left",
                ),
            )
        )
        return None

    @staticmethod
    def _get_sorted_formulas(formulas: Any) -> list:
        """Helper to sort formulas by r_squared descending with fallback."""
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
        return name if len(name) <= max_length else name[: max_length - 3] + "..."

    @staticmethod
    def _format_r_squared(r_value: Any) -> str:
        """Format r_squared value to 4 decimal places or N/A."""
        return f"{r_value:.4f}" if isinstance(r_value, (int, float)) else "N/A"

    @staticmethod
    def _extract_formula_table_data(formulas: Any) -> tuple:
        """Helper to extract names, categories, and r-squared values for table."""
        names = [FormulaicVisualizer._format_name(getattr(f, "name", None)) for f in formulas]
        categories = [getattr(f, "category", "N/A") for f in formulas]
        r_squared_values = [FormulaicVisualizer._format_r_squared(getattr(f, "r_squared", None)) for f in formulas]
        return names, categories, r_squared_values

    @staticmethod
    def create_formula_detail_view(formula: Formula) -> go.Figure:
        """Create a detailed view of a specific formula"""
        fig = go.Figure()

        # Create a text-based visualization of the formula
        #
        fig.add_annotation(
            text=(
                f"<b>{formula.name}</b><br><br>"
                f"<b>Mathematical Expression:</b><br>"
                f"{formula.formula}<br><br>"
                f"<b>LaTeX:</b><br>"
                f"{formula.latex}<br><br>"
                f"<b>Description:</b><br>"
                f"{formula.description}<br><br>"
                f"<b>Category:</b> {formula.category}<br>"
                f"<b>Reliability (R²):</b> {formula.r_squared:.3f}<br><br>"
                "<b>Variables:</b><br>"
                + "<br>".join([f"• {var}: {desc}" for var, desc in formula.variables.items()])
                + "<br><br><b>Example Calculation:</b><br>"
                + f"{formula.example_calculation}"
            ),
            showarrow=False,
        )

    @staticmethod
    def create_correlation_network(
        empirical_relationships: Dict[str, Any],
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
    def create_metric_comparison_chart(
        analysis_results: Dict[str, Any],
    ) -> go.Figure:
        """Create a chart comparing different metrics derived from formulas."""
        fig = go.Figure()

        # Example logic: Compare theoretical vs empirical values if available
        # For now, we plot R-squared distribution by category
        formulas = analysis_results.get("formulas", [])
        if not formulas:
            return fig

        categories = {}
        for f in formulas:
            if f.category not in categories:
                categories[f.category] = []
            categories[f.category].append(f.r_squared)

        fig = go.Figure()

        # Create bar chart for each category
        category_names = list(categories.keys())
        r_squared_by_category = []
        formula_counts = []

        for category in category_names:
            category_formulas = categories[category]
            if category_formulas:
                avg_r_squared = sum(category_formulas) / len(category_formulas)
            else:
                avg_r_squared = 0.0
            r_squared_by_category.append(avg_r_squared)
            formula_counts.append(len(category_formulas))

        # R-squared bars
        fig.add_trace(
            go.Bar(
                name="Average R-squared",
                x=category_names,
                y=r_squared_by_category,
                marker=dict(color="lightcoral"),
                yaxis="y",
                offsetgroup=1,
            )
        )

        fig.update_layout(
            title="Formula Reliability Distribution by Category",
            yaxis_title="R-Squared Score",
            xaxis_title="Formula Category",
            showlegend=False,
            template="plotly_white",
        )
        return fig
