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

export interface Relationship {
  source_id: string;
  target_id: string;
  relationship_type: string;
  strength: number;
  /** Present only when this edge is backed by a governed assertion. */
  assertion_id?: string | null;
  /** `"governed"` when backed by a published assertion; absent/`null` means legacy. */
  governance_status?: "governed" | null;
  /** Publication revision this governance metadata was resolved from. */
  revision_id?: string | null;
  /** Governed `(purpose, predicate_id)` scope references for this edge. */
  scope_refs?: string[] | null;
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
export interface VisualizationEdge {
  source: string;
  target: string;
  relationship_type: string;
  /** Relationship strength, normalised to the range 0.0–1.0. */
  strength: number;
  /** Present only when this edge is backed by a governed assertion. */
  assertion_id?: string | null;
  /** `"governed"` when backed by a published assertion; absent/`null` means legacy. */
  governance_status?: "governed" | null;
  /** Publication revision this governance metadata was resolved from. */
  revision_id?: string | null;
  /** Governed `(purpose, predicate_id)` scope references for this edge. */
  scope_refs?: string[] | null;
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

export type EvidenceVisibility = "public" | "internal" | "restricted" | "confidential";

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

/** Public redacted explanation of one assertion as-of the requested bitemporal bounds. */
export interface AssertionExplanation {
  assertion_id: string;
  predicate_id: string;
  subject_id: string;
  object_id: string;
  method_id: string;
  proposition: string;
  confidence_status: ConfidenceStatus;
  confidence_bp: number | null;
  confidence_type: string | null;
  confidence_method: string | null;
  effective_from: string;
  effective_to: string | null;
  recorded_at: string;
  state: LifecycleState;
  known_at: string | null;
  effective_at: string | null;
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
export interface AssertionHistory {
  assertion_id: string;
  effective_from: string;
  effective_to: string | null;
  recorded_at: string;
  state: LifecycleState;
  known_at: string | null;
  effective_at: string | null;
  events: AssertionPublicEvent[];
}
