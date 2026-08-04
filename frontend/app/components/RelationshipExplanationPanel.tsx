"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type {
  AssertionExplanation,
  AssertionHistory,
  AssertionPublicEvent,
  PublishedEdgeExplanationResponse,
  PublishedProjectionContextResponse,
} from "../types/api";

export type ExplainableRelationship = Readonly<{
  source: string;
  target: string;
  relationship_type: string;
  strength: number;
  assertion_id?: string | null;
  governance_status?: "governed" | null;
  revision_id?: string | null;
  scope_refs?: string[] | null;
  projection_edge_id?: string | null;
}>;

type RelationshipExplanationPanelProps = Readonly<{
  relationship: ExplainableRelationship | null;
  publication?: PublishedProjectionContextResponse | null;
  publicationId?: string | null;
}>;

/**
 * The settled (non-loading) outcome of a fetch for a given request key. Only
 * completed results are ever stored in state; "loading" is derived by
 * comparing the current `requestKey` against `result.requestKey` rather than
 * stored as its own state value.
 */
type PanelResult =
  | Readonly<{ status: "not-found"; requestKey: string }>
  | Readonly<{ status: "unavailable"; requestKey: string }>
  | Readonly<{
      status: "ready";
      requestKey: string;
      payload: PublishedEdgeExplanationResponse;
    }>;

const AUTHORITY_LABELS: Record<string, string> = {
  proposer: "Proposer of record",
  acceptor: "Determining authority (acceptor)",
  disputer: "Determining authority (disputer)",
  retractor: "Determining authority (retractor)",
};

/** Format an ISO timestamp for display, or a bounded placeholder when absent. */
function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

/**
 * Derive the recorded proposer event and the most recent determining-authority
 * event from an assertion's public (identity-redacted) event history.
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

function relationshipHeading(relationship: ExplainableRelationship): string {
  return `${relationship.source} \u2192 ${relationship.target} (${relationship.relationship_type})`;
}

function PanelShell({
  heading,
  toneClassName,
  children,
}: Readonly<{
  heading: string;
  toneClassName: string;
  children: React.ReactNode;
}>) {
  return (
    <section
      aria-label="Relationship explanation"
      className={`p-4 border rounded-lg ${toneClassName}`}
    >
      <h3 className="font-semibold text-gray-900">{heading}</h3>
      {children}
    </section>
  );
}

function EmptySelectionView() {
  return (
    <output className="block p-4 text-sm text-gray-500">
      Select a relationship to see how it was determined.
    </output>
  );
}

function LegacyView({ heading }: Readonly<{ heading: string }>) {
  return (
    <PanelShell heading={heading} toneClassName="border-gray-200 bg-gray-50">
      <output className="block mt-2 text-sm text-gray-600">
        <span className="inline-block px-2 py-0.5 mr-2 text-xs font-medium rounded bg-gray-200 text-gray-700">
          Legacy
        </span>{" "}
        This relationship is outside any governed scope. No assertion, evidence,
        or lifecycle history is available for it.
      </output>
    </PanelShell>
  );
}

function PendingMetadataView({ heading }: Readonly<{ heading: string }>) {
  return (
    <PanelShell heading={heading} toneClassName="border-amber-200 bg-amber-50">
      <output className="block mt-2 text-sm text-amber-800">
        This relationship is governed, but its publication or edge metadata is
        incomplete. It may still be synchronizing.
      </output>
    </PanelShell>
  );
}

function LoadingView({ heading }: Readonly<{ heading: string }>) {
  return (
    <PanelShell heading={heading} toneClassName="border-gray-200">
      <output className="block mt-2 text-sm text-gray-500" aria-live="polite">
        Loading governed explanation...
      </output>
    </PanelShell>
  );
}

function NotFoundView({ heading }: Readonly<{ heading: string }>) {
  return (
    <PanelShell heading={heading} toneClassName="border-amber-200 bg-amber-50">
      <p className="mt-2 text-sm text-amber-800" role="alert">
        The governed assertion behind this relationship could not be found. It
        may be synchronizing with the latest publication.
      </p>
    </PanelShell>
  );
}

function UnavailableView({ heading }: Readonly<{ heading: string }>) {
  return (
    <PanelShell heading={heading} toneClassName="border-red-200 bg-red-50">
      <p className="mt-2 text-sm text-red-800" role="alert">
        Governance explanation is temporarily unavailable. The graph remains
        usable; please try again shortly.
      </p>
    </PanelShell>
  );
}

function ConfidenceAndTimeSummary({
  explanation,
  strength,
  persistedStrength,
}: Readonly<{
  explanation: AssertionExplanation;
  strength: number;
  persistedStrength?: string | null;
}>) {
  return (
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
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
          {persistedStrength ?? strength.toFixed(2)}{" "}
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
    </dl>
  );
}

function AuthoritySummary({
  history,
}: Readonly<{ history: AssertionHistory }>) {
  const summary = useMemo(
    () => deriveAuthoritySummary(history.events),
    [history],
  );
  if (!summary.proposer && !summary.determiner) return null;

  return (
    <div className="text-sm">
      <h4 className="font-medium text-gray-500">Authority</h4>
      <ul className="mt-1 space-y-1">
        {summary.proposer && (
          <li>
            {AUTHORITY_LABELS.proposer} {"\u2014"}{" "}
            {formatTimestamp(summary.proposer.recorded_at)}
          </li>
        )}
        {summary.determiner && (
          <li>
            {AUTHORITY_LABELS[summary.determiner.authority] ??
              "Determining authority"}{" "}
            {"\u2014"} {formatTimestamp(summary.determiner.recorded_at)}
          </li>
        )}
      </ul>
    </div>
  );
}

function EvidenceSummary({
  explanation,
}: Readonly<{ explanation: AssertionExplanation }>) {
  return (
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
              <span className="text-xs text-gray-500">({item.visibility})</span>
              {item.redacted ? (
                <p className="text-xs text-gray-500 italic">
                  Evidence body and restricted references are not shown.
                </p>
              ) : (
                item.source_ref && (
                  <p className="text-xs text-gray-700 mt-1">
                    Source ref: {item.source_ref}
                  </p>
                )
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LifecycleHistory({
  history,
}: Readonly<{ history: AssertionHistory }>) {
  const supersessionEvent = useMemo(
    () => findSupersessionEvent(history.events),
    [history],
  );
  return (
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
        <output className="block mt-1 text-xs text-amber-700">
          This assertion has been superseded by assertion{" "}
          {supersessionEvent.successor_assertion_id}. The public API does not
          expose a backward predecessor reference, so if you are viewing that
          successor assertion instead, its own predecessor cannot be looked up
          from here.
        </output>
      )}
    </div>
  );
}

function PublicationFooter({
  payload,
  relationship,
}: Readonly<{
  payload?: PublishedEdgeExplanationResponse | null;
  relationship: ExplainableRelationship;
}>) {
  const publication = payload?.publication;
  const edge = payload?.edge;

  return (
    <div className="text-xs text-gray-500 border-t border-gray-100 pt-2 space-y-1">
      <p className="font-medium text-gray-700">Publication Provenance</p>
      {publication ? (
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div>
            <dt className="inline font-medium">Publication ID: </dt>
            <dd className="inline font-mono">{publication.publication_id}</dd>
          </div>
          <div>
            <dt className="inline font-medium">Revision ID: </dt>
            <dd className="inline font-mono">{publication.revision_id}</dd>
          </div>
          <div>
            <dt className="inline font-medium">Rebuild Job ID: </dt>
            <dd className="inline font-mono">{publication.rebuild_job_id}</dd>
          </div>
          <div>
            <dt className="inline font-medium">Execution ID: </dt>
            <dd className="inline font-mono">{publication.execution_id}</dd>
          </div>
          <div>
            <dt className="inline font-medium">Published At: </dt>
            <dd className="inline">
              {formatTimestamp(publication.published_at)}
            </dd>
          </div>
          <div>
            <dt className="inline font-medium">Purpose: </dt>
            <dd className="inline">{publication.purpose}</dd>
          </div>
          <div>
            <dt className="inline font-medium">Contract Version: </dt>
            <dd className="inline">{publication.contract_version}</dd>
          </div>
          <div>
            <dt className="inline font-medium">Projector Version: </dt>
            <dd className="inline">{publication.projector_version}</dd>
          </div>
          <div className="col-span-1 sm:col-span-2">
            <dt className="inline font-medium">Edge-set Hash: </dt>
            <dd className="inline font-mono text-[10px] break-all">
              {publication.edge_set_hash}
            </dd>
          </div>
          <div className="col-span-1 sm:col-span-2">
            <dt className="inline font-medium">Projection Hash: </dt>
            <dd className="inline font-mono text-[10px] break-all">
              {publication.projection_hash}
            </dd>
          </div>
          {edge && (
            <>
              <div>
                <dt className="inline font-medium">Projection Edge ID: </dt>
                <dd className="inline font-mono">{edge.projection_edge_id}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Direction: </dt>
                <dd className="inline">{edge.direction}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Persisted Strength: </dt>
                <dd className="inline">{edge.strength}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Assertion ID: </dt>
                <dd className="inline font-mono">{edge.assertion_id}</dd>
              </div>
            </>
          )}
          <div className="col-span-1 sm:col-span-2">
            <dt className="inline font-medium">Governed Scopes: </dt>
            <dd className="inline">
              {publication.governed_scopes?.length
                ? publication.governed_scopes
                    .map((s) => `(${s.purpose}, ${s.predicate_id})`)
                    .join(", ")
                : "none"}
            </dd>
          </div>
        </dl>
      ) : (
        <p>
          Revision: {relationship.revision_id ?? "unknown"} | Scope:{" "}
          {relationship.scope_refs?.length
            ? relationship.scope_refs.join(", ")
            : "unknown"}
          {relationship.projection_edge_id &&
            ` | Edge ID: ${relationship.projection_edge_id}`}
        </p>
      )}
    </div>
  );
}

function ReadyView({
  heading,
  relationship,
  payload,
}: Readonly<{
  heading: string;
  relationship: ExplainableRelationship;
  payload: PublishedEdgeExplanationResponse;
}>) {
  const { explanation, history } = payload.assertion;
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

      <ConfidenceAndTimeSummary
        explanation={explanation}
        strength={relationship.strength}
        persistedStrength={payload.edge.strength}
      />
      <AuthoritySummary history={history} />
      <EvidenceSummary explanation={explanation} />
      <LifecycleHistory history={history} />
      <PublicationFooter payload={payload} relationship={relationship} />
    </section>
  );
}

async function fetchPublishedEdgeExplanation(
  publicationId: string,
  projectionEdgeId: string,
  requestKey: string,
  signal: AbortSignal,
  expectedRevisionId?: string | null,
  expectedAssertionId?: string | null,
): Promise<PanelResult | null> {
  const response = await api.getPublishedEdgeExplanation(
    publicationId,
    projectionEdgeId,
    signal,
  );
  if (signal.aborted) return null;

  // Defensive response-identity validation
  if (
    response.publication.publication_id !== publicationId ||
    (expectedRevisionId && response.publication.revision_id !== expectedRevisionId) ||
    response.edge.projection_edge_id !== projectionEdgeId ||
    (expectedAssertionId && response.edge.assertion_id !== expectedAssertionId) ||
    response.assertion.explanation.assertion_id !== response.edge.assertion_id ||
    response.assertion.history.assertion_id !== response.edge.assertion_id
  ) {
    return { status: "unavailable", requestKey };
  }

  return {
    status: "ready",
    requestKey,
    payload: response,
  };
}

/**
 * Fetch the explanation for a published governed edge, resolving to a settled `PanelResult`.
 */
async function fetchAssertionResult(
  projectionEdgeId: string | null | undefined,
  publicationId: string | null | undefined,
  expectedRevisionId: string | null | undefined,
  expectedAssertionId: string | null | undefined,
  signal: AbortSignal,
): Promise<PanelResult | null> {
  if (!publicationId || !projectionEdgeId) return null;
  const requestKey = `pub:${publicationId}:edge:${projectionEdgeId}`;

  try {
    return await fetchPublishedEdgeExplanation(
      publicationId,
      projectionEdgeId,
      requestKey,
      signal,
      expectedRevisionId,
      expectedAssertionId,
    );
  } catch (err) {
    if (signal.aborted) return null;
    const httpStatus = (err as { response?: { status?: number } })?.response
      ?.status;
    return {
      status: httpStatus === 404 ? "not-found" : "unavailable",
      requestKey,
    };
  }
}

function useAssertionResult(
  projectionEdgeId: string | null | undefined,
  publicationId: string | null | undefined,
  expectedRevisionId: string | null | undefined,
  expectedAssertionId: string | null | undefined,
): PanelResult | null {
  const [result, setResult] = useState<PanelResult | null>(null);

  const requestKey =
    publicationId && projectionEdgeId
      ? `pub:${publicationId}:edge:${projectionEdgeId}`
      : null;

  useEffect(() => {
    if (!requestKey || !publicationId || !projectionEdgeId) {
      return;
    }

    const controller = new AbortController();
    fetchAssertionResult(
      projectionEdgeId,
      publicationId,
      expectedRevisionId,
      expectedAssertionId,
      controller.signal,
    ).then((settled) => {
      if (settled) setResult(settled);
    });

    return () => controller.abort();
  }, [requestKey, projectionEdgeId, publicationId, expectedRevisionId, expectedAssertionId]);

  return result?.requestKey === requestKey ? result : null;
}

/** Discriminated description of what the panel should render next. */
type ViewState =
  | Readonly<{ kind: "empty" }>
  | Readonly<{ kind: "legacy"; heading: string }>
  | Readonly<{ kind: "pending"; heading: string }>
  | Readonly<{ kind: "loading"; heading: string }>
  | Readonly<{ kind: "not-found"; heading: string }>
  | Readonly<{ kind: "unavailable"; heading: string }>
  | Readonly<{
      kind: "ready";
      heading: string;
      relationship: ExplainableRelationship;
      payload: PublishedEdgeExplanationResponse;
    }>;

/**
 * Pure derivation of the panel's view state from its inputs.
 */
function resolveViewState(
  relationship: ExplainableRelationship | null,
  result: PanelResult | null,
  publicationId?: string | null,
): ViewState {
  if (!relationship) return { kind: "empty" };

  const heading = relationshipHeading(relationship);
  if (relationship.governance_status !== "governed") {
    return { kind: "legacy", heading };
  }

  const projectionEdgeId = relationship.projection_edge_id;
  if (!publicationId || !projectionEdgeId || !relationship.assertion_id || !relationship.revision_id) {
    return { kind: "pending", heading };
  }

  const requestKey = `pub:${publicationId}:edge:${projectionEdgeId}`;

  // "Loading" is derived, not stored
  if (result?.requestKey !== requestKey) return { kind: "loading", heading };

  if (result.status === "ready") {
    return {
      kind: "ready",
      heading,
      relationship,
      payload: result.payload,
    };
  }

  return { kind: result.status, heading };
}

/**
 * Render the subcomponent matching a resolved `ViewState`.
 */
function renderView(view: ViewState) {
  switch (view.kind) {
    case "empty":
      return <EmptySelectionView />;
    case "legacy":
      return <LegacyView heading={view.heading} />;
    case "pending":
      return <PendingMetadataView heading={view.heading} />;
    case "loading":
      return <LoadingView heading={view.heading} />;
    case "not-found":
      return <NotFoundView heading={view.heading} />;
    case "unavailable":
      return <UnavailableView heading={view.heading} />;
    case "ready":
      return (
        <ReadyView
          heading={view.heading}
          relationship={view.relationship}
          payload={view.payload}
        />
      );
  }
}

/**
 * Renders the governed explanation for a selected published edge, or a bounded
 * state when governance facts cannot be shown.
 */
export default function RelationshipExplanationPanel({
  relationship,
  publication,
  publicationId: publicationIdProp,
}: RelationshipExplanationPanelProps) {
  const publicationId = publication?.publication_id ?? publicationIdProp ?? null;
  const result = useAssertionResult(
    relationship?.projection_edge_id,
    publicationId,
    relationship?.revision_id,
    relationship?.assertion_id,
  );
  const view = resolveViewState(relationship, result, publicationId);
  return renderView(view);
}
