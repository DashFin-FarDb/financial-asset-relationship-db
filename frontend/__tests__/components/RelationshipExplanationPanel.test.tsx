import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import RelationshipExplanationPanel, {
  type ExplainableRelationship,
} from "../../app/components/RelationshipExplanationPanel";
import { api } from "../../app/lib/api";
import type {
  PublishedEdgeExplanationResponse,
  PublishedProjectionContextResponse,
} from "../../app/types/api";

jest.mock("../../app/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const legacyRelationship: ExplainableRelationship = {
  source: "ASSET_1",
  target: "ASSET_2",
  relationship_type: "SAME_SECTOR",
  strength: 0.8,
};

const governedRelationship: ExplainableRelationship = {
  source: "ASSET_1",
  target: "ASSET_3",
  relationship_type: "CORPORATE_LINK",
  strength: 0.5,
  assertion_id: "assertion-1",
  governance_status: "governed",
  revision_id: "rev-1",
  scope_refs: ["predicate-issuer"],
  projection_edge_id: "pedge-1",
};

const governedWithoutProjectionEdgeId: ExplainableRelationship = {
  ...governedRelationship,
  projection_edge_id: null,
};

const governedWithoutAssertionId: ExplainableRelationship = {
  ...governedRelationship,
  assertion_id: null,
};

const governedWithoutRevisionId: ExplainableRelationship = {
  ...governedRelationship,
  revision_id: null,
};

const mockPublication: PublishedProjectionContextResponse = {
  publication_id: "pub-1",
  revision_id: "rev-1",
  rebuild_job_id: "job-100",
  execution_id: "exec-200",
  published_at: "2024-01-01T12:00:00Z",
  purpose: "financial-relationship-graph",
  effective_at: "2024-01-01T12:00:00Z",
  known_at: "2024-01-01T12:00:00Z",
  contract_version: "grac-v1",
  projector_version: "v1.2.3",
  edge_set_hash: "sha256-edge-hash-val",
  projection_hash: "sha256-proj-hash-val",
  governed_scopes: [
    {
      purpose: "financial-relationship-graph",
      predicate_id: "predicate-issuer",
    },
  ],
};

const baseExplanationResponse: PublishedEdgeExplanationResponse = {
  publication: mockPublication,
  edge: {
    projection_edge_id: "pedge-1",
    source: "ASSET_1",
    target: "ASSET_3",
    relationship_type: "CORPORATE_LINK",
    strength: "0.50",
    direction: "directional",
    assertion_id: "assertion-1",
  },
  assertion: {
    explanation: {
      assertion_id: "assertion-1",
      predicate_id: "predicate-issuer",
      subject_id: "ASSET_1",
      object_id: "ASSET_3",
      method_id: "method-1",
      proposition: "ASSET_1 is the issuer of ASSET_3",
      confidence_status: "assessed",
      confidence_bp: 9500,
      confidence_type: "statistical",
      confidence_method: "manual-review",
      effective_from: "2024-01-01T00:00:00Z",
      effective_to: null,
      recorded_at: "2024-01-01T00:00:00Z",
      state: "Accepted",
      known_at: "2024-01-01T00:00:00Z",
      effective_at: "2024-01-01T00:00:00Z",
      sequence: 2,
      evidence: [
        {
          evidence_id: "evidence-public",
          polarity: "supporting",
          visibility: "public",
          redacted: false,
          source_ref: "https://example.com/filing",
        },
        {
          evidence_id: "evidence-restricted",
          polarity: "supporting",
          visibility: "restricted",
          redacted: true,
        },
      ],
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
        {
          event_id: "event-2",
          assertion_id: "assertion-1",
          sequence: 2,
          from_state: "Proposed",
          to_state: "Accepted",
          authority: "acceptor",
          recorded_at: "2024-01-02T00:00:00Z",
        },
      ],
    },
  },
};

describe("RelationshipExplanationPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows a placeholder when no relationship is selected", () => {
    render(<RelationshipExplanationPanel relationship={null} />);
    expect(
      screen.getByText("Select a relationship to see how it was determined."),
    ).toBeInTheDocument();
    expect(mockedApi.getPublishedEdgeExplanation).not.toHaveBeenCalled();
    expect(mockedApi.getAssertion).not.toHaveBeenCalled();
  });

  it("labels an ungoverned relationship as legacy without fetching", () => {
    render(<RelationshipExplanationPanel relationship={legacyRelationship} />);
    expect(screen.getByText("Legacy")).toBeInTheDocument();
    expect(screen.getByText(/outside any governed scope/)).toBeInTheDocument();
    expect(mockedApi.getPublishedEdgeExplanation).not.toHaveBeenCalled();
    expect(mockedApi.getAssertion).not.toHaveBeenCalled();
  });

  it.each([
    ["projection_edge_id", governedWithoutProjectionEdgeId],
    ["assertion_id", governedWithoutAssertionId],
    ["revision_id", governedWithoutRevisionId],
  ])(
    "shows a pending metadata view for a governed edge with incomplete %s",
    (_, relationshipFixture) => {
      render(
        <RelationshipExplanationPanel
          relationship={relationshipFixture}
          publicationId="pub-1"
        />,
      );
      expect(
        screen.getByText(
          /governed, but its publication or edge metadata is incomplete/,
        ),
      ).toBeInTheDocument();
      expect(mockedApi.getPublishedEdgeExplanation).not.toHaveBeenCalled();
    },
  );

  it("renders the full publication-bound governed explanation once fetched", async () => {
    mockedApi.getPublishedEdgeExplanation.mockResolvedValue(
      baseExplanationResponse,
    );

    render(
      <RelationshipExplanationPanel
        relationship={governedRelationship}
        publicationId="pub-1"
      />,
    );

    expect(
      screen.getByText("Loading governed explanation..."),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText("ASSET_1 is the issuer of ASSET_3"),
      ).toBeInTheDocument();
    });

    // Proves single bundled request called without generic assertion fallback or client temporal authority
    expect(mockedApi.getPublishedEdgeExplanation).toHaveBeenCalledTimes(1);
    expect(mockedApi.getPublishedEdgeExplanation).toHaveBeenCalledWith(
      "pub-1",
      "pedge-1",
      expect.anything(),
    );
    expect(mockedApi.getAssertion).not.toHaveBeenCalled();

    // Confidence vs projection strength distinct facts
    expect(screen.getByText(/statistical/)).toBeInTheDocument();
    expect(screen.getAllByText(/0\.50/).length).toBeGreaterThan(0);

    // Public evidence shows source ref; restricted evidence never leaks a body
    expect(
      screen.getByText(/Source ref: https:\/\/example\.com\/filing/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Evidence body and restricted references are not shown/),
    ).toBeInTheDocument();

    // Authority roles
    expect(screen.getAllByText(/Proposer of record/).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Determining authority \(acceptor\)/).length,
    ).toBeGreaterThan(0);

    // Publication provenance details rendered
    expect(screen.getByText("pub-1")).toBeInTheDocument();
    expect(screen.getByText("job-100")).toBeInTheDocument();
    expect(screen.getByText("exec-200")).toBeInTheDocument();
    expect(screen.getByText("grac-v1")).toBeInTheDocument();
    expect(screen.getByText("v1.2.3")).toBeInTheDocument();
    expect(screen.getByText("sha256-edge-hash-val")).toBeInTheDocument();
    expect(screen.getByText("sha256-proj-hash-val")).toBeInTheDocument();
    expect(
      screen.getByText("(financial-relationship-graph, predicate-issuer)"),
    ).toBeInTheDocument();
  });

  it.each([
    { httpStatus: 404, expectedText: /could not be found/ },
    { httpStatus: 503, expectedText: /temporarily unavailable/ },
  ])(
    "shows a bounded state without fallback to generic assertion endpoints on $httpStatus failure",
    async ({ httpStatus, expectedText }) => {
      mockedApi.getPublishedEdgeExplanation.mockRejectedValue({
        response: { status: httpStatus },
      });

      render(
        <RelationshipExplanationPanel
          relationship={governedRelationship}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(screen.getByText(expectedText)).toBeInTheDocument();
      });
      expect(mockedApi.getAssertion).not.toHaveBeenCalled();
    },
  );

  it("maps defensive response-identity mismatches to unavailable view", async () => {
    const mismatchedResponse: PublishedEdgeExplanationResponse = {
      ...baseExplanationResponse,
      edge: {
        ...baseExplanationResponse.edge,
        projection_edge_id: "mismatched-edge-id",
      },
    };
    mockedApi.getPublishedEdgeExplanation.mockResolvedValue(mismatchedResponse);

    render(
      <RelationshipExplanationPanel
        relationship={governedRelationship}
        publicationId="pub-1"
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Governance explanation is temporarily unavailable/),
      ).toBeInTheDocument();
    });
  });

  it("shows superseded chain information when a successor is recorded", async () => {
    mockedApi.getPublishedEdgeExplanation.mockResolvedValue({
      ...baseExplanationResponse,
      assertion: {
        explanation: {
          ...baseExplanationResponse.assertion.explanation,
          state: "Superseded",
        },
        history: {
          ...baseExplanationResponse.assertion.history,
          state: "Superseded",
          events: [
            ...baseExplanationResponse.assertion.history.events,
            {
              event_id: "event-3",
              assertion_id: "assertion-1",
              sequence: 3,
              from_state: "Accepted",
              to_state: "Superseded",
              authority: "acceptor",
              recorded_at: "2024-02-01T00:00:00Z",
              successor_assertion_id: "assertion-2",
            },
          ],
        },
      },
    });

    render(
      <RelationshipExplanationPanel
        relationship={governedRelationship}
        publicationId="pub-1"
      />,
    );

    await waitFor(() => {
      expect(
        screen.getAllByText((_, element) =>
          Boolean(
            element?.textContent?.includes(
              "does not expose a backward predecessor reference",
            ),
          ),
        ).length,
      ).toBeGreaterThan(0);
    });
    expect(
      screen.getAllByText((_, element) =>
        Boolean(
          element?.textContent?.includes("superseded by assertion assertion-2"),
        ),
      ).length,
    ).toBeGreaterThan(0);
  });

  it("re-fetches when the selected relationship or publication changes and suppresses stale state", async () => {
    mockedApi.getPublishedEdgeExplanation.mockResolvedValue(
      baseExplanationResponse,
    );

    const { rerender } = render(
      <RelationshipExplanationPanel
        relationship={governedRelationship}
        publicationId="pub-1"
      />,
    );

    await waitFor(() => {
      expect(mockedApi.getPublishedEdgeExplanation).toHaveBeenCalledWith(
        "pub-1",
        "pedge-1",
        expect.anything(),
      );
    });

    rerender(
      <RelationshipExplanationPanel
        relationship={legacyRelationship}
        publicationId="pub-1"
      />,
    );

    expect(screen.getByText("Legacy")).toBeInTheDocument();

    // Rerender with governedRelationship and a different publicationId ("pub-2") after legacy transition
    const pub2ExplanationResponse = {
      ...baseExplanationResponse,
      publication: {
        ...baseExplanationResponse.publication,
        publication_id: "pub-2",
      },
    };

    let resolvePub2: (
      value: PublishedEdgeExplanationResponse,
    ) => void = () => {};
    const pub2Promise = new Promise<PublishedEdgeExplanationResponse>(
      (resolve) => {
        resolvePub2 = resolve;
      },
    );
    mockedApi.getPublishedEdgeExplanation.mockReturnValue(pub2Promise);

    rerender(
      <RelationshipExplanationPanel
        relationship={governedRelationship}
        publicationId="pub-2"
      />,
    );

    // Stale-state suppression: should show the loading view because requestKey has changed
    expect(
      screen.getByText("Loading governed explanation..."),
    ).toBeInTheDocument();

    // Resolve the second fetch
    resolvePub2(pub2ExplanationResponse);

    await waitFor(() => {
      expect(mockedApi.getPublishedEdgeExplanation).toHaveBeenLastCalledWith(
        "pub-2",
        "pedge-1",
        expect.anything(),
      );
    });
  });

  it("renders edge ID, relationship type, source node, and target node for a legacy relationship", () => {
    const legacyWithId: ExplainableRelationship = {
      ...legacyRelationship,
      edge_id: "edge-legacy-123",
    };
    render(
      <RelationshipExplanationPanel
        relationship={legacyWithId}
        publicationId="pub-1"
      />,
    );

    expect(screen.getByText("Edge ID")).toBeInTheDocument();
    expect(screen.getByText("edge-legacy-123")).toBeInTheDocument();
    expect(screen.getByText("Relationship type")).toBeInTheDocument();
    expect(screen.getByText("SAME_SECTOR")).toBeInTheDocument();
    expect(screen.getByText("Source node")).toBeInTheDocument();
    expect(screen.getByText("ASSET_1")).toBeInTheDocument();
    expect(screen.getByText("Target node")).toBeInTheDocument();
    expect(screen.getByText("ASSET_2")).toBeInTheDocument();
  });

  it("invokes onDeselect when the Clear selection button is clicked", () => {
    const onDeselect = jest.fn();
    render(
      <RelationshipExplanationPanel
        relationship={legacyRelationship}
        publicationId="pub-1"
        onDeselect={onDeselect}
      />,
    );

    const clearButton = screen.getByRole("button", {
      name: "Clear relationship selection",
    });
    expect(clearButton).toBeInTheDocument();
    clearButton.click();
    expect(onDeselect).toHaveBeenCalledTimes(1);
  });

  describe("Institutional Action Layer", () => {
    it("governed relationship exposes only supported actions and unavailable mutation notice", async () => {
      mockedApi.getPublishedEdgeExplanation.mockResolvedValue(
        baseExplanationResponse,
      );

      render(
        <RelationshipExplanationPanel
          relationship={governedRelationship}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByText("ASSET_1 is the issuer of ASSET_3"),
        ).toBeInTheDocument();
      });

      // 1. Institutional Actions heading and context are present
      expect(screen.getByText("Institutional Actions")).toBeInTheDocument();
      expect(
        screen.getByTestId("institutional-action-context"),
      ).toHaveTextContent("pedge-1");

      // 2. Supported read-only actions are exposed
      const evidenceAction = screen.getByRole("button", {
        name: "Inspect evidence (2)",
      });
      const lifecycleAction = screen.getByRole("button", {
        name: "Inspect lifecycle (2)",
      });
      const provenanceAction = screen.getByRole("button", {
        name: "Inspect provenance",
      });

      expect(evidenceAction).toBeInTheDocument();
      expect(lifecycleAction).toBeInTheDocument();
      expect(provenanceAction).toBeInTheDocument();
      expect(evidenceAction).toHaveAttribute("aria-pressed", "false");

      // 3. Unavailable mutation notice is rendered
      expect(
        screen.getByText("Governance mutation unavailable"),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /no authorized mutation pathway \(Dispute, Accept, or Supersede\) is exposed by this public interface/i,
        ),
      ).toBeInTheDocument();

      // 4. Clicking a supported action focuses that section and toggles active view
      fireEvent.click(evidenceAction);
      expect(evidenceAction).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByText("Focused view:")).toBeInTheDocument();
      expect(screen.getByText("evidence")).toBeInTheDocument();

      // Show all button is now present and restores full view
      const showAllButton = screen.getByRole("button", {
        name: "Show all sections",
      });
      expect(showAllButton).toBeInTheDocument();
      fireEvent.click(showAllButton);
      expect(evidenceAction).toHaveAttribute("aria-pressed", "false");
      expect(screen.queryByText("Focused view:")).not.toBeInTheDocument();
    });

    it("resets dossier focus state when relationship data changes, including refreshes with unchanged edge IDs", async () => {
      mockedApi.getPublishedEdgeExplanation.mockResolvedValue(
        baseExplanationResponse,
      );

      const { rerender } = render(
        <RelationshipExplanationPanel
          relationship={governedRelationship}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /Inspect evidence/i }),
        ).toBeInTheDocument();
      });

      const evidenceButton = screen.getByRole("button", {
        name: /Inspect evidence/i,
      });
      fireEvent.click(evidenceButton);
      expect(screen.getByText("Focused view:")).toBeInTheDocument();
      expect(screen.getByText("evidence")).toBeInTheDocument();

      // Refresh with refreshed relationship object where edge ID remains unchanged
      const refreshedSameEdge: ExplainableRelationship = {
        ...governedRelationship,
        strength: 0.95,
      };

      rerender(
        <RelationshipExplanationPanel
          relationship={refreshedSameEdge}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(screen.queryByText("Focused view:")).not.toBeInTheDocument();
      });
      expect(
        screen.getByRole("button", { name: /Inspect evidence/i }),
      ).toHaveAttribute("aria-pressed", "false");
    });

    it("legacy relationship exposes no governed actions", () => {
      render(
        <RelationshipExplanationPanel
          relationship={legacyRelationship}
          publicationId="pub-1"
        />,
      );

      expect(screen.getByText("Legacy")).toBeInTheDocument();
      expect(
        screen.queryByText("Institutional Actions"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Inspect evidence/i }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Inspect lifecycle/i }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Inspect provenance/i }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(
          "No governed institutional actions available for legacy relationships.",
        ),
      ).toBeInTheDocument();
    });

    it("action context remains bound to canonical edge_id", async () => {
      mockedApi.getPublishedEdgeExplanation.mockResolvedValue(
        baseExplanationResponse,
      );

      const governedWithCanonicalEdgeId: ExplainableRelationship = {
        ...governedRelationship,
        edge_id: "edge-canonical-xyz-999",
      };

      render(
        <RelationshipExplanationPanel
          relationship={governedWithCanonicalEdgeId}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("institutional-action-context"),
        ).toHaveTextContent("edge-canonical-xyz-999");
      });
    });

    it("deselection removes the action context", async () => {
      mockedApi.getPublishedEdgeExplanation.mockResolvedValue(
        baseExplanationResponse,
      );

      const { rerender } = render(
        <RelationshipExplanationPanel
          relationship={governedRelationship}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("institutional-action-context"),
        ).toBeInTheDocument();
      });

      // Deselect by passing null relationship
      rerender(
        <RelationshipExplanationPanel
          relationship={null}
          publicationId="pub-1"
        />,
      );

      expect(
        screen.getByText("Select a relationship to see how it was determined."),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("institutional-action-context"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText("Institutional Actions"),
      ).not.toBeInTheDocument();
    });

    it("changing from governed edge A to governed edge B updates the action context", async () => {
      const edgeAResponse: PublishedEdgeExplanationResponse = {
        ...baseExplanationResponse,
        edge: {
          ...baseExplanationResponse.edge,
          projection_edge_id: "pedge-A",
          assertion_id: "assertion-A",
        },
        assertion: {
          explanation: {
            ...baseExplanationResponse.assertion.explanation,
            assertion_id: "assertion-A",
            proposition: "Edge A proposition",
          },
          history: {
            ...baseExplanationResponse.assertion.history,
            assertion_id: "assertion-A",
          },
        },
      };

      const edgeBResponse: PublishedEdgeExplanationResponse = {
        ...baseExplanationResponse,
        edge: {
          ...baseExplanationResponse.edge,
          projection_edge_id: "pedge-B",
          assertion_id: "assertion-B",
        },
        assertion: {
          explanation: {
            ...baseExplanationResponse.assertion.explanation,
            assertion_id: "assertion-B",
            proposition: "Edge B proposition",
          },
          history: {
            ...baseExplanationResponse.assertion.history,
            assertion_id: "assertion-B",
          },
        },
      };

      mockedApi.getPublishedEdgeExplanation.mockImplementation(
        (_pubId, projectionEdgeId) => {
          if (projectionEdgeId === "pedge-A") {
            return Promise.resolve(edgeAResponse);
          }
          return Promise.resolve(edgeBResponse);
        },
      );

      const edgeA: ExplainableRelationship = {
        ...governedRelationship,
        edge_id: "edge-A",
        projection_edge_id: "pedge-A",
        assertion_id: "assertion-A",
      };

      const edgeB: ExplainableRelationship = {
        ...governedRelationship,
        edge_id: "edge-B",
        projection_edge_id: "pedge-B",
        assertion_id: "assertion-B",
      };

      const { rerender } = render(
        <RelationshipExplanationPanel
          relationship={edgeA}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(screen.getByText("Edge A proposition")).toBeInTheDocument();
        expect(
          screen.getByTestId("institutional-action-context"),
        ).toHaveTextContent("edge-A");
      });

      // Switch to edge B
      rerender(
        <RelationshipExplanationPanel
          relationship={edgeB}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(screen.getByText("Edge B proposition")).toBeInTheDocument();
        expect(
          screen.getByTestId("institutional-action-context"),
        ).toHaveTextContent("edge-B");
      });
    });

    it("identical source/target pairs with different edge IDs remain distinct in action context", async () => {
      const resp1: PublishedEdgeExplanationResponse = {
        ...baseExplanationResponse,
        edge: {
          ...baseExplanationResponse.edge,
          projection_edge_id: "pedge-pair-1",
          assertion_id: "assertion-pair-1",
        },
        assertion: {
          explanation: {
            ...baseExplanationResponse.assertion.explanation,
            assertion_id: "assertion-pair-1",
            proposition: "Proposition 1 for identical pair",
          },
          history: {
            ...baseExplanationResponse.assertion.history,
            assertion_id: "assertion-pair-1",
          },
        },
      };

      const resp2: PublishedEdgeExplanationResponse = {
        ...baseExplanationResponse,
        edge: {
          ...baseExplanationResponse.edge,
          projection_edge_id: "pedge-pair-2",
          assertion_id: "assertion-pair-2",
        },
        assertion: {
          explanation: {
            ...baseExplanationResponse.assertion.explanation,
            assertion_id: "assertion-pair-2",
            proposition: "Proposition 2 for identical pair",
          },
          history: {
            ...baseExplanationResponse.assertion.history,
            assertion_id: "assertion-pair-2",
          },
        },
      };

      mockedApi.getPublishedEdgeExplanation.mockImplementation(
        (_pubId, projectionEdgeId) => {
          if (projectionEdgeId === "pedge-pair-1") {
            return Promise.resolve(resp1);
          }
          return Promise.resolve(resp2);
        },
      );

      const rel1: ExplainableRelationship = {
        source: "ASSET_X",
        target: "ASSET_Y",
        relationship_type: "CORPORATE_LINK",
        strength: 0.5,
        governance_status: "governed",
        revision_id: "rev-1",
        edge_id: "edge-pair-1",
        projection_edge_id: "pedge-pair-1",
        assertion_id: "assertion-pair-1",
      };

      const rel2: ExplainableRelationship = {
        source: "ASSET_X",
        target: "ASSET_Y",
        relationship_type: "CORPORATE_LINK",
        strength: 0.7,
        governance_status: "governed",
        revision_id: "rev-1",
        edge_id: "edge-pair-2",
        projection_edge_id: "pedge-pair-2",
        assertion_id: "assertion-pair-2",
      };

      const { rerender } = render(
        <RelationshipExplanationPanel
          relationship={rel1}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByText("Proposition 1 for identical pair"),
        ).toBeInTheDocument();
        expect(
          screen.getByTestId("institutional-action-context"),
        ).toHaveTextContent("edge-pair-1");
      });

      rerender(
        <RelationshipExplanationPanel
          relationship={rel2}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByText("Proposition 2 for identical pair"),
        ).toBeInTheDocument();
        expect(
          screen.getByTestId("institutional-action-context"),
        ).toHaveTextContent("edge-pair-2");
      });
    });

    it("unsupported mutations are not presented as executable actions", async () => {
      mockedApi.getPublishedEdgeExplanation.mockResolvedValue(
        baseExplanationResponse,
      );

      render(
        <RelationshipExplanationPanel
          relationship={governedRelationship}
          publicationId="pub-1"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByText("ASSET_1 is the issuer of ASSET_3"),
        ).toBeInTheDocument();
      });

      // Verify that no buttons exist for mutating operations
      const mutationButtonNames = [
        /^accept$/i,
        /^accept\s+determination/i,
        /^dispute$/i,
        /^challenge$/i,
        /^supersede$/i,
        /^withdraw$/i,
        /^propose/i,
      ];

      for (const pattern of mutationButtonNames) {
        expect(
          screen.queryByRole("button", { name: pattern }),
        ).not.toBeInTheDocument();
      }

      // Explicit notice confirms no mutation pathway is exposed
      expect(
        screen.getByText("Governance mutation unavailable"),
      ).toBeInTheDocument();
    });
  });
});
