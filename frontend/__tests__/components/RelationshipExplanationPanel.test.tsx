import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
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
});
