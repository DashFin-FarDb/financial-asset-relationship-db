/**
 * Comprehensive unit tests for NetworkVisualization component.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import NetworkVisualization from '../../app/components/NetworkVisualization';
import type { VisualizationData } from '../../app/types/api';
import { mockVisualizationData } from '../test-utils';

jest.mock('react-plotly.js', () => {
  return function MockPlot({ data }: { data: unknown }) {
    return (
      <div data-testid="mock-plot">
        <div data-testid="plot-data">{JSON.stringify(data)}</div>
      </div>
    );
  };
});

describe('NetworkVisualization Component', () => {
  it('should show empty data message when nodes or edges are missing', () => {
    render(<NetworkVisualization data={{ nodes: [], edges: [] }} />);
    expect(screen.getByText('Visualization data is missing nodes or edges.')).toBeInTheDocument();
  });

  it('should render plot with data', async () => {
    render(<NetworkVisualization data={mockVisualizationData} />);

    // New edge case tests
    const dataWithMissingCoords: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY' } as any], // missing x,y,z
      edges: [{ source: '1', target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithMissingCoords} />);
    await waitFor(() => {
      expect(screen.getByText(/missing coordinates/i)).toBeInTheDocument();
    });

    const dataWithNullEdge: VisualizationData = {
      nodes: [
        { id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY', x: 0, y: 0, z: 0, color: '#000', size: 5 },
        { id: '2', name: 'N2', symbol: 'S2', asset_class: 'BOND', x: 1, y: 1, z: 1, color: '#111', size: 5 },
      ],
      edges: [{ source: null as unknown as string, target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithNullEdge} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid edge/i)).toBeInTheDocument();
    });

    const dataWithUnknownAssetClass: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'UNKNOWN_CLASS' as any, x: 0, y: 0, z: 0, color: '#000', size: 5 }],
      edges: [],
    };
    render(<NetworkVisualization data={dataWithUnknownAssetClass} />);
    await waitFor(() => {
      expect(screen.getByText(/unknown asset class/i)).toBeInTheDocument();
    });

    render(<NetworkVisualization data={{} as unknown as VisualizationData} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid visualization data/i)).toBeInTheDocument();
    });

    // New edge case tests
    const dataWithMissingCoords2: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY' } as any], // missing x,y,z
      edges: [{ source: '1', target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithMissingCoords2} />);
    await waitFor(() => {
      expect(screen.getByText(/missing coordinates/i)).toBeInTheDocument();
    });

    const dataWithNullEdge: VisualizationData = {
      nodes: [
        { id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY', x: 0, y: 0, z: 0, color: '#000', size: 5 },
        { id: '2', name: 'N2', symbol: 'S2', asset_class: 'BOND', x: 1, y: 1, z: 1, color: '#111', size: 5 },
      ],
      edges: [{ source: null as unknown as string, target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithNullEdge} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid edge/i)).toBeInTheDocument();
    });

    const dataWithUnknownAssetClass: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'UNKNOWN_CLASS' as any, x: 0, y: 0, z: 0, color: '#000', size: 5 }],
      edges: [],
    };
    render(<NetworkVisualization data={dataWithUnknownAssetClass} />);
    await waitFor(() => {
      expect(screen.getByText(/unknown asset class/i)).toBeInTheDocument();
    });

    render(<NetworkVisualization data={{} as unknown as VisualizationData} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid visualization data/i)).toBeInTheDocument();
    });

    // New edge case tests
    const dataWithMissingCoords1: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY' } as any], // missing x,y,z
      edges: [{ source: '1', target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithMissingCoords1} />);
    await waitFor(() => {
      expect(screen.getByText(/missing coordinates/i)).toBeInTheDocument();
    });

    const dataWithNullEdge2: VisualizationData = {
      nodes: [
        { id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY', x: 0, y: 0, z: 0, color: '#000', size: 5 },
        { id: '2', name: 'N2', symbol: 'S2', asset_class: 'BOND', x: 1, y: 1, z: 1, color: '#111', size: 5 },
      ],
      edges: [{ source: null as unknown as string, target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithNullEdge2} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid edge/i)).toBeInTheDocument();
    });

    const dataWithUnknownAssetClass: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'UNKNOWN_CLASS' as any, x: 0, y: 0, z: 0, color: '#000', size: 5 }],
      edges: [],
    };
    render(<NetworkVisualization data={dataWithUnknownAssetClass} />);
    await waitFor(() => {
      expect(screen.getByText(/unknown asset class/i)).toBeInTheDocument();
    });

    render(<NetworkVisualization data={{} as unknown as VisualizationData} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid visualization data/i)).toBeInTheDocument();
    });

    // New edge case tests
    const dataWithMissingCoords: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY' } as any], // missing x,y,z
      edges: [{ source: '1', target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithMissingCoords} />);
    await waitFor(() => {
      expect(screen.getByText(/missing coordinates/i)).toBeInTheDocument();
    });

    const dataWithNullEdge: VisualizationData = {
      nodes: [
        { id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY', x: 0, y: 0, z: 0, color: '#000', size: 5 },
        { id: '2', name: 'N2', symbol: 'S2', asset_class: 'BOND', x: 1, y: 1, z: 1, color: '#111', size: 5 },
      ],
      edges: [{ source: null as unknown as string, target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithNullEdge} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid edge/i)).toBeInTheDocument();
    });

    const dataWithUnknownAssetClass: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'UNKNOWN_CLASS' as any, x: 0, y: 0, z: 0, color: '#000', size: 5 }],
      edges: [],
    };
    render(<NetworkVisualization data={dataWithUnknownAssetClass} />);
    await waitFor(() => {
      expect(screen.getByText(/unknown asset class/i)).toBeInTheDocument();
    });

    render(<NetworkVisualization data={{} as unknown as VisualizationData} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid visualization data/i)).toBeInTheDocument();
    });

    // New edge case tests
    const dataWithMissingCoords: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY' } as any], // missing x,y,z
      edges: [{ source: '1', target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithMissingCoords} />);
    await waitFor(() => {
      expect(screen.getByText(/missing coordinates/i)).toBeInTheDocument();
    });

    const dataWithNullEdge: VisualizationData = {
      nodes: [
        { id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY', x: 0, y: 0, z: 0, color: '#000', size: 5 },
        { id: '2', name: 'N2', symbol: 'S2', asset_class: 'BOND', x: 1, y: 1, z: 1, color: '#111', size: 5 },
      ],
      edges: [{ source: null as unknown as string, target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithNullEdge} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid edge/i)).toBeInTheDocument();
    });

    const dataWithUnknownAssetClass: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'UNKNOWN_CLASS' as any, x: 0, y: 0, z: 0, color: '#000', size: 5 }],
      edges: [],
    };
    render(<NetworkVisualization data={dataWithUnknownAssetClass} />);
    await waitFor(() => {
      expect(screen.getByText(/unknown asset class/i)).toBeInTheDocument();
    });

    render(<NetworkVisualization data={{} as unknown as VisualizationData} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid visualization data/i)).toBeInTheDocument();
    });

    // New edge case tests
    const dataWithMissingCoords2: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY' } as any], // missing x,y,z
      edges: [{ source: '1', target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithMissingCoords2} />);
    await waitFor(() => {
      expect(screen.getByText(/missing coordinates/i)).toBeInTheDocument();
    });

    const dataWithNullEdge: VisualizationData = {
      nodes: [
        { id: '1', name: 'N1', symbol: 'S1', asset_class: 'EQUITY', x: 0, y: 0, z: 0, color: '#000', size: 5 },
        { id: '2', name: 'N2', symbol: 'S2', asset_class: 'BOND', x: 1, y: 1, z: 1, color: '#111', size: 5 },
      ],
      edges: [{ source: null as unknown as string, target: '2', relationship_type: 'TEST', strength: 0.5 } as any],
    };
    render(<NetworkVisualization data={dataWithNullEdge} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid edge/i)).toBeInTheDocument();
    });

    const dataWithUnknownAssetClass: VisualizationData = {
      nodes: [{ id: '1', name: 'N1', symbol: 'S1', asset_class: 'UNKNOWN_CLASS' as any, x: 0, y: 0, z: 0, color: '#000', size: 5 }],
      edges: [],
    };
    render(<NetworkVisualization data={dataWithUnknownAssetClass} />);
    await waitFor(() => {
      expect(screen.getByText(/unknown asset class/i)).toBeInTheDocument();
    });

    render(<NetworkVisualization data={{} as unknown as VisualizationData} />);
    await waitFor(() => {
      expect(screen.getByText(/invalid visualization data/i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });
  });

  it('should process node coordinates', async () => {
    render(<NetworkVisualization data={mockVisualizationData} />);

    await waitFor(() => {
      const plotData = screen.getByTestId('plot-data');
      const data = JSON.parse(plotData.textContent || '[]');
      expect(data.length).toBeGreaterThan(0);
    });
  });

  it('should handle null data gracefully', () => {
    render(<NetworkVisualization data={null as unknown as VisualizationData} />);
    expect(screen.getByText('No visualization data available.')).toBeInTheDocument();
  });

  it('should update when data changes', async () => {
    const { rerender } = render(<NetworkVisualization data={mockVisualizationData} />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });

    const newData: VisualizationData = {
      nodes: [],
      edges: [],
    };

    rerender(<NetworkVisualization data={newData} />);
    expect(screen.getByText('Visualization data is missing nodes or edges.')).toBeInTheDocument();
  });

  it('should show a helpful message when dataset is too large', () => {
    const bigData: VisualizationData = {
      nodes: Array.from({ length: 600 }, (_, index) => ({
        id: `NODE_${index}`,
        name: `Node ${index}`,
        symbol: `SYM${index}`,
        asset_class: 'EQUITY',
        x: Math.random(),
        y: Math.random(),
        z: Math.random(),
        color: '#000000',
        size: 5,
      })),
      edges: Array.from({ length: 2001 }, (_, index) => ({
        source: 'NODE_0',
        target: `NODE_${index % 599 + 1}`,
        relationship_type: 'TEST',
        strength: 0.5,
      })),
    };

    render(<NetworkVisualization data={bigData} />);

    expect(
      screen.getByText(/Visualization is unavailable because the dataset is too large/)
    ).toBeInTheDocument();
  });
});

  describe('Accessibility and ARIA Attributes', () => {
    it('should have appropriate role for empty state', () => {
      render(<NetworkVisualization data={{ nodes: [], edges: [] }} />);
      
      const statusElement = screen.getByRole('status');
      expect(statusElement).toHaveTextContent('Visualization data is missing nodes or edges.');
    });

    it('should have alert role for too-large dataset', () => {
      const bigData: VisualizationData = {
        nodes: Array.from({ length: 600 }, (_, i) => ({
          id: `N${i}`, name: `Node ${i}`, symbol: `S${i}`,
          asset_class: 'EQUITY', x: 0, y: 0, z: 0, color: '#000', size: 5,
        })),
        edges: [{ source: 'N0', target: 'N1', relationship_type: 'TEST', strength: 0.5 }],
      };
      
      render(<NetworkVisualization data={bigData} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  describe('Edge Cases with Node and Edge Data', () => {
    it('should handle edges with missing source nodes', async () => {
      const invalidData: VisualizationData = {
        nodes: [mockVisualizationData.nodes[0]],
        edges: [{
          source: 'NONEXISTENT',
          target: mockVisualizationData.nodes[0].id,
          relationship_type: 'TEST',
          strength: 0.5,
        }],
      };
      
      render(<NetworkVisualization data={invalidData} />);
      
      await waitFor(() => {
        expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
      });
    });

    it('should handle edges with missing target nodes', async () => {
      const invalidData: VisualizationData = {
        nodes: [mockVisualizationData.nodes[0]],
        edges: [{
          source: mockVisualizationData.nodes[0].id,
          target: 'NONEXISTENT',
          relationship_type: 'TEST',
          strength: 0.5,
        }],
      };
      
      render(<NetworkVisualization data={invalidData} />);
      
      await waitFor(() => {
        expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
      });
    });

    it('should handle nodes with zero coordinates', async () => {
      const zeroData: VisualizationData = {
        nodes: [{
          id: 'ZERO',
          name: 'Zero Node',
          symbol: 'ZERO',
          asset_class: 'EQUITY',
          x: 0,
          y: 0,
          z: 0,
          color: '#000000',
          size: 5,
        }],
        edges: [],
      };
      
      render(<NetworkVisualization data={zeroData} />);
      
      await waitFor(() => {
        const plotData = screen.getByTestId('plot-data');
        expect(plotData).toBeInTheDocument();
      });
    });

    it('should handle nodes with negative coordinates', async () => {
      const negativeData: VisualizationData = {
        nodes: [{
          id: 'NEG',
          name: 'Negative Node',
          symbol: 'NEG',
          asset_class: 'EQUITY',
          x: -10,
          y: -20,
          z: -30,
          color: '#000000',
          size: 5,
        }],
        edges: [],
      };
      
      render(<NetworkVisualization data={negativeData} />);
      
      await waitFor(() => {
        expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
      });
    });

    it('should handle edges with zero strength', async () => {
      const zeroStrengthData: VisualizationData = {
        nodes: mockVisualizationData.nodes,
        edges: [{
          source: mockVisualizationData.nodes[0].id,
          target: mockVisualizationData.nodes[1].id,
          relationship_type: 'WEAK',
          strength: 0,
        }],
      };
      
      render(<NetworkVisualization data={zeroStrengthData} />);
      
      await waitFor(() => {
        expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
      });
    });

    it('should handle edges with maximum strength', async () => {
      const maxStrengthData: VisualizationData = {
        nodes: mockVisualizationData.nodes,
        edges: [{
          source: mockVisualizationData.nodes[0].id,
          target: mockVisualizationData.nodes[1].id,
          relationship_type: 'STRONG',
          strength: 1.0,
        }],
      };
      
      render(<NetworkVisualization data={maxStrengthData} />);
      
      await waitFor(() => {
        expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
      });
    });
  });

  describe('Performance and Size Limits', () => {
    it('should handle exactly at node limit', () => {
      const atLimitData: VisualizationData = {
        nodes: Array.from({ length: 500 }, (_, i) => ({
          id: `N${i}`, name: `Node ${i}`, symbol: `S${i}`,
          asset_class: 'EQUITY', x: i, y: i, z: i, color: '#000', size: 5,
        })),
        edges: [],
      };
      
      render(<NetworkVisualization data={atLimitData} />);
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('should handle exactly at edge limit', () => {
      const nodes = Array.from({ length: 50 }, (_, i) => ({
        id: `N${i}`, name: `Node ${i}`, symbol: `S${i}`,
        asset_class: 'EQUITY', x: 0, y: 0, z: 0, color: '#000', size: 5,
      }));
      
      const atLimitData: VisualizationData = {
        nodes,
        edges: Array.from({ length: 2000 }, (_, i) => ({
          source: `N${i % 50}`,
          target: `N${(i + 1) % 50}`,
          relationship_type: 'TEST',
          strength: 0.5,
        })),
      };
      
      render(<NetworkVisualization data={atLimitData} />);
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('should reject data just over node limit', () => {
      const overLimitData: VisualizationData = {
        nodes: Array.from({ length: 501 }, (_, i) => ({
          id: `N${i}`, name: `Node ${i}`, symbol: `S${i}`,
          asset_class: 'EQUITY', x: 0, y: 0, z: 0, color: '#000', size: 5,
        })),
        edges: [],
      };
      
      render(<NetworkVisualization data={overLimitData} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  describe('Data Updates and Re-renders', () => {
    it('should handle rapid data changes', async () => {
      const { rerender } = render(<NetworkVisualization data={mockVisualizationData} />);
      
      await waitFor(() => {
        expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
      });
      
      const newData1: VisualizationData = { nodes: [], edges: [] };
      rerender(<NetworkVisualization data={newData1} />);
      expect(screen.getByRole('status')).toBeInTheDocument();
      
      rerender(<NetworkVisualization data={mockVisualizationData} />);
      await waitFor(() => {
        expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
      });
    });

    it('should handle data change from valid to null', async () => {
      const { rerender } = render(<NetworkVisualization data={mockVisualizationData} />);
      
      await waitFor(() => {
        expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
      });
      
      rerender(<NetworkVisualization data={null as unknown as VisualizationData} />);
      expect(screen.getByText('No visualization data available.')).toBeInTheDocument();
    });
  });
