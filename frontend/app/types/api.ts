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
}
