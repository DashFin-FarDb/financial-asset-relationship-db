import type {
  Asset,
  AssetPageResponse,
  Relationship,
  Metrics,
  VisualizationData,
  PublishedProjectionContextResponse,
  PublishedProjectionEdgeResponse,
  PublishedAssertionBundleResponse,
  PublishedEdgeExplanationResponse,
} from "../../app/types/api";

export const mockAssets: Asset[] = [
  {
    id: "ASSET_1",
    symbol: "AAPL",
    name: "Apple Inc.",
    asset_class: "EQUITY",
    sector: "Technology",
    price: 150.0,
    market_cap: 2400000000000,
    currency: "USD",
    additional_fields: {},
  },
  {
    id: "ASSET_2",
    symbol: "GOOGL",
    name: "Alphabet Inc.",
    asset_class: "EQUITY",
    sector: "Technology",
    price: 140.0,
    market_cap: 1800000000000,
    currency: "USD",
    additional_fields: {},
  },
];

export const mockAssetsPage: AssetPageResponse = {
  items: mockAssets,
  total: 2,
  page: 1,
  per_page: 50,
  hasMore: false,
};

export const mockAsset: Asset = {
  id: "ASSET_1",
  symbol: "AAPL",
  name: "Apple Inc.",
  asset_class: "EQUITY",
  sector: "Technology",
  price: 150.0,
  market_cap: 2400000000000,
  currency: "USD",
  additional_fields: {
    pe_ratio: 25.5,
    dividend_yield: 0.005,
  },
};

export const mockAssetClasses = {
  asset_classes: ["EQUITY", "FIXED_INCOME", "COMMODITY", "CURRENCY"],
};

export const mockSectors = {
  sectors: ["Energy", "Financials", "Technology"],
};

export const mockRelationships: Relationship[] = [
  {
    source_id: "ASSET_1",
    target_id: "ASSET_2",
    relationship_type: "SAME_SECTOR",
    strength: 0.8,
  },
  {
    source_id: "ASSET_1",
    target_id: "ASSET_3",
    relationship_type: "ISSUER",
    strength: 0.95,
  },
];

export const mockAllRelationships: Relationship[] = [
  {
    source_id: "ASSET_1",
    target_id: "ASSET_2",
    relationship_type: "SAME_SECTOR",
    strength: 0.8,
  },
  {
    source_id: "ASSET_3",
    target_id: "ASSET_4",
    relationship_type: "COMMODITY_EXPOSURE",
    strength: 0.6,
  },
];

export const mockMetrics: Metrics = {
  total_assets: 15,
  total_relationships: 42,
  asset_classes: {
    EQUITY: 6,
    FIXED_INCOME: 4,
    COMMODITY: 3,
    CURRENCY: 2,
  },
  avg_degree: 5.6,
  max_degree: 12,
  network_density: 0.42,
};

export const mockVisualizationData: VisualizationData = {
  nodes: [
    {
      id: "ASSET_1",
      name: "Apple Inc.",
      symbol: "AAPL",
      asset_class: "EQUITY",
      x: 1.5,
      y: 2.3,
      z: 0.8,
      color: "#1f77b4",
      size: 10,
    },
    {
      id: "ASSET_2",
      name: "Microsoft Corp.",
      symbol: "MSFT",
      asset_class: "EQUITY",
      x: 2.5,
      y: 3.3,
      z: 1.2,
      color: "#ff7f0e",
      size: 12,
    },
  ],
  edges: [
    {
      edge_id: "edge-1",
      source: "ASSET_1",
      target: "ASSET_2",
      relationship_type: "TEST",
      strength: 0.7,
    },
  ],
  network_density: 0.42,
};

export const mockVizData: VisualizationData = {
  nodes: [
    {
      id: "ASSET_1",
      name: "Apple Inc.",
      symbol: "AAPL",
      asset_class: "EQUITY",
      x: 1.5,
      y: 2.3,
      z: 0.8,
      color: "#1f77b4",
      size: 10,
    },
    {
      id: "ASSET_2",
      name: "Gold",
      symbol: "GOLD",
      asset_class: "COMMODITY",
      x: -1.2,
      y: 0.5,
      z: 1.9,
      color: "#ff7f0e",
      size: 8,
    },
  ],
  edges: [
    {
      edge_id: "edge-viz-1",
      source: "ASSET_1",
      target: "ASSET_2",
      relationship_type: "COMMODITY_EXPOSURE",
      strength: 0.7,
    },
  ],
  network_density: 0.42,
};

export const mockPublishedProjectionContext: PublishedProjectionContextResponse =
  {
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
    edge_set_hash: "sha256-edges-123",
    projection_hash: "sha256-proj-456",
    governed_scopes: [
      {
        purpose: "financial-relationship-graph",
        predicate_id: "predicate-issuer",
      },
    ],
  };

export const mockPublishedProjectionEdge: PublishedProjectionEdgeResponse = {
  projection_edge_id: "pedge-1",
  source: "ASSET_2",
  target: "ASSET_1",
  relationship_type: "CORPORATE_LINK",
  strength: "0.90",
  direction: "directional",
  assertion_id: "assertion-1",
};

export const mockPublishedAssertionBundle: PublishedAssertionBundleResponse = {
  explanation: {
    assertion_id: "assertion-1",
    predicate_id: "predicate-issuer",
    subject_id: "ASSET_2",
    object_id: "ASSET_1",
    method_id: "method-1",
    proposition: "ASSET_2 is the issuer of ASSET_1",
    confidence_status: "assessed",
    confidence_bp: 9500,
    confidence_type: "statistical",
    confidence_method: "historical_filings",
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
      {
        event_id: "event-2",
        assertion_id: "assertion-1",
        sequence: 2,
        from_state: "Proposed",
        to_state: "Accepted",
        authority: "acceptor",
        recorded_at: "2024-01-01T00:00:00Z",
      },
    ],
  },
};

export const mockPublishedEdgeExplanation: PublishedEdgeExplanationResponse = {
  publication: mockPublishedProjectionContext,
  edge: mockPublishedProjectionEdge,
  assertion: mockPublishedAssertionBundle,
};
