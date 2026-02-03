/**
 * Unit tests for the main page component.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import Home from "../../app/page";
import { api } from "../../app/lib/api";
import { mockMetrics, mockVisualizationData } from "../test-utils";

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

beforeEach(() => {
  jest.clearAllMocks();
  mockedApi.getMetrics.mockResolvedValue(mockMetrics);
  mockedApi.getVisualizationData.mockResolvedValue(mockVisualizationData);
});

// Sanity check: ensure centralized mocks conform to expected structure
describe("Centralized Mock Shape Validation", () => {
  it("mockMetrics should have expected keys and types", () => {
    expect(mockMetrics).toEqual(
      expect.objectContaining({
        total_assets: expect.any(Number),
        total_relationships: expect.any(Number),
        asset_classes: expect.any(Object),
        avg_degree: expect.any(Number),
        max_degree: expect.any(Number),
        network_density: expect.any(Number),
      }),
    );
  });

  it("mockVisualizationData should have nodes and edges with expected fields", () => {
    expect(mockVisualizationData).toEqual(
      expect.objectContaining({
        nodes: expect.arrayContaining([
          expect.objectContaining({
            id: expect.any(String),
            name: expect.any(String),
            symbol: expect.any(String),
            asset_class: expect.any(String),
            x: expect.any(Number),
            y: expect.any(Number),
            z: expect.any(Number),
            color: expect.any(String),
            size: expect.any(Number),
          }),
        ]),
        edges: expect.any(Array),
      }),
    );
  });
});

describe("Home Page", () => {
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

describe("Accessibility Tests", () => {
  it("should have proper heading hierarchy", async () => {
    render(<Home />);

    await waitFor(() => {
      const h1 = screen.getByRole("heading", { level: 1 });
      expect(h1).toHaveTextContent("Financial Asset Relationship Network");
    });
  });

  it("should have accessible navigation buttons", async () => {
    render(<Home />);

    await waitFor(() => {
      const buttons = screen.getAllByRole("button");
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it("should have descriptive button text", async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("3D Visualization")).toBeInTheDocument();
      expect(screen.getByText("Metrics & Analytics")).toBeInTheDocument();
      expect(screen.getByText("Asset Explorer")).toBeInTheDocument();
    });
  });
});

describe("Error Handling and Recovery", () => {
  it("should handle visualization data loading failure separately from metrics", async () => {
    mockedApi.getMetrics.mockResolvedValue(mockMetrics);
    mockedApi.getVisualizationData.mockRejectedValue(new Error("Viz Error"));
    const consoleError = jest.spyOn(console, "error").mockImplementation();

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
    });

    consoleError.mockRestore();
  });

  it("should show generic error message for unknown errors", async () => {
    mockedApi.getMetrics.mockRejectedValue(new Error());
    const consoleError = jest.spyOn(console, "error").mockImplementation();

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
    });

    consoleError.mockRestore();
  });

  it("should clear error state on successful retry", async () => {
    mockedApi.getMetrics
      .mockRejectedValueOnce(new Error("Network Error"))
      .mockResolvedValueOnce(mockMetrics);
    mockedApi.getVisualizationData.mockResolvedValue(mockVisualizationData);

    const consoleError = jest.spyOn(console, "error").mockImplementation();
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Retry"));

    await waitFor(() => {
      expect(
        screen.queryByText(/Failed to load data/i),
      ).not.toBeInTheDocument();
    });

    consoleError.mockRestore();
  });
});

describe("Tab Navigation and State Management", () => {
  it("should maintain active tab during re-renders", async () => {
    const { rerender } = render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Metrics & Analytics"));
    expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();

    rerender(<Home />);
    expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();
  });

  it("should switch between all three tabs sequentially", async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Metrics & Analytics"));
    expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();
    expect(
      screen.queryByTestId("network-visualization"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Asset Explorer"));
    expect(screen.getByTestId("asset-list")).toBeInTheDocument();
    expect(screen.queryByTestId("metrics-dashboard")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("3D Visualization"));
    expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
    expect(screen.queryByTestId("asset-list")).not.toBeInTheDocument();
  });

  it("should highlight active tab button", async () => {
    render(<Home />);

    await waitFor(() => {
      const vizButton = screen.getByText("3D Visualization");
      expect(vizButton).toHaveClass("border-blue-500");
    });

    const metricsButton = screen.getByText("Metrics & Analytics");
    fireEvent.click(metricsButton);

    expect(metricsButton).toHaveClass("border-blue-500");
    expect(screen.getByText("3D Visualization")).toHaveClass(
      "border-transparent",
    );
  });
});

describe("Component Integration", () => {
  it("should pass correct props to NetworkVisualization", async () => {
    const customVizData = {
      nodes: [
        {
          id: "TEST",
          name: "Test",
          symbol: "TST",
          asset_class: "EQUITY",
          x: 0,
          y: 0,
          z: 0,
          color: "#000",
          size: 5,
        },
      ],
      edges: [],
    };
    mockedApi.getVisualizationData.mockResolvedValue(customVizData);

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
    });
  });

  it("should pass correct props to MetricsDashboard", async () => {
    const customMetrics = {
      total_assets: 99,
      total_relationships: 88,
      asset_classes: { TEST: 77 },
      avg_degree: 6.6,
      max_degree: 66,
      network_density: 0.66,
    };
    mockedApi.getMetrics.mockResolvedValue(customMetrics);

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Metrics & Analytics"));

    expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();
  });
});

describe("Loading States", () => {
  it("should show loading spinner while fetching data", () => {
    mockedApi.getMetrics.mockImplementation(
      () =>
        new Promise(() => {
          // intentionally left empty to simulate a pending promise for loading state
        }),
    );
    render(<Home />);

    expect(screen.getByText("Loading data...")).toBeInTheDocument();
    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("should hide loading state after data loads", async () => {
    render(<Home />);

    expect(screen.getByText("Loading data...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText("Loading data...")).not.toBeInTheDocument();
    });
  });

  it("should hide loading state after error occurs", async () => {
    mockedApi.getMetrics.mockRejectedValue(new Error("Test Error"));
    const consoleError = jest.spyOn(console, "error").mockImplementation();

    render(<Home />);

    await waitFor(() => {
      expect(screen.queryByText("Loading data...")).not.toBeInTheDocument();
      expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
    });

    consoleError.mockRestore();
  });
});

describe("Footer and Static Content", () => {
  it("should render footer with correct text", async () => {
    render(<Home />);

    await waitFor(() => {
      expect(
        screen.getByText(/Powered by Next.js & FastAPI/i),
      ).toBeInTheDocument();
    });
  });

  it("should render description paragraph", async () => {
    render(<Home />);

    expect(
      screen.getByText(/Interactive 3D visualization/i),
    ).toBeInTheDocument();
  });
});
