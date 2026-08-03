/**
 * Focused unit + accessibility tests for RelationshipExplanationPanel.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import RelationshipExplanationPanel, {
  type ExplainableRelationship,
} from "../../app/components/RelationshipExplanationPanel";
import { api } from "../../app/lib/api";
import type { AssertionExplanation, AssertionHistory } from "../../app/types/api";

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
};

const governedWithoutAssertionId: ExplainableRelationship = {
  ...governedRelationship,
  assertion_id: null,
};

const baseExplanation: AssertionExplanation = {
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
      content_sha256: "abc123",
    },
    {
      evidence_id: "evidence-restricted",
      polarity: "supporting",
      visibility: "restricted",
      redacted: true,
    },
  ],
};

const baseHistory: AssertionHistory = {
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
    expect(mockedApi.getAssertion).not.toHaveBeenCalled();
  });

  it("labels an ungoverned relationship as legacy without fetching", () => {
    render(<RelationshipExplanationPanel relationship={legacyRelationship} />);
    expect(screen.getByText("Legacy")).toBeInTheDocument();
    expect(
      screen.getByText(/outside any governed scope/),
    ).toBeInTheDocument();
    expect(mockedApi.getAssertion).not.toHaveBeenCalled();
  });

  it("shows a bounded unavailable state for a governed edge with no assertion id", () => {
    render(<RelationshipExplanationPanel relationship={governedWithoutAssertionId} />);
    expect(
      screen.getByText(/governed, but its assertion metadata is not yet available/),
    ).toBeInTheDocument();
    expect(mockedApi.getAssertion).not.toHaveBeenCalled();
  });

  it("renders the full governed explanation once fetched", async () => {
    mockedApi.getAssertion.mockResolvedValue(baseExplanation);
    mockedApi.getAssertionHistory.mockResolvedValue(baseHistory);

    render(<RelationshipExplanationPanel relationship={governedRelationship} />);

    expect(screen.getByText("Loading governed explanation...")).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText("ASSET_1 is the issuer of ASSET_3"),
      ).toBeInTheDocument();
    });

    // Confidence vs. projection strength are shown as distinct facts.
    expect(screen.getByText(/statistical/)).toBeInTheDocument();
    expect(screen.getByText(/0\.50/)).toBeInTheDocument();

    // Public evidence shows its digest; restricted evidence never leaks a body/reference.
    expect(screen.getByText(/SHA-256: abc123/)).toBeInTheDocument();
    expect(
      screen.getByText(/Evidence body and restricted references are not shown/),
    ).toBeInTheDocument();

    // Proposer and determining authority are distinct, identity-redacted roles.
    expect(screen.getAllByText(/Proposer of record/).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Determining authority \(acceptor\)/).length,
    ).toBeGreaterThan(0);
  });

  it.each([
    { httpStatus: 404, expectedText: /could not be found/ },
    { httpStatus: 503, expectedText: /temporarily unavailable/ },
  ])(
    "shows a bounded state without fabricating governance facts on a $httpStatus failure",
    async ({ httpStatus, expectedText }) => {
      mockedApi.getAssertion.mockRejectedValue({ response: { status: httpStatus } });
      mockedApi.getAssertionHistory.mockRejectedValue({ response: { status: httpStatus } });

      render(<RelationshipExplanationPanel relationship={governedRelationship} />);

      await waitFor(() => {
        expect(screen.getByText(expectedText)).toBeInTheDocument();
      });
    },
  );

  it("shows superseded chain information when a successor is recorded", async () => {
    mockedApi.getAssertion.mockResolvedValue({ ...baseExplanation, state: "Superseded" });
    mockedApi.getAssertionHistory.mockResolvedValue({
      ...baseHistory,
      state: "Superseded",
      events: [
        ...baseHistory.events,
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
    });

    render(<RelationshipExplanationPanel relationship={governedRelationship} />);

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

  it("passes identical as-of bounds to both the explanation and history requests", async () => {
    mockedApi.getAssertion.mockResolvedValue(baseExplanation);
    mockedApi.getAssertionHistory.mockResolvedValue(baseHistory);

    render(<RelationshipExplanationPanel relationship={governedRelationship} />);

    await waitFor(() => {
      expect(mockedApi.getAssertion).toHaveBeenCalledTimes(1);
      expect(mockedApi.getAssertionHistory).toHaveBeenCalledTimes(1);
    });

    const explanationParams = mockedApi.getAssertion.mock.calls[0][1];
    const historyParams = mockedApi.getAssertionHistory.mock.calls[0][1];
    expect(explanationParams).toBeDefined();
    expect(explanationParams).toEqual(historyParams);
  });

  it("re-fetches when the selected relationship changes and no stale state leaks through", async () => {
    mockedApi.getAssertion.mockResolvedValue(baseExplanation);
    mockedApi.getAssertionHistory.mockResolvedValue(baseHistory);

    const { rerender } = render(
      <RelationshipExplanationPanel relationship={governedRelationship} />,
    );

    await waitFor(() => {
      expect(mockedApi.getAssertion).toHaveBeenCalledWith(
        "assertion-1",
        expect.objectContaining({ known_at: expect.any(String) }),
        expect.anything(),
      );
    });

    rerender(<RelationshipExplanationPanel relationship={legacyRelationship} />);

    expect(screen.getByText("Legacy")).toBeInTheDocument();
  });
});
