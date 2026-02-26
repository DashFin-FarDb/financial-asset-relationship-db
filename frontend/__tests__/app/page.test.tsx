/**
 * Unit tests for the main page component.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import Home from "../../app/page";
import { api } from "../../app/lib/api";

jest.mock("../../app/lib/api");
jest.mock("../../app/components/NetworkVisualization", () => {
  return function MockVisualization() {
    return <div data-testid="network-visualization">Visualization</div>;
  };
});
jest.mock("../../app/components/MetricsDashboard", () => {
  return function MockMetrics() {
    return <div data-testid="metrics-dashboard">Metrics</div>;
  };
});
jest.mock("../../app/components/AssetList", () => {
  return function MockAssetList() {
    return <div data-testid="asset-list">Assets</div>;
  };
});

const mockedApi = api as jest.Mocked<typeof api>;

describe("Home Page", () => {
  const mockMetrics = {
    total_assets: 15,
    total_relationships: 42,
    asset_classes: { EQUITY: 6 },
    avg_degree: 5.6,
    max_degree: 12,
    network_density: 0.42,
  };

  const mockVizData = {
    nodes: [],
    edges: [],
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.getMetrics.mockResolvedValue(mockMetrics);
    mockedApi.getVisualizationData.mockResolvedValue(mockVizData);
  });

  it("should render header", async () => {
    render(<Home />);
    expect(
      screen.getByText(/Financial Asset Relationship Network/i),
    ).toBeInTheDocument();
  });

  it("should render navigation tabs", async () => {
    render(<Home />);
    expect(screen.getByText("3D Visualization")).toBeInTheDocument();
    expect(screen.getByText("Metrics & Analytics")).toBeInTheDocument();
    expect(screen.getByText("Asset Explorer")).toBeInTheDocument();
  });

  it("should load data on mount", async () => {
    render(<Home />);

    await waitFor(() => {
      expect(mockedApi.getMetrics).toHaveBeenCalled();
      expect(mockedApi.getVisualizationData).toHaveBeenCalled();
    });
  });

  it("should show loading state", () => {
    render(<Home />);
    expect(screen.getByText("Loading data...")).toBeInTheDocument();
  });

  it("should switch tabs", async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Metrics & Analytics"));
    expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Asset Explorer"));
    expect(screen.getByTestId("asset-list")).toBeInTheDocument();
  });

  it("should handle API errors", async () => {
    const consoleError = jest.spyOn(console, "error").mockImplementation();
    mockedApi.getMetrics.mockRejectedValue(new Error("API Error"));

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
    });

    consoleError.mockRestore();
  });

  it("should allow retry after error", async () => {
    mockedApi.getMetrics.mockRejectedValueOnce(new Error("API Error"));
    mockedApi.getMetrics.mockResolvedValueOnce(mockMetrics);

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
    });

    const retryButton = screen.getByText("Retry");
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(mockedApi.getMetrics).toHaveBeenCalledTimes(2);
    });
  });
});
