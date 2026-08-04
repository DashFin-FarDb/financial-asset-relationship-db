/**
 * Comprehensive unit tests for NetworkVisualization component.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import NetworkVisualization from "../../app/components/NetworkVisualization";
import type { VisualizationData } from "../../app/types/api";
import { mockVisualizationData } from "../test-utils";
import { api } from "../../app/lib/api";

jest.mock("../../app/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

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
      network_density: 0,
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
      network_density: 0,
    };

    render(<NetworkVisualization data={bigData} />);

    expect(
      screen.getByText(
        /Visualization is unavailable because the dataset is too large/,
      ),
    ).toBeInTheDocument();
  });

  describe("keyboard-accessible relationship selection and opaque edge_id selection", () => {
    const governedData: VisualizationData = {
      nodes: mockVisualizationData.nodes,
      edges: [
        {
          edge_id: "legacy-edge-1",
          source: "ASSET_1",
          target: "ASSET_2",
          relationship_type: "SAME_SECTOR",
          strength: 0.7,
        },
        {
          edge_id: "edge-canonical",
          projection_edge_id: "pedge-1",
          source: "ASSET_2",
          target: "ASSET_1",
          relationship_type: "CORPORATE_LINK",
          strength: 0.9,
          assertion_id: "assertion-1",
          governance_status: "governed",
          revision_id: "rev-1",
          scope_refs: ["predicate-issuer"],
        },
        {
          edge_id: "edge-reverse",
          projection_edge_id: "pedge-2",
          source: "ASSET_1",
          target: "ASSET_2",
          relationship_type: "CORPORATE_LINK",
          strength: 0.9,
          assertion_id: "assertion-1",
          governance_status: "governed",
          revision_id: "rev-1",
          scope_refs: ["predicate-issuer"],
        },
        {
          // Edge missing edge_id should be skipped
          source: "ASSET_1",
          target: "ASSET_2",
          relationship_type: "INVALID_MALFORMED",
          strength: 0.5,
        } as unknown as VisualizationData["edges"][number],
      ],
      network_density: 0.5,
      publication: {
        publication_id: "pub-1",
        revision_id: "rev-1",
        rebuild_job_id: "job-1",
        execution_id: "exec-1",
        published_at: "2024-01-01T00:00:00Z",
        purpose: "financial-relationship-graph",
        effective_at: "2024-01-01T00:00:00Z",
        known_at: "2024-01-01T00:00:00Z",
        contract_version: "grac-v1",
        projector_version: "v1.0.0",
        edge_set_hash: "hash-edges-123",
        projection_hash: "hash-proj-456",
        governed_scopes: [
          {
            purpose: "financial-relationship-graph",
            predicate_id: "predicate-issuer",
          },
        ],
      },
    };

    beforeEach(() => {
      jest.clearAllMocks();
    });

    it("lists valid relationships and skips malformed edges missing edge_id", () => {
      render(<NetworkVisualization data={governedData} />);

      expect(
        screen.getByRole("group", {
          name: "Relationships (keyboard-accessible list)",
        }),
      ).toBeInTheDocument();
      expect(screen.getByText("Legacy")).toBeInTheDocument();
      expect(screen.getAllByText("Governed")).toHaveLength(2);
      expect(screen.queryByText(/INVALID_MALFORMED/)).not.toBeInTheDocument();
    });

    it("selects a relationship via keyboard navigation using tab and Enter/Space key", async () => {
      mockedApi.getPublishedEdgeExplanation.mockResolvedValue({
        publication: governedData.publication!,
        edge: {
          projection_edge_id: "pedge-1",
          source: "ASSET_2",
          target: "ASSET_1",
          relationship_type: "CORPORATE_LINK",
          strength: "0.90",
          direction: "directional",
          assertion_id: "assertion-1",
        },
        assertion: {
          explanation: {
            assertion_id: "assertion-1",
            predicate_id: "predicate-issuer",
            subject_id: "ASSET_2",
            object_id: "ASSET_1",
            method_id: "method-1",
            proposition: "ASSET_2 is the issuer of ASSET_1",
            confidence_status: "not_assessed",
            confidence_bp: null,
            confidence_type: null,
            confidence_method: null,
            effective_from: "2024-01-01T00:00:00Z",
            effective_to: null,
            recorded_at: "2024-01-01T00:00:00Z",
            state: "Accepted",
            known_at: "2024-01-01T00:00:00Z",
            effective_at: "2024-01-01T00:00:00Z",
            sequence: 1,
            evidence: [],
          },
          history: {
            assertion_id: "assertion-1",
            effective_from: "2024-01-01T00:00:00Z",
            effective_to: null,
            recorded_at: "2024-01-01T00:00:00Z",
            state: "Accepted",
            known_at: "2024-01-01T00:00:00Z",
            effective_at: "2024-01-01T00:00:00Z",
            events: [
              {
                event_id: "event-1",
                assertion_id: "assertion-1",
                sequence: 1,
                from_state: null,
                to_state: "Proposed",
                authority: "proposer",
                recorded_at: "2024-01-01T00:00:00Z",
              },
            ],
          },
        },
      });

      const user = userEvent.setup();
      render(<NetworkVisualization data={governedData} />);

      const canonicalButton = screen.getByRole("button", {
        name: /ASSET_2.*ASSET_1.*CORPORATE_LINK.*Governed/,
      });

      let reachedButton = false;
      for (let tabStop = 0; tabStop < 25; tabStop += 1) {
        await user.tab();
        if (document.activeElement === canonicalButton) {
          reachedButton = true;
          break;
        }
      }
      expect(reachedButton).toBe(true);

      await user.keyboard("{Enter}");

      expect(canonicalButton).toHaveAttribute("aria-pressed", "true");
      await waitFor(() => {
        expect(mockedApi.getPublishedEdgeExplanation).toHaveBeenCalledWith(
          "pub-1",
          "pedge-1",
          expect.anything(),
        );
      });
      await waitFor(() => {
        expect(
          screen.getByText("ASSET_2 is the issuer of ASSET_1"),
        ).toBeInTheDocument();
      });
    });

    it("allows canonical and reverse representations to select independently by their edge_id", async () => {
      mockedApi.getPublishedEdgeExplanation.mockResolvedValue({
        publication: governedData.publication!,
        edge: {
          projection_edge_id: "pedge-2",
          source: "ASSET_1",
          target: "ASSET_2",
          relationship_type: "CORPORATE_LINK",
          strength: "0.90",
          direction: "directional",
          assertion_id: "assertion-1",
        },
        assertion: {
          explanation: {
            assertion_id: "assertion-1",
            predicate_id: "predicate-issuer",
            subject_id: "ASSET_2",
            object_id: "ASSET_1",
            method_id: "method-1",
            proposition: "ASSET_2 is the issuer of ASSET_1",
            confidence_status: "not_assessed",
            confidence_bp: null,
            confidence_type: null,
            confidence_method: null,
            effective_from: "2024-01-01T00:00:00Z",
            effective_to: null,
            recorded_at: "2024-01-01T00:00:00Z",
            state: "Accepted",
            known_at: "2024-01-01T00:00:00Z",
            effective_at: "2024-01-01T00:00:00Z",
            sequence: 1,
            evidence: [],
          },
          history: {
            assertion_id: "assertion-1",
            effective_from: "2024-01-01T00:00:00Z",
            effective_to: null,
            recorded_at: "2024-01-01T00:00:00Z",
            state: "Accepted",
            known_at: "2024-01-01T00:00:00Z",
            effective_at: "2024-01-01T00:00:00Z",
            events: [],
          },
        },
      });

      const user = userEvent.setup();
      render(<NetworkVisualization data={governedData} />);

      const canonicalButton = screen.getByRole("button", {
        name: /ASSET_2.*ASSET_1.*CORPORATE_LINK.*Governed/,
      });
      const reverseButton = screen.getByRole("button", {
        name: /ASSET_1.*ASSET_2.*CORPORATE_LINK.*Governed/,
      });

      await user.click(reverseButton);
      expect(reverseButton).toHaveAttribute("aria-pressed", "true");
      expect(canonicalButton).toHaveAttribute("aria-pressed", "false");

      await waitFor(() => {
        expect(mockedApi.getPublishedEdgeExplanation).toHaveBeenCalledWith(
          "pub-1",
          "pedge-2",
          expect.anything(),
        );
      });
    });
  });
});
