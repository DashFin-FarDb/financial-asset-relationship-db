from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple

import gradio as gr
import pandas as pd

from src.constants import AppConstants
from src.formulaic import FormulaicVisualizer
from src.graph_builder import GraphBuilder
from src.visualization import (
    visualize_2d_graph,
    visualize_3d_graph_with_filters,
)


class FinancialAssetApp:
    """Gradio application for financial asset relationship visualization."""

    def __init__(self) -> None:
        self.graph_builder = GraphBuilder()
        self.formulaic_visualizer = FormulaicVisualizer()
        self._graph = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def ensure_graph(self):
        if self._graph is None:
            self._graph = self.graph_builder.build_graph()
        return self._graph

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def refresh_visualization(
        self,
        view_mode: str,
        layout_type: str,
        min_weight: float,
        show_labels: bool,
    ):
        """Refresh the network visualization based on UI controls."""
        try:
            graph = self.ensure_graph()

            if view_mode == "2D":
                graph_fig = visualize_2d_graph(
                    graph=graph,
                    layout=layout_type,
                    min_weight=min_weight,
                    show_labels=show_labels,
                )
            else:
                graph_fig = visualize_3d_graph_with_filters(
                    graph=graph,
                    layout=layout_type,
                    min_weight=min_weight,
                    show_labels=show_labels,
                )

            return graph_fig, gr.update(visible=False)

        except Exception as exc:  # noqa: BLE001
            return (
                gr.Markdown(f"❌ Error generating visualization: {exc}"),
                gr.update(visible=True),
            )

    def generate_formulaic_analysis(
        self,
        selected_assets: list[str],
        metric: str,
        lookback_days: int,
    ):
        """Generate dashboard and analytical plots."""
        try:
            analysis_results = self.formulaic_visualizer.run_analysis(
                assets=selected_assets,
                metric=metric,
                lookback_days=lookback_days,
            )

            dashboard_fig = self.formulaic_visualizer.create_formula_dashboard(
                analysis_results
            )
            correlation_network_fig = (
                self.formulaic_visualizer.create_correlation_network(analysis_results)
            )
            metric_comparison_fig = self.formulaic_visualizer.create_metric_comparison(
                analysis_results
            )

            summary_text = analysis_results.summary

            return (
                dashboard_fig,
                correlation_network_fig,
                metric_comparison_fig,
                gr.update(visible=True),
                summary_text,
                gr.update(visible=False),
            )

        except Exception as exc:  # noqa: BLE001
            return (
                None,
                None,
                None,
                gr.update(visible=False),
                f"❌ Analysis failed: {exc}",
                gr.update(visible=True),
            )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def build_ui(self) -> gr.Blocks:
        """Construct and return the Gradio UI."""
        with gr.Blocks(title=AppConstants.TITLE) as demo:
            gr.Markdown(f"# {AppConstants.TITLE}")
            gr.Markdown(AppConstants.DESCRIPTION)

            with gr.Tabs():
                # ------------------------------------------------------
                # Network visualization tab
                # ------------------------------------------------------
                with gr.Tab("Network Visualization"):
                    with gr.Row():
                        view_mode = gr.Radio(
                            ["2D", "3D"],
                            value="2D",
                            label="View Mode",
                        )
                        layout_type = gr.Dropdown(
                            ["spring", "circular", "grid"],
                            value="spring",
                            label="Layout",
                        )

                    min_weight = gr.Slider(
                        0.0,
                        1.0,
                        value=0.1,
                        step=0.01,
                        label="Minimum Relationship Weight",
                    )
                    show_labels = gr.Checkbox(
                        value=True,
                        label="Show Node Labels",
                    )

                    refresh_btn = gr.Button("Refresh Visualization")

                    graph_output = gr.Plot()
                    error_box = gr.Markdown(visible=False)

                    refresh_btn.click(
                        fn=self.refresh_visualization,
                        inputs=[
                            view_mode,
                            layout_type,
                            min_weight,
                            show_labels,
                        ],
                        outputs=[
                            graph_output,
                            error_box,
                        ],
                    )

                # ------------------------------------------------------
                # Formulaic analysis tab
                # ------------------------------------------------------
                with gr.Tab("Formulaic Analysis"):
                    assets = gr.Dropdown(
                        choices=self.graph_builder.available_assets(),
                        multiselect=True,
                        label="Assets",
                    )
                    metric = gr.Dropdown(
                        ["returns", "volatility", "correlation"],
                        value="returns",
                        label="Metric",
                    )
                    lookback = gr.Slider(
                        30,
                        365,
                        value=90,
                        step=1,
                        label="Lookback Days",
                    )

                    analyze_btn = gr.Button("Run Analysis")

                    dashboard_plot = gr.Plot()
                    correlation_plot = gr.Plot()
                    comparison_plot = gr.Plot()

                    summary_md = gr.Markdown(visible=False)
                    error_md = gr.Markdown(visible=False)

                    analyze_btn.click(
                        fn=self.generate_formulaic_analysis,
                        inputs=[
                            assets,
                            metric,
                            lookback,
                        ],
                        outputs=[
                            dashboard_plot,
                            correlation_plot,
                            comparison_plot,
                            summary_md,
                            summary_md,
                            error_md,
                        ],
                    )

        return demo


def create_app() -> gr.Blocks:
    """Application entry point."""
    app = FinancialAssetApp()
    return app.build_ui()
