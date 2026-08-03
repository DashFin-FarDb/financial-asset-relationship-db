// Type definitions for the Financial Asset Relationship API

export interface Asset {
  id: string;
  symbol: string;
  name: string;
  asset_class: string;
  sector: string;
  price: number;
  market_cap?: number;
  currency: string;
  additional_fields: Record<string, unknown>;
}

/**
 * Governed-edge metadata shared by `Relationship` and `VisualizationEdge`.
 * Kept as a single interface so the two response shapes cannot drift from
 * each other as the underlying API evolves.
 *
 * Note: despite the name, `scope_refs` currently contains only the governed
 * `predicate_id` for the edge (see `api/services/relationship_index.py`,
 * `"scope_refs": [predicate_id]`) -- it does NOT include the governed
 * `purpose`, which is not exposed at the edge/visualization level today.
 */
export interface GovernedEdgeMetadata {
  /** Present only when this edge is backed by a governed assertion. */
  assertion_id?: string | null;
  /** `"governed"` when backed by a published assertion; absent/`null` means legacy. */
  governance_status?: "governed" | null;
  /** Publication revision this governance metadata was resolved from. */
  revision_id?: string | null;
  /** Governed predicate-id scope reference(s) for this edge (see note above: no purpose is included). */
  scope_refs?: string[] | null;
}

export interface Relationship extends GovernedEdgeMetadata {
  source_id: string;
  target_id: string;
  relationship_type: string;
  strength: number;
}

export interface Metrics {
  total_assets: number;
  total_relationships: number;
  asset_classes: Record<string, number>;
  avg_degree: number;
  max_degree: number;
  network_density: number;
}

/**
 * A node in the 3-D visualisation graph.
 * Coordinates are Fibonacci-sphere positions; `size` is degree-scaled 5–20.
 */
export interface VisualizationNode {
  id: string;
  name: string;
  symbol: string;
  asset_class: string;
  /** Fibonacci-sphere x-coordinate. */
  x: number;
  /** Fibonacci-sphere y-coordinate. */
  y: number;
  /** Fibonacci-sphere z-coordinate. */
  z: number;
  color: string;
  /** Node size scaled by degree, clamped to 5–20. */
  size: number;
}

/** An edge in the 3-D visualisation graph. `strength` is normalised 0.0–1.0. */
export interface VisualizationEdge extends GovernedEdgeMetadata {
  source: string;
  target: string;
  relationship_type: string;
  /** Relationship strength, normalised to the range 0.0–1.0. */
  strength: number;
}

export interface VisualizationData {
  nodes: VisualizationNode[];
  edges: VisualizationEdge[];
  network_density: number;
}

/**
 * Paginated asset response.
 *
 * Contract:
 * - `page` is 1-indexed.
 * - `per_page` defaults to 50; maximum is 1,000.
 * - `total` is the exact count matching current filters (not an estimate).
 * - An out-of-range `page` returns an empty `items` array, not an error.
 * - Results are deterministically ordered by `asset.id ASC`.
 */
export interface AssetPageResponse {
  items: Asset[];
  total: number;
  page: number;
  per_page: number;
  hasMore: boolean;
}

// --- Governed assertion explanation (GRAC v1) ---
//
// These mirror the public, identity-redacted read models exposed by
// `GET /api/assertions/{assertion_id}` and `GET /api/assertions/{assertion_id}/history`
// (see `api/assertion_models.py`). Actor identity is never exposed on these public
// reads; only the authenticated command APIs (out of scope for this UI) carry actor_id.
//
// KNOWN LIMITATION (tracked for a follow-up backend change, out of scope here):
// both endpoints default `known_at`/`effective_at` to "now" server-side when the
// caller omits them. Neither response currently carries the graph publication's
// own `known_at`/`effective_at`/`published_at`, so a panel driven purely by
// `assertion_id` cannot guarantee its explanation matches the lifecycle state
// that was true when the displayed graph edge was published. Until the
// visualization/relationship API exposes that publication envelope, callers
// should treat this explanation as "as of now", not "as of the displayed graph".

export type LifecycleState =
  | "Proposed"
  | "Accepted"
  | "Rejected"
  | "Withdrawn"
  | "Disputed"
  | "Retracted"
  | "Superseded";

export type AuthorityRole = "proposer" | "acceptor" | "disputer" | "retractor";

export type EvidencePolarity = "supporting" | "opposing" | "contextual";

export type ConfidenceStatus = "assessed" | "not_assessed";

export type EvidenceVisibility =
  | "public"
  | "internal"
  | "restricted"
  | "confidential";

/** Redacted evidence metadata: bodies and restricted references are never included. */
export interface AssertionEvidence {
  evidence_id: string;
  polarity: EvidencePolarity;
  visibility: EvidenceVisibility;
  redacted: boolean;
  source_ref?: string | null;
  media_type?: string | null;
  content_sha256?: string | null;
  observed_at?: string | null;
  issued_at?: string | null;
  licensing?: string | null;
  reuse_policy?: string | null;
  recorded_at?: string | null;
}

/**
 * Bitemporal lifecycle fields shared by the explanation and history read
 * models. Kept as a single interface so the two public response contracts
 * cannot diverge as the underlying API evolves.
 */
export interface AssertionLifecycleMetadata {
  assertion_id: string;
  effective_from: string;
  effective_to: string | null;
  recorded_at: string;
  state: LifecycleState;
  known_at: string | null;
  effective_at: string | null;
}

/** Public redacted explanation of one assertion as-of the requested bitemporal bounds. */
export interface AssertionExplanation extends AssertionLifecycleMetadata {
  predicate_id: string;
  subject_id: string;
  object_id: string;
  method_id: string;
  proposition: string;
  confidence_status: ConfidenceStatus;
  confidence_bp: number | null;
  confidence_type: string | null;
  confidence_method: string | null;
  sequence: number;
  evidence: AssertionEvidence[];
}

/** Identity-redacted lifecycle event: only the authority role, never actor_id. */
export interface AssertionPublicEvent {
  event_id: string;
  assertion_id: string;
  sequence: number;
  from_state: LifecycleState | null;
  to_state: LifecycleState;
  authority: AuthorityRole;
  recorded_at: string;
  successor_assertion_id?: string | null;
}

/** Public immutable assertion lifecycle history. */
export interface AssertionHistory extends AssertionLifecycleMetadata {
  events: AssertionPublicEvent[];
}

/** Optional bitemporal bounds accepted by the assertion read endpoints. */
export interface AssertionAsOfParams {
  known_at?: string;
  effective_at?: string;
}
