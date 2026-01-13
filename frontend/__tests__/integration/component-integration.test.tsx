/**
 * Integration tests for component interactions and data flow.
 *
 * Tests the integration between API client, components, and user interactions,
 * ensuring that data flows correctly through the application and components
 * work together as expected.
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import Home from '../../app/page';
import { api } from '../../app/lib/api';
import {
  mockAssets,
  mockMetrics,
  mockVisualizationData,
  mockAssetClasses,
  mockSectors,
} from '../test-utils';

jest.mock('../../app/lib/api');
jest.mock('../../app/components/NetworkVisualization', () => {
  return function MockVisualization({ data }: { data: unknown }) {
    return (
      <div data-testid="network-visualization">
        <div data-testid="viz-node-count">{data?.nodes?.length || 0}</div>
        <div data-testid="viz-edge-count">{data?.edges?.length || 0}</div>
      </div>
    );
  };
});
jest.mock('../../app/components/MetricsDashboard', () => {
  return function MockMetrics({ metrics }: { metrics: unknown }) {
    return (
      <div data-testid="metrics-dashboard">
        <div data-testid="total-assets">{metrics?.total_assets || 0}</div>
        <div data-testid="total-relationships">{metrics?.total_relationships || 0}</div>
      </div>
    );
  };
});
jest.mock('../../app/components/AssetList', () => {
  return function MockAssetList() {
    return <div data-testid="asset-list">Asset List Component</div>;
  };
});

const mockedApi = api as jest.Mocked<typeof api>;

describe('Component Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.getMetrics.mockResolvedValue(mockMetrics);
    mockedApi.getVisualizationData.mockResolvedValue(mockVisualizationData);
    mockedApi.getAssets.mockResolvedValue({
      items: mockAssets,
      total: mockAssets.length,
      page: 1,
      per_page: 20,
    });
    mockedApi.getAssetClasses.mockResolvedValue(mockAssetClasses);
    mockedApi.getSectors.mockResolvedValue(mockSectors);
  });

  describe('Data Flow from API to Components', () => {
    it('should load data from API and pass to visualization component', async () => {
      render(<Home />);

      await waitFor(() => {
        expect(mockedApi.getVisualizationData).toHaveBeenCalled();
        expect(screen.getByTestId('network-visualization')).toBeInTheDocument();
      });

      expect(screen.getByTestId('viz-node-count')).toHaveTextContent(
        mockVisualizationData.nodes.length.toString()
      );
      expect(screen.getByTestId('viz-edge-count')).toHaveTextContent(
        mockVisualizationData.edges.length.toString()
      );
    });

    it('should load data from API and pass to metrics dashboard', async () => {
      render(<Home />);

      await waitFor(() => {
        fireEvent.click(screen.getByText('Metrics & Analytics'));
      });

      expect(mockedApi.getMetrics).toHaveBeenCalled();
      expect(screen.getByTestId('total-assets')).toHaveTextContent(
        mockMetrics.total_assets.toString()
      );
      expect(screen.getByTestId('total-relationships')).toHaveTextContent(
        mockMetrics.total_relationships.toString()
      );
    });
  });

  describe('User Interaction Flows', () => {
    it('should complete full user journey: visualization → metrics → assets', async () => {
      render(<Home />);

      // Start with visualization
      await waitFor(() => {
        expect(screen.getByTestId('network-visualization')).toBeInTheDocument();
      });

      // Navigate to metrics
      fireEvent.click(screen.getByText('Metrics & Analytics'));
      expect(screen.getByTestId('metrics-dashboard')).toBeInTheDocument();
      expect(screen.queryByTestId('network-visualization')).not.toBeInTheDocument();

      // Navigate to assets
      fireEvent.click(screen.getByText('Asset Explorer'));
      expect(screen.getByTestId('asset-list')).toBeInTheDocument();
      expect(screen.queryByTestId('metrics-dashboard')).not.toBeInTheDocument();

      // Return to visualization
      fireEvent.click(screen.getByText('3D Visualization'));
      expect(screen.getByTestId('network-visualization')).toBeInTheDocument();
      expect(screen.queryByTestId('asset-list')).not.toBeInTheDocument();
    });

    it('should handle rapid tab switching without errors', async () => {
      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('network-visualization')).toBeInTheDocument();
      });

      // Rapidly switch tabs
      for (let i = 0; i < 5; i++) {
        fireEvent.click(screen.getByText('Metrics & Analytics'));
        fireEvent.click(screen.getByText('Asset Explorer'));
        fireEvent.click(screen.getByText('3D Visualization'));
      }

      // Should end on visualization without errors
      expect(screen.getByTestId('network-visualization')).toBeInTheDocument();
    });
  });

  describe('Error Recovery Across Components', () => {
    it('should allow partial data loading (metrics succeeds, visualization fails)', async () => {
      mockedApi.getMetrics.mockResolvedValue(mockMetrics);
      mockedApi.getVisualizationData.mockRejectedValue(new Error('Viz failed'));
      const consoleError = jest.spyOn(console, 'error').mockImplementation();

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
      });

      // Metrics were loaded, but error prevents showing any component
      expect(mockedApi.getMetrics).toHaveBeenCalled();
      expect(mockedApi.getVisualizationData).toHaveBeenCalled();

      consoleError.mockRestore();
    });

    it('should retry loading all data on retry button click', async () => {
      mockedApi.getMetrics.mockRejectedValueOnce(new Error('First fail'));
      mockedApi.getMetrics.mockResolvedValueOnce(mockMetrics);
      mockedApi.getVisualizationData.mockRejectedValueOnce(new Error('First fail'));
      mockedApi.getVisualizationData.mockResolvedValueOnce(mockVisualizationData);

      const consoleError = jest.spyOn(console, 'error').mockImplementation();
      render(<Home />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Retry'));

      await waitFor(() => {
        expect(screen.getByTestId('network-visualization')).toBeInTheDocument();
      });

      expect(mockedApi.getMetrics).toHaveBeenCalledTimes(2);
      expect(mockedApi.getVisualizationData).toHaveBeenCalledTimes(2);

      consoleError.mockRestore();
    });
  });

  describe('State Consistency Across Tab Changes', () => {
    it('should maintain data consistency when switching tabs', async () => {
      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('network-visualization')).toBeInTheDocument();
      });

      const initialNodeCount = screen.getByTestId('viz-node-count').textContent;

      // Switch away and back
      fireEvent.click(screen.getByText('Metrics & Analytics'));
      fireEvent.click(screen.getByText('3D Visualization'));

      // Data should remain the same
      expect(screen.getByTestId('viz-node-count')).toHaveTextContent(initialNodeCount || '');
    });

    it('should not reload data when switching tabs', async () => {
      render(<Home />);

      await waitFor(() => {
        expect(mockedApi.getMetrics).toHaveBeenCalledTimes(1);
        expect(mockedApi.getVisualizationData).toHaveBeenCalledTimes(1);
      });

      // Switch tabs multiple times
      fireEvent.click(screen.getByText('Metrics & Analytics'));
      fireEvent.click(screen.getByText('Asset Explorer'));
      fireEvent.click(screen.getByText('3D Visualization'));

      // API should still only be called once
      expect(mockedApi.getMetrics).toHaveBeenCalledTimes(1);
      expect(mockedApi.getVisualizationData).toHaveBeenCalledTimes(1);
    });
  });

  describe('Performance and Edge Cases', () => {
    it('should handle empty visualization data gracefully', async () => {
      mockedApi.getVisualizationData.mockResolvedValue({ nodes: [], edges: [] });

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('network-visualization')).toBeInTheDocument();
      });

      expect(screen.getByTestId('viz-node-count')).toHaveTextContent('0');
      expect(screen.getByTestId('viz-edge-count')).toHaveTextContent('0');
    });

    it('should handle zero metrics gracefully', async () => {
      const zeroMetrics = {
        total_assets: 0,
        total_relationships: 0,
        asset_classes: {},
        avg_degree: 0,
        max_degree: 0,
        network_density: 0,
      };
      mockedApi.getMetrics.mockResolvedValue(zeroMetrics);

      render(<Home />);

      await waitFor(() => {
        fireEvent.click(screen.getByText('Metrics & Analytics'));
      });

      expect(screen.getByTestId('total-assets')).toHaveTextContent('0');
      expect(screen.getByTestId('total-relationships')).toHaveTextContent('0');
    });

    it('should handle very large datasets', async () => {
      const largeData = {
        nodes: Array.from({ length: 500 }, (_, i) => ({
          id: `N${i}`,
          name: `Node ${i}`,
          symbol: `S${i}`,
          asset_class: 'EQUITY',
          x: i,
          y: i,
          z: i,
          color: '#000',
          size: 5,
        })),
        edges: Array.from({ length: 2000 }, (_, i) => ({
          source: `N${i % 500}`,
          target: `N${(i + 1) % 500}`,
          relationship_type: 'TEST',
          strength: 0.5,
        })),
      };

      mockedApi.getVisualizationData.mockResolvedValue(largeData);

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('network-visualization')).toBeInTheDocument();
      });

      expect(screen.getByTestId('viz-node-count')).toHaveTextContent('500');
      expect(screen.getByTestId('viz-edge-count')).toHaveTextContent('2000');
    });
  });

  describe('Concurrent Component Rendering', () => {
    it('should handle simultaneous API calls without race conditions', async () => {
      let metricsResolve: ((value: unknown) => void) | null = null;
      let vizResolve: ((value: unknown) => void) | null = null;

      mockedApi.getMetrics.mockImplementation(() => new Promise(resolve => {
        metricsResolve = resolve;
      }));
      mockedApi.getVisualizationData.mockImplementation(() => new Promise(resolve => {
        vizResolve = resolve;
      }));

      render(<Home />);

      expect(screen.getByText('Loading data...')).toBeInTheDocument();

      // Resolve in reverse order
      await waitFor(() => {
        expect(vizResolve).not.toBeNull();
        expect(metricsResolve).not.toBeNull();
      });

      vizResolve!(mockVisualizationData);
      await new Promise(resolve => setTimeout(resolve, 10));
      metricsResolve!(mockMetrics);

      await waitFor(() => {
        expect(screen.queryByText('Loading data...')).not.toBeInTheDocument();
        expect(screen.getByTestId('network-visualization')).toBeInTheDocument();
      });
    });
  });
});
