/**
 * Comprehensive unit tests for MetricsDashboard component.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import MetricsDashboard from '../../app/components/MetricsDashboard';
import type { Metrics } from '../../app/types/api';
import { mockMetrics } from '../test-utils';

describe('MetricsDashboard Component', () => {
  it('should render all metric cards', () => {
    render(<MetricsDashboard metrics={mockMetrics} />);
    
    expect(screen.getByText('Total Assets')).toBeInTheDocument();
    expect(screen.getByText('Total Relationships')).toBeInTheDocument();
    expect(screen.getByText('Network Density')).toBeInTheDocument();
  });

  it('should display metrics correctly', () => {
    render(<MetricsDashboard metrics={mockMetrics} />);
    
    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('42.00%')).toBeInTheDocument();
  });

  it('should format network density as percentage', () => {
    render(<MetricsDashboard metrics={mockMetrics} />);
    expect(screen.getByText('42.00%')).toBeInTheDocument();
  });

  it('should display average degree with 2 decimals', () => {
    render(<MetricsDashboard metrics={mockMetrics} />);
    expect(screen.getByText('5.60')).toBeInTheDocument();
  });

  it('should display all asset classes', () => {
    render(<MetricsDashboard metrics={mockMetrics} />);
    
    expect(screen.getByText('EQUITY:')).toBeInTheDocument();
    expect(screen.getByText('6')).toBeInTheDocument();
    expect(screen.getByText('COMMODITY:')).toBeInTheDocument();
  });

  it('should handle zero metrics', () => {
    const zeroMetrics: Metrics = {
      total_assets: 0,
      total_relationships: 0,
      asset_classes: {},
      avg_degree: 0,
      max_degree: 0,
      network_density: 0,
    };
    
    render(<MetricsDashboard metrics={zeroMetrics} />);
    expect(screen.getByText('0.00%')).toBeInTheDocument();
  });
});

  describe('Accessibility Tests', () => {
    it('should have proper heading hierarchy', () => {
      render(<MetricsDashboard metrics={mockMetrics} />);
      
      const headings = screen.getAllByRole('heading', { level: 3 });
      expect(headings).toHaveLength(6);
      expect(headings[0]).toHaveTextContent('Total Assets');
    });

    it('should have semantic HTML structure', () => {
      const { container } = render(<MetricsDashboard metrics={mockMetrics} />);
      
      const grid = container.querySelector('.grid');
      expect(grid).toBeInTheDocument();
      expect(grid?.children.length).toBe(6);
    });

    it('should have readable text contrast', () => {
      const { container } = render(<MetricsDashboard metrics={mockMetrics} />);
      
      const headings = container.querySelectorAll('h3');
      headings.forEach(heading => {
        expect(heading).toHaveClass('text-gray-700');
      });
    });
  });

  describe('Edge Cases and Boundary Conditions', () => {
    it('should handle very large numbers gracefully', () => {
      const largeMetrics: Metrics = {
        total_assets: 999999,
        total_relationships: 9999999,
        asset_classes: { EQUITY: 100000 },
        avg_degree: 9999.99,
        max_degree: 99999,
        network_density: 1.0,
      };
      
      render(<MetricsDashboard metrics={largeMetrics} />);
      expect(screen.getByText('999999')).toBeInTheDocument();
      expect(screen.getByText('100.00%')).toBeInTheDocument();
    });

    it('should handle very small network density', () => {
      const sparseMetrics: Metrics = {
        ...mockMetrics,
        network_density: 0.001,
      };
      
      render(<MetricsDashboard metrics={sparseMetrics} />);
      expect(screen.getByText('0.10%')).toBeInTheDocument();
    });

    it('should handle fractional average degree', () => {
      const fractionalMetrics: Metrics = {
        ...mockMetrics,
        avg_degree: 3.14159,
      };
      
      render(<MetricsDashboard metrics={fractionalMetrics} />);
      expect(screen.getByText('3.14')).toBeInTheDocument();
    });

    it('should handle empty asset classes object', () => {
      const noClassesMetrics: Metrics = {
        ...mockMetrics,
        asset_classes: {},
      };
      
      const { container } = render(<MetricsDashboard metrics={noClassesMetrics} />);
      const assetClassCard = container.querySelectorAll('.bg-white')[5];
      expect(screen.getByText('Asset Classes')).toBeInTheDocument();
    });

    it('should handle many asset classes', () => {
      const manyClassesMetrics: Metrics = {
        ...mockMetrics,
        asset_classes: {
          EQUITY: 10,
          FIXED_INCOME: 20,
          COMMODITY: 30,
          CURRENCY: 40,
          DERIVATIVES: 50,
          REAL_ESTATE: 60,
          CRYPTO: 70,
        },
      };
      
      render(<MetricsDashboard metrics={manyClassesMetrics} />);
      expect(screen.getByText('EQUITY:')).toBeInTheDocument();
      expect(screen.getByText('CRYPTO:')).toBeInTheDocument();
      expect(screen.getByText('70')).toBeInTheDocument();
    });
  });

  describe('Data Formatting and Display', () => {
    it('should always format density with 2 decimal places', () => {
      const testCases = [0.1, 0.123, 0.999, 0.5555];
      
      testCases.forEach(density => {
        const testMetrics: Metrics = { ...mockMetrics, network_density: density };
        const { unmount } = render(<MetricsDashboard metrics={testMetrics} />);
        
        const formatted = (density * 100).toFixed(2) + '%';
        expect(screen.getByText(formatted)).toBeInTheDocument();
        
        unmount();
      });
    });

    it('should display asset class counts as integers', () => {
      render(<MetricsDashboard metrics={mockMetrics} />);
      
      Object.values(mockMetrics.asset_classes).forEach(count => {
        expect(screen.getByText(count.toString())).toBeInTheDocument();
      });
    });

    it('should handle max degree display', () => {
      const testMetrics: Metrics = {
        ...mockMetrics,
        max_degree: 1,
      };
      
      render(<MetricsDashboard metrics={testMetrics} />);
      expect(screen.getByText('1')).toBeInTheDocument();
    });
  });

  describe('Component Rendering and Updates', () => {
    it('should re-render when metrics change', () => {
      const { rerender } = render(<MetricsDashboard metrics={mockMetrics} />);
      expect(screen.getByText('15')).toBeInTheDocument();
      
      const newMetrics: Metrics = { ...mockMetrics, total_assets: 25 };
      rerender(<MetricsDashboard metrics={newMetrics} />);
      
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.queryByText('15')).not.toBeInTheDocument();
    });

    it('should maintain layout structure with different data', () => {
      const { container, rerender } = render(<MetricsDashboard metrics={mockMetrics} />);
      const initialCards = container.querySelectorAll('.bg-white').length;
      
      const newMetrics: Metrics = {
        total_assets: 1,
        total_relationships: 1,
        asset_classes: { TEST: 1 },
        avg_degree: 1.0,
        max_degree: 1,
        network_density: 0.01,
      };
      
      rerender(<MetricsDashboard metrics={newMetrics} />);
      const updatedCards = container.querySelectorAll('.bg-white').length;
      
      expect(updatedCards).toBe(initialCards);
    });
  });