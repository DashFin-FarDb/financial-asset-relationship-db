/**
 * Comprehensive unit tests for MetricsDashboard component.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import MetricsDashboard from "../../app/components/MetricsDashboard";
import type { Metrics } from "../../app/types/api";
import { mockMetrics } from "../test-utils";

describe("MetricsDashboard Component", () => {
  it("should render all metric cards", () => {
    render(<MetricsDashboard metrics={mockMetrics} />);

    expect(screen.getByText("Total Assets")).toBeInTheDocument();
    expect(screen.getByText("Total Relationships")).toBeInTheDocument();
    expect(screen.getByText("Network Density")).toBeInTheDocument();
  });

  it("should display metrics correctly", () => {
    render(<MetricsDashboard metrics={mockMetrics} />);

    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("42.00%")).toBeInTheDocument();
  });

  it("should format network density as percentage", () => {
    render(<MetricsDashboard metrics={mockMetrics} />);
    expect(screen.getByText("42.00%")).toBeInTheDocument();
  });

  it("should display average degree with 2 decimals", () => {
    render(<MetricsDashboard metrics={mockMetrics} />);
    expect(screen.getByText("5.60")).toBeInTheDocument();
  });

  it("should display all asset classes", () => {
    render(<MetricsDashboard metrics={mockMetrics} />);

    expect(screen.getByText("EQUITY:")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("COMMODITY:")).toBeInTheDocument();
  });

  it("should handle zero metrics", () => {
    const zeroMetrics: Metrics = {
      total_assets: 0,
      total_relationships: 0,
      asset_classes: {},
      avg_degree: 0,
      max_degree: 0,
      network_density: 0,
    };

    render(<MetricsDashboard metrics={zeroMetrics} />);
    expect(screen.getByText("0.00%")).toBeInTheDocument();
  });
});
