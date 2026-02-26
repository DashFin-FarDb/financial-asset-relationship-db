/**
 * Comprehensive unit tests for NetworkVisualization component.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import NetworkVisualization from "../../app/components/NetworkVisualization";
import type { VisualizationData } from "../../app/types/api";
import { mockVisualizationData } from "../test-utils";

jest.mock("react-plotly.js", () => {
  return function MockPlot({ data }: { data: unknown }) {
    return (
      <div data-testid="mock-plot">
        <div data-testid="plot-data">{JSON.stringify(data)}</div>
      </div>
    );
  };
});

describe("NetworkVisualization Component", () => {
  it("should show empty data message when nodes are missing", () => {
    render(<NetworkVisualization data={{ nodes: [], edges: [] }} />);
    expect(
      screen.getByText("Visualization data is missing nodes."),
    ).toBeInTheDocument();
  });

  it("should render node-only data without showing an empty message", async () => {
    const nodeOnlyData: VisualizationData = {
      nodes: mockVisualizationData.nodes,
      edges: [],
    };

    render(<NetworkVisualization data={nodeOnlyData} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-plot")).toBeInTheDocument();
    });
  });

  it("should render plot with data", async () => {
    render(<NetworkVisualization data={mockVisualizationData} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-plot")).toBeInTheDocument();
    });
  });

  it("should process node coordinates", async () => {
    render(<NetworkVisualization data={mockVisualizationData} />);

    await waitFor(() => {
      const plotData = screen.getByTestId("plot-data");
      const data = JSON.parse(plotData.textContent || "[]");
      expect(data.length).toBeGreaterThan(0);
    });
  });

  it("should handle null data gracefully", () => {
    render(
      <NetworkVisualization data={null as unknown as VisualizationData} />,
    );
    expect(
      screen.getByText("No visualization data available."),
    ).toBeInTheDocument();
  });

  it("should update when data changes", async () => {
    const { rerender } = render(
      <NetworkVisualization data={mockVisualizationData} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("mock-plot")).toBeInTheDocument();
    });

    const newData: VisualizationData = {
      nodes: [],
      edges: [],
    };

    rerender(<NetworkVisualization data={newData} />);
    expect(
      screen.getByText("Visualization data is missing nodes."),
    ).toBeInTheDocument();
  });

  it("should show a helpful message when dataset is too large", () => {
    const bigData: VisualizationData = {
      nodes: Array.from({ length: 600 }, (_, index) => ({
        id: `NODE_${index}`,
        name: `Node ${index}`,
        symbol: `SYM${index}`,
        asset_class: "EQUITY",
        x: Math.random(),
        y: Math.random(),
        z: Math.random(),
        color: "#000000",
        size: 5,
      })),
      edges: Array.from({ length: 2001 }, (_, index) => ({
        source: "NODE_0",
        target: `NODE_${(index % 599) + 1}`,
        relationship_type: "TEST",
        strength: 0.5,
      })),
    };

    render(<NetworkVisualization data={bigData} />);

    expect(
      screen.getByText(
        /Visualization is unavailable because the dataset is too large/,
      ),
    ).toBeInTheDocument();
  });
});
