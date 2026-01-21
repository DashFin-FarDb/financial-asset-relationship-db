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

export interface VisualizationNode {
  id: string;
  name: string;
  symbol: string;
  asset_class: string;
  x: number;
  y: number;
  z: number;
  color: string;
  size: number;
}

export interface VisualizationEdge {
  source: string;
  target: string;
  relationship_type: string;
  strength: number;
}

export interface VisualizationData {
  nodes: VisualizationNode[];
  edges: VisualizationEdge[];
}
