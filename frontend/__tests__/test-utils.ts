import type { Asset, Relationship, Metrics, VisualizationData } from '../../app/types/api';

export const mockAssets: Asset[] = [
  {
    id: 'ASSET_1',
    symbol: 'AAPL',
    name: 'Apple Inc.',
    asset_class: 'EQUITY',
    sector: 'Technology',
    price: 150.0,
    market_cap: 2400000000000,
    currency: 'USD',
    additional_fields: {},
  },
  {
    id: 'ASSET_2',
    symbol: 'GOOGL',
    name: 'Alphabet Inc.',
    asset_class: 'EQUITY',
    sector: 'Technology',
    price: 140.0,
    market_cap: 1800000000000,
    currency: 'USD',
    additional_fields: {},
  },
];

export const mockAsset: Asset = {
  id: 'ASSET_1',
  symbol: 'AAPL',
  name: 'Apple Inc.',
  asset_class: 'EQUITY',
  sector: 'Technology',
  price: 150.0,
  market_cap: 2400000000000,
  currency: 'USD',
  additional_fields: {
    pe_ratio: 25.5,
    dividend_yield: 0.005,
  },
};

export const mockAssetClasses = {
  asset_classes: ['EQUITY', 'FIXED_INCOME', 'COMMODITY', 'CURRENCY'],
};

export const mockSectors = {
  sectors: ['Energy', 'Financials', 'Technology'],
};

export const mockRelationships: Relationship[] = [
  {
    source_id: 'ASSET_1',
    target_id: 'ASSET_2',
    relationship_type: 'SAME_SECTOR',
    strength: 0.8,
  },
  {
    source_id: 'ASSET_2',
    target_id: 'ASSET_1',
    relationship_type: 'PEER',
    strength: 0.75,
  },
];
  {
    source_id: 'ASSET_1',
    target_id: 'ASSET_2',
    relationship_type: 'SAME_SECTOR',
    strength: 0.8,
  },
  {
    source_id: 'ASSET_2',
    target_id: 'ASSET_1',
    relationship_type: 'PEER',
    strength: 0.75,
  },
];
  {
    source_id: 'ASSET_1',
    target_id: 'ASSET_2',
    relationship_type: 'SAME_SECTOR',
    strength: 0.8,
  },
  {
    source_id: 'ASSET_2',
    target_id: 'ASSET_1',
    relationship_type: 'PEER',
    strength: 0.75,
  },
];
  {
    source_id: 'ASSET_1',
    target_id: 'ASSET_2',
    relationship_type: 'SAME_SECTOR',
    strength: 0.8,
  },
  {
    source_id: 'ASSET_2',
    target_id: 'ASSET_1',
    relationship_type: 'PEER',
    strength: 0.75,
  },
];

export const mockAllRelationships: Relationship[] = [
  {
    source_id: 'ASSET_1',
    target_id: 'ASSET_2',
    relationship_type: 'SAME_SECTOR',
    strength: 0.8,
  },
  {
    source_id: 'ASSET_3',
    target_id: 'ASSET_4',
    relationship_type: 'COMMODITY_EXPOSURE',
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
      id: 'ASSET_1',
      name: 'Apple Inc.',
      symbol: 'AAPL',
      asset_class: 'EQUITY',
      x: 1.5,
      y: 2.3,
      z: 0.8,
      color: '#1f77b4',
      size: 10,
    },
    {
      id: 'ASSET_2',
      name: 'Microsoft Corp.',
      symbol: 'MSFT',
      asset_class: 'EQUITY',
      x: 2.5,
      y: 3.3,
      z: 1.2,
      color: '#ff7f0e',
      size: 12,
    },
  ],
  edges: [
    {
      source: 'ASSET_1',
      target: 'ASSET_2',
      relationship_type: 'TEST',
      strength: 0.7,
    },
  ],
};

/**
 * Visualization data with mixed asset classes for testing cross-asset relationships
 * (e.g., EQUITY to COMMODITY links)
 */
export const mockVizDataCrossAsset: VisualizationData = {
  nodes: [
    {
      id: 'ASSET_1',
      name: 'Apple Inc.',
      symbol: 'AAPL',
      asset_class: 'EQUITY',
      x: 1.5,
      y: 2.3,
      z: 0.8,
      color: '#1f77b4',
      size: 10,
    },
    {
      id: 'ASSET_2',
      name: 'Gold',
      symbol: 'GOLD',
      asset_class: 'COMMODITY',
      x: -1.2,
      y: 0.5,
      z: 1.9,
      color: '#ff7f0e',
      size: 8,
    },
  ],
  edges: [
    {
      source: 'ASSET_1',
      target: 'ASSET_2',
      relationship_type: 'COMMODITY_EXPOSURE',
      strength: 0.7,
    },
  ],
};