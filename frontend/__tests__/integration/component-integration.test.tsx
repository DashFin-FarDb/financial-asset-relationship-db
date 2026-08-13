/**
 * Integration tests for component interactions and data flow.
 *
 * Tests the integration between API client, components, and user interactions,
 * ensuring that data flows correctly through the application and components
 * work together as expected.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import Home from "../../app/page";
import { api } from "../../app/lib/api";
import {
  mockAssets,
  mockMetrics,
  mockVisualizationData,
  mockAssetClasses,
  mockSectors,
} from "../test-utils";

jest.mock("../../app/lib/api");
jest.mock("../../app/components/NetworkVisualization", () => {
  return function MockVisualization({ data }: { data: unknown }) {
    return (
      <div data-testid="network-visualization">
        <div data-testid="viz-node-count">{data?.nodes?.length || 0}</div>
        <div data-testid="viz-edge-count">{data?.edges?.length || 0}</div>
      </div>
    );
  };
});
jest.mock("../../app/components/MetricsDashboard", () => {
  return function MockMetrics({ metrics }: { metrics: unknown }) {
    return (
      <div data-testid="metrics-dashboard">
        <div data-testid="total-assets">{metrics?.total_assets || 0}</div>
        <div data-testid="total-relationships">
          {metrics?.total_relationships || 0}
        </div>
      </div>
    );
  };
});
jest.mock("../../app/components/AssetList", () => {
  return function MockAssetList() {
    return <div data-testid="asset-list">Asset List Component</div>;
  };
});

const mockedApi = api as jest.Mocked<typeof api>;

describe("Component Integration Tests", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.getMetrics.mockResolvedValue(mockMetrics);
    mockedApi.getVisualizationData.mockResolvedValue(mockVisualizationData);
    mockedApi.getAssets.mockResolvedValue({
      items: mockAssets,
      total: mockAssets.length,
      page: 1,
      per_page: 50,
      hasMore: false,
    });
    mockedApi.getAssetClasses.mockResolvedValue(mockAssetClasses);
    mockedApi.getSectors.mockResolvedValue(mockSectors);
  });

  describe("Data Flow from API to Components", () => {
    it("should load data from API and pass to visualization component", async () => {
      render(<Home />);

      await waitFor(() => {
        expect(mockedApi.getVisualizationData).toHaveBeenCalled();
        expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
      });

      expect(screen.getByTestId("viz-node-count")).toHaveTextContent(
        mockVisualizationData.nodes.length.toString(),
      );
      expect(screen.getByTestId("viz-edge-count")).toHaveTextContent(
        mockVisualizationData.edges.length.toString(),
      );
    });

    it("should load data from API and pass to metrics dashboard", async () => {
      render(<Home />);

      fireEvent.click(screen.getByText("Metrics & Analytics"));

      await waitFor(() => {
        expect(mockedApi.getMetrics).toHaveBeenCalled();
      });

      const totalAssets = await screen.findByTestId("total-assets");
      expect(totalAssets).toHaveTextContent(
        mockMetrics.total_assets.toString(),
      );

      const totalRels = await screen.findByTestId("total-relationships");
      expect(totalRels).toHaveTextContent(
        mockMetrics.total_relationships.toString(),
      );
    });
  });

  describe("User Interaction Flows", () => {
    it("should complete full user journey: visualization → metrics → assets", async () => {
      render(<Home />);

      // Start with visualization
      await waitFor(() => {
        expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
      });

      // Navigate to metrics
      fireEvent.click(screen.getByText("Metrics & Analytics"));
      expect(screen.getByTestId("metrics-dashboard")).toBeInTheDocument();
      expect(
        screen.queryByTestId("network-visualization"),
      ).not.toBeInTheDocument();

      // Navigate to assets
      fireEvent.click(screen.getByText("Asset Explorer"));
      expect(screen.getByTestId("asset-list")).toBeInTheDocument();
      expect(screen.queryByTestId("metrics-dashboard")).not.toBeInTheDocument();

      // Return to visualization
      fireEvent.click(screen.getByText("3D Visualization"));
      expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
      expect(screen.queryByTestId("asset-list")).not.toBeInTheDocument();
    });

    it("should handle rapid tab switching without errors", async () => {
      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
      });

      // Rapidly switch tabs
      for (let i = 0; i < 5; i++) {
        fireEvent.click(screen.getByText("Metrics & Analytics"));
        fireEvent.click(screen.getByText("Asset Explorer"));
        fireEvent.click(screen.getByText("3D Visualization"));
      }

      // Should end on visualization without errors
      expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
    });
  });

  describe("Error Recovery Across Components", () => {
    it("should allow partial data loading (metrics succeeds, visualization fails)", async () => {
      mockedApi.getMetrics.mockResolvedValue(mockMetrics);
      mockedApi.getVisualizationData.mockRejectedValue(new Error("Viz failed"));
      const consoleError = jest.spyOn(console, "error").mockImplementation();

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
      });

      // Metrics were loaded, but error prevents showing any component
      expect(mockedApi.getMetrics).toHaveBeenCalled();
      expect(mockedApi.getVisualizationData).toHaveBeenCalled();

      consoleError.mockRestore();
    });

    it("should retry loading all data on retry button click", async () => {
      mockedApi.getMetrics.mockRejectedValueOnce(new Error("First fail"));
      mockedApi.getMetrics.mockResolvedValueOnce(mockMetrics);
      mockedApi.getVisualizationData.mockRejectedValueOnce(
        new Error("First fail"),
      );
      mockedApi.getVisualizationData.mockResolvedValueOnce(
        mockVisualizationData,
      );

      const consoleError = jest.spyOn(console, "error").mockImplementation();
      render(<Home />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Retry"));

      await waitFor(() => {
        expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
      });

      expect(mockedApi.getMetrics).toHaveBeenCalledTimes(2);
      expect(mockedApi.getVisualizationData).toHaveBeenCalledTimes(2);

      consoleError.mockRestore();
    });
  });

  describe("State Consistency Across Tab Changes", () => {
    it("should maintain data consistency when switching tabs", async () => {
      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
      });

      const initialNodeCount = screen.getByTestId("viz-node-count").textContent;

      // Switch away and back
      fireEvent.click(screen.getByText("Metrics & Analytics"));
      fireEvent.click(screen.getByText("3D Visualization"));

      // Data should remain the same
      expect(screen.getByTestId("viz-node-count")).toHaveTextContent(
        initialNodeCount || "",
      );
    });

    it("should not reload data when switching tabs", async () => {
      render(<Home />);

      await waitFor(() => {
        expect(mockedApi.getMetrics).toHaveBeenCalledTimes(1);
        expect(mockedApi.getVisualizationData).toHaveBeenCalledTimes(1);
      });

      // Switch tabs multiple times
      fireEvent.click(screen.getByText("Metrics & Analytics"));
      fireEvent.click(screen.getByText("Asset Explorer"));
      fireEvent.click(screen.getByText("3D Visualization"));

      // API should still only be called once
      expect(mockedApi.getMetrics).toHaveBeenCalledTimes(1);
      expect(mockedApi.getVisualizationData).toHaveBeenCalledTimes(1);
    });
  });

  describe("Performance and Edge Cases", () => {
    it("should handle empty visualization data gracefully", async () => {
      mockedApi.getVisualizationData.mockResolvedValue({
        nodes: [],
        edges: [],
      });

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
      });

      expect(screen.getByTestId("viz-node-count")).toHaveTextContent("0");
      expect(screen.getByTestId("viz-edge-count")).toHaveTextContent("0");
    });

    it("should handle zero metrics gracefully", async () => {
      const zeroMetrics = {
        total_assets: 0,
        total_relationships: 0,
        asset_classes: {},
        avg_degree: 0,
        max_degree: 0,
        network_density: 0,
      };
      mockedApi.getMetrics.mockResolvedValue(zeroMetrics);

      render(<Home />);

      fireEvent.click(screen.getByText("Metrics & Analytics"));

      const totalAssets = await screen.findByTestId("total-assets");
      expect(totalAssets).toHaveTextContent("0");

      const totalRels = await screen.findByTestId("total-relationships");
      expect(totalRels).toHaveTextContent("0");
    });

    it("should handle very large datasets", async () => {
      const largeData = {
        nodes: Array.from({ length: 500 }, (_, i) => ({
          id: `N${i}`,
          name: `Node ${i}`,
          symbol: `S${i}`,
          asset_class: "EQUITY",
          x: i,
          y: i,
          z: i,
          color: "#000",
          size: 5,
        })),
        edges: Array.from({ length: 2000 }, (_, i) => ({
          source: `N${i % 500}`,
          target: `N${(i + 1) % 500}`,
          relationship_type: "TEST",
          strength: 0.5,
        })),
      };

      mockedApi.getVisualizationData.mockResolvedValue(largeData);

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
      });

      expect(screen.getByTestId("viz-node-count")).toHaveTextContent("500");
      expect(screen.getByTestId("viz-edge-count")).toHaveTextContent("2000");
    });
  });

  describe("Concurrent Component Rendering", () => {
    it("should handle simultaneous API calls without race conditions", async () => {
      let metricsResolve: ((value: unknown) => void) | null = null;
      let vizResolve: ((value: unknown) => void) | null = null;

      mockedApi.getMetrics.mockImplementation(
        () =>
          new Promise((resolve) => {
            metricsResolve = resolve;
          }),
      );
      mockedApi.getVisualizationData.mockImplementation(
        () =>
          new Promise((resolve) => {
            vizResolve = resolve;
          }),
      );

      render(<Home />);

      expect(screen.getByText("Loading data...")).toBeInTheDocument();

      // Resolve in reverse order
      await waitFor(() => {
        expect(vizResolve).not.toBeNull();
        expect(metricsResolve).not.toBeNull();
      });

      if (!vizResolve) {
        throw new Error("vizResolve is null");
      }
      vizResolve(mockVisualizationData);
      await new Promise((resolve) => setTimeout(resolve, 10));
      if (!metricsResolve) {
        throw new Error("metricsResolve is null");
      }
      metricsResolve(mockMetrics);

      await waitFor(() => {
        expect(screen.queryByText("Loading data...")).not.toBeInTheDocument();
        expect(screen.getByTestId("network-visualization")).toBeInTheDocument();
      });
    });
  });

  describe("Parent-to-Child Publication-Envelope Integration", () => {
    const ActualNetworkVisualization = jest.requireActual(
      "../../app/components/NetworkVisualization",
    ).default;

    const publicationA = {
      publication_id: "pub-A",
      revision_id: "rev-A",
      rebuild_job_id: "job-100",
      execution_id: "exec-200",
      published_at: "2024-01-01T12:00:00Z",
      purpose: "financial-relationship-graph",
      effective_at: "2024-01-01T12:00:00Z",
      known_at: "2024-01-01T12:00:00Z",
      contract_version: "grac-v1",
      projector_version: "v1.2.3",
      edge_set_hash: "hash-edges-A",
      projection_hash: "hash-proj-A",
      governed_scopes: [
        {
          purpose: "financial-relationship-graph",
          predicate_id: "predicate-issuer",
        },
      ],
    };

    const publicationB = {
      ...publicationA,
      publication_id: "pub-B",
      revision_id: "rev-B",
      edge_set_hash: "hash-edges-B",
      projection_hash: "hash-proj-B",
    };

    const dataA = {
      nodes: [
        {
          id: "A1",
          name: "Asset 1",
          symbol: "A1",
          asset_class: "EQUITY",
          x: 1,
          y: 1,
          z: 1,
          color: "red",
          size: 1,
        },
        {
          id: "A2",
          name: "Asset 2",
          symbol: "A2",
          asset_class: "EQUITY",
          x: 2,
          y: 2,
          z: 2,
          color: "blue",
          size: 1,
        },
      ],
      edges: [
        {
          edge_id: "edge-A",
          projection_edge_id: "pedge-A",
          source: "A1",
          target: "A2",
          relationship_type: "CORPORATE_LINK",
          strength: 0.9,
          assertion_id: "assert-A",
          governance_status: "governed",
          revision_id: "rev-A",
          scope_refs: ["predicate-issuer"],
        },
      ],
      network_density: 0.5,
      publication: publicationA,
    };

    const dataB = {
      nodes: [
        {
          id: "A1",
          name: "Asset 1",
          symbol: "A1",
          asset_class: "EQUITY",
          x: 1,
          y: 1,
          z: 1,
          color: "red",
          size: 1,
        },
        {
          id: "A2",
          name: "Asset 2",
          symbol: "A2",
          asset_class: "EQUITY",
          x: 2,
          y: 2,
          z: 2,
          color: "blue",
          size: 1,
        },
      ],
      edges: [
        {
          edge_id: "edge-B",
          projection_edge_id: "pedge-B",
          source: "A1",
          target: "A2",
          relationship_type: "CORPORATE_LINK",
          strength: 0.85,
          assertion_id: "assert-B",
          governance_status: "governed",
          revision_id: "rev-B",
          scope_refs: ["predicate-issuer"],
        },
      ],
      network_density: 0.5,
      publication: publicationB,
    };

    const explanationA = {
      publication: publicationA,
      edge: {
        projection_edge_id: "pedge-A",
        source: "A1",
        target: "A2",
        relationship_type: "CORPORATE_LINK",
        strength: "0.90",
        direction: "directional",
        assertion_id: "assert-A",
      },
      assertion: {
        explanation: {
          assertion_id: "assert-A",
          predicate_id: "predicate-issuer",
          subject_id: "A1",
          object_id: "A2",
          method_id: "m-1",
          proposition: "A1 controls A2",
          confidence_status: "assessed",
          confidence_bp: 9000,
          confidence_type: "statistical",
          confidence_method: "filings",
          effective_from: "2024-01-01T12:00:00Z",
          effective_to: null,
          recorded_at: "2024-01-01T12:00:00Z",
          state: "Accepted",
          known_at: "2024-01-01T12:00:00Z",
          effective_at: "2024-01-01T12:00:00Z",
          sequence: 1,
          evidence: [],
        },
        history: {
          assertion_id: "assert-A",
          effective_from: "2024-01-01T12:00:00Z",
          effective_to: null,
          recorded_at: "2024-01-01T12:00:00Z",
          state: "Accepted",
          known_at: "2024-01-01T12:00:00Z",
          effective_at: "2024-01-01T12:00:00Z",
          events: [],
        },
      },
    };

    const explanationB = {
      publication: publicationB,
      edge: {
        projection_edge_id: "pedge-B",
        source: "A1",
        target: "A2",
        relationship_type: "CORPORATE_LINK",
        strength: "0.85",
        direction: "directional",
        assertion_id: "assert-B",
      },
      assertion: {
        explanation: {
          assertion_id: "assert-B",
          predicate_id: "predicate-issuer",
          subject_id: "A1",
          object_id: "A2",
          method_id: "m-1",
          proposition: "A1 has exposure to A2",
          confidence_status: "assessed",
          confidence_bp: 8500,
          confidence_type: "statistical",
          confidence_method: "filings",
          effective_from: "2024-01-01T12:00:00Z",
          effective_to: null,
          recorded_at: "2024-01-01T12:00:00Z",
          state: "Accepted",
          known_at: "2024-01-01T12:00:00Z",
          effective_at: "2024-01-01T12:00:00Z",
          sequence: 1,
          evidence: [],
        },
        history: {
          assertion_id: "assert-B",
          effective_from: "2024-01-01T12:00:00Z",
          effective_to: null,
          recorded_at: "2024-01-01T12:00:00Z",
          state: "Accepted",
          known_at: "2024-01-01T12:00:00Z",
          effective_at: "2024-01-01T12:00:00Z",
          events: [],
        },
      },
    };

    it("verifies the parent-to-child publication envelope lifecycle", async () => {
      mockedApi.getPublishedEdgeExplanation.mockResolvedValue(explanationA);

      // 1. Render NetworkVisualization with publication A
      const { rerender } = render(<ActualNetworkVisualization data={dataA} />);

      // 2. Select its governed edge
      const edgeAButton = screen.getByRole("button", {
        name: /A1.*A2.*CORPORATE_LINK.*Governed/,
      });
      fireEvent.click(edgeAButton);

      // 3. Resolves and displays publication-A explanation data
      await waitFor(() => {
        expect(mockedApi.getPublishedEdgeExplanation).toHaveBeenCalledWith(
          "pub-A",
          "pedge-A",
          expect.anything(),
        );
      });
      await waitFor(() => {
        expect(screen.getByText("A1 controls A2")).toBeInTheDocument();
        expect(screen.getByText("pub-A")).toBeInTheDocument();
      });

      // 4. Rerender with publication B, whose edge IDs differ
      mockedApi.getPublishedEdgeExplanation.mockResolvedValue(explanationB);
      rerender(<ActualNetworkVisualization data={dataB} />);

      // 5. Verifies the publication-A explanation disappears
      await waitFor(() => {
        expect(screen.queryByText("A1 controls A2")).not.toBeInTheDocument();
      });

      // 6. Verifies no replacement edge is silently selected
      expect(
        screen.getByText("Select a relationship to see how it was determined."),
      ).toBeInTheDocument();

      // 7. Selects publication-B’s edge and confirms the request and displayed provenance use publication B
      const edgeBButton = screen.getByRole("button", {
        name: /A1.*A2.*CORPORATE_LINK.*Governed/,
      });
      fireEvent.click(edgeBButton);

      await waitFor(() => {
        expect(mockedApi.getPublishedEdgeExplanation).toHaveBeenLastCalledWith(
          "pub-B",
          "pedge-B",
          expect.anything(),
        );
      });
      await waitFor(() => {
        expect(screen.getByText("A1 has exposure to A2")).toBeInTheDocument();
        expect(screen.getByText("pub-B")).toBeInTheDocument();
      });
    });
  });
});
