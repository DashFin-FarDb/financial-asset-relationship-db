"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type {
  AssertionExplanation,
  AssertionHistory,
  AssertionPublicEvent,
} from "../types/api";

/** The minimal edge shape the panel needs to explain a selected relationship. */
export type ExplainableRelationship = Readonly<{
  source: string;
  target: string;
  relationship_type: string;
  strength: number;
  assertion_id?: string | null;
  governance_status?: "governed" | null;
  revision_id?: string | null;
  scope_refs?: string[] | null;
}>;

type RelationshipExplanationPanelProps = Readonly<{
  relationship: ExplainableRelationship | null;
}>;

type PanelStatus = "idle" | "loading" | "ready" | "not-found" | "unavailable";

type PanelState = Readonly<{
  status: PanelStatus;
  explanation: AssertionExplanation | null;
  history: AssertionHistory | null;
}>;

const IDLE_STATE: PanelState = {
  status: "idle",
  explanation: null,
  history: null,
};

const AUTHORITY_LABELS: Record<string, string> = {
  proposer: "Proposer of record",
  acceptor: "Determining authority (acceptor)",
  disputer: "Determining authority (disputer)",
  retractor: "Determining authority (retractor)",
};

/**
 * Format an ISO timestamp for display, or a bounded placeholder when absent.
 */
function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

/**
 * Derive the recorded proposer event and the most recent determining-authority
 * event from an assertion's public (identity-redacted) event history. Only the
 * authority role is available on public reads -- actor identity is never
 * fabricated here.
 */
function deriveAuthoritySummary(events: readonly AssertionPublicEvent[]): {
  proposer: AssertionPublicEvent | null;
  determiner: AssertionPublicEvent | null;
} {
  const proposer =
    events.find((event) => event.authority === "proposer") ?? null;
  const determiner =
    [...events].reverse().find((event) => event.authority !== "proposer") ??
    null;
  return { proposer, determiner };
}

/**
 * Find the most recent event carrying a successor_assertion_id, if this
 * assertion has been superseded.
 */
function findSupersessionEvent(
  events: readonly AssertionPublicEvent[],
): AssertionPublicEvent | null {
  return (
    [...events]
      .reverse()
      .find((event) => Boolean(event.successor_assertion_id)) ?? null
  );
}

/**
 * Renders the governed explanation (evidence, authority, time, confidence,
 * supersession, and publication scope) for a selected relationship edge, or a
 * bounded legacy/unavailable/loading state when governance facts cannot be
 * shown. Never displays evidence bodies, restricted references, or invented
 * `CURRENT`/production-proof claims.
 */
export default function RelationshipExplanationPanel({
  relationship,
}: RelationshipExplanationPanelProps) {
  const [state, setState] = useState<PanelState>(IDLE_STATE);

  const isGoverned = relationship?.governance_status === "governed";
  const assertionId = isGoverned ? (relationship?.assertion_id ?? null) : null;

  // Track which assertionId the current `state` reflects so a change in the
  // selected relationship resets state synchronously during render, rather
  // than via a setState call inside the effect body (see React docs on
  // "adjusting state when a prop changes").
  const [trackedAssertionId, setTrackedAssertionId] = useState<string | null>(
    null,
  );
  if (assertionId !== trackedAssertionId) {
    setTrackedAssertionId(assertionId);
    setState(
      assertionId
        ? { status: "loading", explanation: null, history: null }
        : IDLE_STATE,
    );
  }

  useEffect(() => {
    if (!assertionId) {
      return;
    }

    const controller = new AbortController();

    Promise.all([
      api.getAssertion(assertionId, undefined, controller.signal),
      api.getAssertionHistory(assertionId, undefined, controller.signal),
    ])
      .then(([explanation, history]) => {
        if (controller.signal.aborted) return;
        setState({ status: "ready", explanation, history });
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        const httpStatus = err?.response?.status;
        setState({
          status: httpStatus === 404 ? "not-found" : "unavailable",
          explanation: null,
          history: null,
        });
      });

    return () => controller.abort();
  }, [assertionId]);

  const authoritySummary = useMemo(() => {
    if (!state.history) return null;
    return deriveAuthoritySummary(state.history.events);
  }, [state.history]);

  const supersessionEvent = useMemo(() => {
    if (!state.history) return null;
    return findSupersessionEvent(state.history.events);
  }, [state.history]);

  if (!relationship) {
    return (
      <div className="p-4 text-sm text-gray-500" role="status">
        Select a relationship to see how it was determined.
      </div>
    );
  }

  const heading = `${relationship.source} \u2192 ${relationship.target} (${relationship.relationship_type})`;

  if (!isGoverned) {
    return (
      <section
        aria-label="Relationship explanation"
        className="p-4 border border-gray-200 rounded-lg bg-gray-50"
      >
        <h3 className="font-semibold text-gray-900">{heading}</h3>
        <p className="mt-2 text-sm text-gray-600" role="status">
          <span className="inline-block px-2 py-0.5 mr-2 text-xs font-medium rounded bg-gray-200 text-gray-700">
            Legacy
          </span>
          This relationship is outside any governed scope. No assertion,
          evidence, or lifecycle history is available for it.
        </p>
      </section>
    );
  }

  if (!assertionId) {
    return (
      <section
        aria-label="Relationship explanation"
        className="p-4 border border-amber-200 rounded-lg bg-amber-50"
      >
        <h3 className="font-semibold text-gray-900">{heading}</h3>
        <p className="mt-2 text-sm text-amber-800" role="status">
          This relationship is governed, but its assertion metadata is not yet
          available. It may still be synchronizing.
        </p>
      </section>
    );
  }

  if (state.status === "loading" || state.status === "idle") {
    return (
      <section
        aria-label="Relationship explanation"
        className="p-4 border border-gray-200 rounded-lg"
      >
        <h3 className="font-semibold text-gray-900">{heading}</h3>
        <p
          className="mt-2 text-sm text-gray-500"
          role="status"
          aria-live="polite"
        >
          Loading governed explanation...
        </p>
      </section>
    );
  }

  if (state.status === "not-found") {
    return (
      <section
        aria-label="Relationship explanation"
        className="p-4 border border-amber-200 rounded-lg bg-amber-50"
      >
        <h3 className="font-semibold text-gray-900">{heading}</h3>
        <p className="mt-2 text-sm text-amber-800" role="alert">
          The governed assertion behind this relationship could not be found. It
          may be synchronizing with the latest publication.
        </p>
      </section>
    );
  }

  if (state.status === "unavailable" || !state.explanation || !state.history) {
    return (
      <section
        aria-label="Relationship explanation"
        className="p-4 border border-red-200 rounded-lg bg-red-50"
      >
        <h3 className="font-semibold text-gray-900">{heading}</h3>
        <p className="mt-2 text-sm text-red-800" role="alert">
          Governance explanation is temporarily unavailable. The graph remains
          usable; please try again shortly.
        </p>
      </section>
    );
  }

  const { explanation, history } = state;

  return (
    <section
      aria-label="Relationship explanation"
      className="p-4 border border-gray-200 rounded-lg space-y-4"
    >
      <header>
        <h3 className="font-semibold text-gray-900">{heading}</h3>
        <p className="text-sm text-gray-700 mt-1">{explanation.proposition}</p>
        <span className="inline-block mt-2 px-2 py-0.5 text-xs font-medium rounded bg-blue-100 text-blue-800">
          {explanation.state}
        </span>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="font-medium text-gray-500">Confidence</dt>
          <dd className="text-gray-800">
            {explanation.confidence_status === "assessed"
              ? `${explanation.confidence_type ?? "assessed"} (${
                  explanation.confidence_bp ?? "n/a"
                } bp, method: ${explanation.confidence_method ?? "unspecified"})`
              : "Not assessed"}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-gray-500">Projection strength</dt>
          <dd className="text-gray-800">
            {relationship.strength.toFixed(2)}{" "}
            <span className="text-xs text-gray-500">
              (distinct from confidence above)
            </span>
          </dd>
        </div>
        <div>
          <dt className="font-medium text-gray-500">Effective time</dt>
          <dd className="text-gray-800">
            {formatTimestamp(explanation.effective_from)}
            {explanation.effective_to
              ? ` \u2013 ${formatTimestamp(explanation.effective_to)}`
              : " (ongoing)"}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-gray-500">Recorded / known at</dt>
          <dd className="text-gray-800">
            {formatTimestamp(explanation.recorded_at)}
            {explanation.known_at
              ? ` (known: ${formatTimestamp(explanation.known_at)})`
              : ""}
          </dd>
        </div>
      </div>

      {authoritySummary &&
        (authoritySummary.proposer || authoritySummary.determiner) && (
          <div className="text-sm">
            <h4 className="font-medium text-gray-500">Authority</h4>
            <ul className="mt-1 space-y-1">
              {authoritySummary.proposer && (
                <li>
                  {AUTHORITY_LABELS.proposer} {"\u2014"}{" "}
                  {formatTimestamp(authoritySummary.proposer.recorded_at)}
                </li>
              )}
              {authoritySummary.determiner && (
                <li>
                  {AUTHORITY_LABELS[authoritySummary.determiner.authority] ??
                    "Determining authority"}{" "}
                  {"\u2014"}{" "}
                  {formatTimestamp(authoritySummary.determiner.recorded_at)}
                </li>
              )}
            </ul>
          </div>
        )}

      <div className="text-sm">
        <h4 className="font-medium text-gray-500">Evidence</h4>
        {explanation.evidence.length === 0 ? (
          <p className="text-gray-500 italic">No evidence recorded.</p>
        ) : (
          <ul className="mt-1 space-y-2">
            {explanation.evidence.map((item) => (
              <li
                key={item.evidence_id}
                className="border border-gray-100 rounded p-2"
              >
                <span className="font-medium">{item.polarity}</span>{" "}
                <span className="text-xs text-gray-500">
                  ({item.visibility})
                </span>
                {item.redacted ? (
                  <p className="text-xs text-gray-500 italic">
                    Evidence body and restricted references are not shown.
                  </p>
                ) : (
                  <div className="text-xs text-gray-600 space-y-0.5">
                    {item.source_ref && <p>Reference: {item.source_ref}</p>}
                    {item.content_sha256 && (
                      <p>SHA-256: {item.content_sha256}</p>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="text-sm">
        <h4 className="font-medium text-gray-500">Lifecycle history</h4>
        <ul className="mt-1 space-y-1">
          {history.events.map((event) => (
            <li key={event.event_id}>
              #{event.sequence} {event.from_state ?? "(none)"} {"\u2192"}{" "}
              {event.to_state}{" "}
              <span className="text-xs text-gray-500">
                ({AUTHORITY_LABELS[event.authority] ?? event.authority},{" "}
                {formatTimestamp(event.recorded_at)})
              </span>
              {event.successor_assertion_id && (
                <span className="text-xs text-gray-500">
                  {" "}
                  {"\u2014"} superseded by assertion{" "}
                  {event.successor_assertion_id}
                </span>
              )}
            </li>
          ))}
        </ul>
        {supersessionEvent?.successor_assertion_id && (
          <p className="mt-1 text-xs text-amber-700" role="status">
            This assertion has been superseded by assertion{" "}
            {supersessionEvent.successor_assertion_id}. Predecessor information
            is only available from that successor&apos;s own governed scope, if
            published.
          </p>
        )}
      </div>

      <div className="text-xs text-gray-500 border-t border-gray-100 pt-2">
        <p>
          Revision: {relationship.revision_id ?? "unknown"} | Scope:{" "}
          {relationship.scope_refs && relationship.scope_refs.length > 0
            ? relationship.scope_refs.join(", ")
            : "unknown"}
        </p>
      </div>
    </section>
  );
}
