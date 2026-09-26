/**
 * Unit tests for the main page component.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import Home from "../../app/page";
import { api } from "../../app/lib/api";
import type { VisualizationData } from "../../app/types/api";
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
      screen.getByText(/FarDb — Financial Asset Relationship Database/i),
    ).toBeInTheDocument();
  });

  it("should render navigation tabs", async () => {
    render(<Home />);
    expect(screen.getByText("GRAC Demonstrator")).toBeInTheDocument();
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

  it("should expose tab semantics for the active demonstrator", async () => {
    render(<Home />);

    await waitFor(() => {
      const tab = screen.getByRole("tab", { name: "GRAC Demonstrator" });
      expect(tab).toHaveAttribute("aria-selected", "true");
      expect(tab).toHaveAttribute("aria-controls", "tabpanel-demonstrator");
      expect(screen.getByRole("tabpanel")).toHaveAttribute(
        "aria-labelledby",
        "tab-demonstrator",
      );
      expect(
        screen.getByRole("tab", { name: "3D Visualization" }),
      ).not.toHaveAttribute("aria-controls");
    });
  });

  it("should show loading state for data-dependent tabs", () => {
    render(<Home />);
    fireEvent.click(screen.getByText("3D Visualization"));
    expect(screen.getByText("Loading data...")).toBeInTheDocument();
  });

  it("should render the demonstrator before dashboard data settles", () => {
    mockedApi.getMetrics.mockImplementation(() => new Promise(() => {}));
    mockedApi.getVisualizationData.mockImplementation(
      () => new Promise(() => {}),
    );

    render(<Home />);

    expect(
      screen.getByText("FarDb Institutional Demonstrator"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Loading data...")).not.toBeInTheDocument();
  });

  it("should switch tabs", async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("3D Visualization"));
    expect(screen.getByTestId("network-visualization")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Metrics & Analytics"));
    expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Asset Explorer"));
    expect(screen.getByTestId("asset-list")).toBeInTheDocument();
  });

  it("should allow Asset Explorer when dashboard requests both fail", async () => {
    mockedApi.getMetrics.mockRejectedValue(new Error("Metrics outage"));
    mockedApi.getVisualizationData.mockRejectedValue(
      new Error("Visualization outage"),
    );
    const consoleError = jest.spyOn(console, "error").mockImplementation();

    render(<Home />);

    await waitFor(() => {
      expect(mockedApi.getMetrics).toHaveBeenCalled();
      expect(mockedApi.getVisualizationData).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByText("Asset Explorer"));

    expect(screen.getByTestId("asset-list")).toBeInTheDocument();
    expect(screen.queryByText(/Failed to load data/i)).not.toBeInTheDocument();

    consoleError.mockRestore();
  });

  it("should handle metrics API errors without blocking the demonstrator", async () => {
    const consoleError = jest.spyOn(console, "error").mockImplementation();
    mockedApi.getMetrics.mockRejectedValue(new Error("API Error"));

    render(<Home />);

    await waitFor(() => {
      expect(
        screen.getByText("FarDb Institutional Demonstrator"),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Metrics & Analytics"));
    expect(
      screen.getByText("Failed to load metrics data."),
    ).toBeInTheDocument();

    consoleError.mockRestore();
  });

  it("should allow retry after a metrics error", async () => {
    mockedApi.getMetrics.mockRejectedValueOnce(new Error("API Error"));
    mockedApi.getMetrics.mockResolvedValueOnce(mockMetrics);

    render(<Home />);

    await waitFor(() => {
      expect(
        screen.getByText("FarDb Institutional Demonstrator"),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Metrics & Analytics"));
    expect(
      screen.getByText("Failed to load metrics data."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText("Retry"));

    await waitFor(() => {
      expect(mockedApi.getMetrics).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();
    });
  });
});

describe("Accessibility Tests", () => {
  it("should have proper heading hierarchy", async () => {
    render(<Home />);

    await waitFor(() => {
      const h1 = screen.getByRole("heading", { level: 1 });
      expect(h1).toHaveTextContent(
        "FarDb — Financial Asset Relationship Database",
      );
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
      expect(
        screen.getByText("FarDb Institutional Demonstrator"),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("3D Visualization"));

    expect(
      screen.getByText(
        "Failed to load visualization data. Please ensure the API server is running.",
      ),
    ).toBeInTheDocument();

    consoleError.mockRestore();
  });

  it("should show generic error message when both dashboard requests fail", async () => {
    mockedApi.getMetrics.mockRejectedValue(new Error());
    mockedApi.getVisualizationData.mockRejectedValue(new Error());
    const consoleError = jest.spyOn(console, "error").mockImplementation();

    render(<Home />);
    fireEvent.click(screen.getByText("3D Visualization"));

    await waitFor(() => {
      expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
    });

    consoleError.mockRestore();
  });

  it("should show a stale graph notice after a total dashboard outage", async () => {
    mockedApi.getMetrics
      .mockRejectedValueOnce(new Error("Metrics outage"))
      .mockRejectedValueOnce(new Error("Metrics retry outage"));
    mockedApi.getVisualizationData
      .mockResolvedValueOnce(mockVisualizationData)
      .mockRejectedValueOnce(new Error("Viz retry outage"));

    const consoleError = jest.spyOn(console, "error").mockImplementation();
    render(<Home />);

    fireEvent.click(screen.getByText("Metrics & Analytics"));
    await waitFor(() => {
      expect(
        screen.getByText("Failed to load metrics data."),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Retry"));

    await waitFor(() => {
      expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("GRAC Demonstrator"));

    expect(
      screen.getByText(
        "The latest refresh failed — showing the last successfully loaded graph.",
      ),
    ).toBeInTheDocument();

    consoleError.mockRestore();
  });

  it("should show a stale graph notice after a visualization refresh fails", async () => {
    mockedApi.getMetrics
      .mockRejectedValueOnce(new Error("Metrics outage"))
      .mockResolvedValueOnce(mockMetrics);
    mockedApi.getVisualizationData
      .mockResolvedValueOnce(mockVisualizationData)
      .mockRejectedValueOnce(new Error("Viz refresh failed"));

    const consoleError = jest.spyOn(console, "error").mockImplementation();
    render(<Home />);

    fireEvent.click(screen.getByText("Metrics & Analytics"));
    await waitFor(() => {
      expect(
        screen.getByText("Failed to load metrics data."),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Retry"));

    await waitFor(() => {
      expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("GRAC Demonstrator"));

    expect(
      screen.getByText(
        "The latest refresh failed — showing the last successfully loaded graph.",
      ),
    ).toBeInTheDocument();

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
      expect(
        screen.getByText("FarDb Institutional Demonstrator"),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Metrics & Analytics"));
    expect(
      screen.getByText("Failed to load metrics data."),
    ).toBeInTheDocument();

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

  it("should switch between all four tabs sequentially", async () => {
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

    fireEvent.click(screen.getByText("GRAC Demonstrator"));
    expect(
      screen.getByText("FarDb Institutional Demonstrator"),
    ).toBeInTheDocument();
  });

  it("should expose active tab state after switching tabs", async () => {
    render(<Home />);

    await waitFor(() => {
      expect(
        screen.getByRole("tab", { name: "GRAC Demonstrator" }),
      ).toHaveAttribute("aria-selected", "true");
    });

    fireEvent.click(screen.getByText("Metrics & Analytics"));
    expect(
      screen.getByRole("tab", { name: "Metrics & Analytics" }),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByRole("tab", { name: "GRAC Demonstrator" }),
    ).toHaveAttribute("aria-selected", "false");
  });

  it("should support keyboard navigation between tabs", async () => {
    render(<Home />);

    await waitFor(() => {
      expect(
        screen.getByRole("tab", { name: "GRAC Demonstrator" }),
      ).toHaveAttribute("aria-selected", "true");
    });

    const demoTab = screen.getByRole("tab", { name: "GRAC Demonstrator" });
    fireEvent.keyDown(demoTab, { key: "ArrowRight" });

    const visualizationTab = screen.getByRole("tab", {
      name: "3D Visualization",
    });
    expect(visualizationTab).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(visualizationTab);

    fireEvent.keyDown(visualizationTab, { key: "End" });
    const assetTab = screen.getByRole("tab", { name: "Asset Explorer" });
    expect(assetTab).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(assetTab);

    fireEvent.keyDown(assetTab, { key: "Home" });
    expect(demoTab).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(demoTab);
  });

  it("should highlight active tab button", async () => {
    render(<Home />);

    await waitFor(() => {
      const demoButton = screen.getByText("GRAC Demonstrator");
      expect(demoButton).toHaveClass("border-blue-500");
    });

    const vizButton = screen.getByText("3D Visualization");
    fireEvent.click(vizButton);
    expect(vizButton).toHaveClass("border-blue-500");

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
    const customVizData: VisualizationData = {
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
      network_density: 0,
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
    fireEvent.click(screen.getByText("3D Visualization"));

    expect(screen.getByText("Loading data...")).toBeInTheDocument();
    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("should hide loading state after data loads", async () => {
    render(<Home />);
    fireEvent.click(screen.getByText("3D Visualization"));

    expect(screen.getByText("Loading data...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText("Loading data...")).not.toBeInTheDocument();
    });
  });

  it("should hide loading state after error occurs", async () => {
    mockedApi.getMetrics.mockRejectedValue(new Error("Test Error"));
    mockedApi.getVisualizationData.mockRejectedValue(
      new Error("Test Visualization Error"),
    );
    const consoleError = jest.spyOn(console, "error").mockImplementation();

    render(<Home />);
    fireEvent.click(screen.getByText("3D Visualization"));

    await waitFor(() => {
      expect(screen.queryByText("Loading data...")).not.toBeInTheDocument();
      expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
    });

    consoleError.mockRestore();
  });
});

describe("Footer and Static Content", () => {
  it("should render footer with demonstrator text", async () => {
    render(<Home />);

    await waitFor(() => {
      expect(
        screen.getByText(
          /FarDb — Governed Relationship Assertion Contract demonstrator/i,
        ),
      ).toBeInTheDocument();
    });
  });

  it("should render description paragraph", async () => {
    render(<Home />);

    expect(
      screen.getByText(
        /Governed relationship infrastructure with an institutional demonstration surface/i,
      ),
    ).toBeInTheDocument();
  });
});
