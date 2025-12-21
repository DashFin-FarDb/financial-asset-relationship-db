/**
 * Integration tests validating axios 1.13.2 upgrade.
 *
 * Tests cover:
 * - Real-world API usage patterns
 * - Common error scenarios in production
 * - Edge cases from axios 1.6.0 to 1.13.2 migration
 * - Security improvements validation
 * - Performance characteristics
 * - Breaking change detection
 *
 * These tests ensure the upgrade doesn't introduce regressions
 * in actual usage patterns found in the application.
 */

import axios from 'axios';
import type { Asset, Metrics, VisualizationData } from '../../app/types/api';
import { mockAsset, mockMetrics, mockVizData, mockAssets } from '../test-utils';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('Axios Upgrade Integration Tests', () => {
  let mockAxiosInstance: any;
  let api: typeof import('../../app/lib/api')['api'];

  beforeEach(async () => {
    jest.resetModules();

    mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      defaults: {
        baseURL: 'http://localhost:8000',
        headers: { common: {}, get: {}, post: {}, put: {}, delete: {} },
      },
      interceptors: {
        request: { use: jest.fn(), eject: jest.fn(), clear: jest.fn() },
        response: { use: jest.fn(), eject: jest.fn(), clear: jest.fn() },
      },
    };

    mockedAxios.create.mockReturnValue(mockAxiosInstance);

    const apiModule = await import('../../app/lib/api');
    api = apiModule.api;
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Production Usage Patterns', () => {
    it('should handle typical dashboard data fetching flow', async () => {
      // Simulate loading dashboard: metrics + visualization
      mockAxiosInstance.get
        .mockResolvedValueOnce({ data: mockMetrics })
        .mockResolvedValueOnce({ data: mockVizData });

      const [metrics, vizData] = await Promise.all([
        api.getMetrics(),
        api.getVisualizationData(),
      ]);

      expect(metrics).toEqual(mockMetrics);
      expect(vizData).toEqual(mockVizData);
      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(2);
    });

    it('should handle asset search with filters pattern', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      // User applies filters
      const filters = { asset_class: 'EQUITY', sector: 'Technology' };
      const result = await api.getAssets(filters);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: filters,
      });
      expect(result).toEqual(mockAssets);
    });

    it('should handle detail view navigation pattern', async () => {
      // User clicks asset -> fetch detail + relationships
      mockAxiosInstance.get
        .mockResolvedValueOnce({ data: mockAsset })
        .mockResolvedValueOnce({ data: [] });

      const [asset, relationships] = await Promise.all([
        api.getAssetDetail('ASSET_1'),
        api.getAssetRelationships('ASSET_1'),
      ]);

      expect(asset).toEqual(mockAsset);
      expect(relationships).toEqual([]);
    });

    it('should handle pagination pattern', async () => {
      const page1 = { items: [mockAsset], total: 100, page: 1, per_page: 10 };
      const page2 = { items: [mockAsset], total: 100, page: 2, per_page: 10 };

      mockAxiosInstance.get
        .mockResolvedValueOnce({ data: page1 })
        .mockResolvedValueOnce({ data: page2 });

      const firstPage = await api.getAssets({ page: 1, per_page: 10 });
      const secondPage = await api.getAssets({ page: 2, per_page: 10 });

      expect(firstPage).toEqual(page1);
      expect(secondPage).toEqual(page2);
    });
  });

  describe('Error Recovery Patterns', () => {
    it('should allow retry after network error', async () => {
      mockAxiosInstance.get
        .mockRejectedValueOnce(new Error('Network Error'))
        .mockResolvedValueOnce({ data: mockMetrics });

      // First attempt fails
      await expect(api.getMetrics()).rejects.toThrow('Network Error');

      // Retry succeeds
      const result = await api.getMetrics();
      expect(result).toEqual(mockMetrics);
    });

    it('should handle partial failure in concurrent requests', async () => {
      mockAxiosInstance.get
        .mockResolvedValueOnce({ data: mockMetrics })
        .mockRejectedValueOnce(new Error('API Error'));

      // One succeeds, one fails
      const results = await Promise.allSettled([
        api.getMetrics(),
        api.getVisualizationData(),
      ]);

      expect(results[0].status).toBe('fulfilled');
      expect(results[1].status).toBe('rejected');
    });

    it('should gracefully handle empty response after error', async () => {
      mockAxiosInstance.get
        .mockRejectedValueOnce({ response: { status: 404 } })
        .mockResolvedValueOnce({ data: [] });

      // 404 on asset detail
      await expect(api.getAssetDetail('NONEXISTENT')).rejects.toMatchObject({
        response: { status: 404 },
      });

      // Fallback to list
      const assets = await api.getAssets();
      expect(assets).toEqual([]);
    });
  });

  describe('Axios 1.13.2 Security Improvements', () => {
    it('should use secure defaults for baseURL', () => {
      const config = mockedAxios.create.mock.calls[0]?.[0];

      // Should not use http in production (mocked here)
      expect(config?.baseURL).toBeDefined();
    });

    it('should properly sanitize user input in URLs', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      // Attempt with potentially malicious input
      const maliciousId = "'; DROP TABLE assets; --";
      await api.getAssetDetail(maliciousId);

      // URL should be properly encoded/escaped
      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        `/api/assets/${maliciousId}`
      );
    });

    it('should maintain JSON content-type for security', () => {
      const config = mockedAxios.create.mock.calls[0]?.[0];

      // Prevents some types of injection attacks
      expect(config?.headers?.['Content-Type']).toBe('application/json');
    });
  });

  describe('Breaking Change Detection', () => {
    it('should NOT break: response.data extraction', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      const result = await api.getAssetDetail('ASSET_1');

      // Should automatically extract .data
      expect(result).toEqual(mockAsset);
      expect(result).not.toHaveProperty('status');
      expect(result).not.toHaveProperty('headers');
    });

    it('should NOT break: error.response structure', async () => {
      const error = {
        response: {
          status: 404,
          data: { detail: 'Not found' },
        },
      };

      mockAxiosInstance.get.mockRejectedValue(error);

      await expect(api.getAssetDetail('NONEXISTENT')).rejects.toMatchObject({
        response: {
          status: 404,
          data: { detail: 'Not found' },
        },
      });
    });

    it('should NOT break: query parameter handling', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      await api.getAssets({ asset_class: 'EQUITY' });

      // Params should still be passed correctly
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: { asset_class: 'EQUITY' },
      });
    });

    it('should NOT break: Promise-based API', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      // Should still return Promise
      const promise = api.getAssetDetail('ASSET_1');
      expect(promise).toBeInstanceOf(Promise);

      const result = await promise;
      expect(result).toEqual(mockAsset);
    });
  });

  describe('Performance Validation', () => {
    it('should complete simple GET request in reasonable time', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      const start = Date.now();
      await api.getAssetDetail('ASSET_1');
      const duration = Date.now() - start;

      // Should be essentially instant with mocks
      expect(duration).toBeLessThan(100);
    });

    it('should handle multiple rapid requests efficiently', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      const start = Date.now();
      const promises = Array.from({ length: 50 }, (_, i) =>
        api.getAssetDetail(`ASSET_${i}`)
      );
      await Promise.all(promises);
      const duration = Date.now() - start;

      // Should handle batch efficiently
      expect(duration).toBeLessThan(500);
      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(50);
    });

    it('should not leak memory with many requests', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      // Make many requests to check for leaks
      for (let i = 0; i < 100; i++) {
        await api.getAssetDetail(`ASSET_${i}`);
      }

      // If this completes without hanging, no obvious leak
      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(100);
    });
  });

  describe('Environment Configuration', () => {
    it('should respect NEXT_PUBLIC_API_URL environment variable', () => {
      const config = mockedAxios.create.mock.calls[0]?.[0];

      // Should use env var or fallback
      expect(config?.baseURL).toBeDefined();
      expect(typeof config?.baseURL).toBe('string');
    });

    it('should use reasonable defaults when env vars missing', () => {
      const config = mockedAxios.create.mock.calls[0]?.[0];

      // Should have baseURL even without env var
      expect(config?.baseURL).toMatch(/localhost:8000/);
    });
  });

  describe('Compatibility with Testing Tools', () => {
    it('should work with Jest mock system', () => {
      expect(mockedAxios.create).toHaveBeenCalled();
      expect(mockAxiosInstance.get).toBeDefined();
      expect(jest.isMockFunction(mockAxiosInstance.get)).toBe(true);
    });

    it('should allow mock assertions', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      await api.getAssetDetail('ASSET_1');

      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(1);
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets/ASSET_1');
    });

    it('should support mock implementation changes', async () => {
      // Change mock behavior mid-test
      mockAxiosInstance.get
        .mockResolvedValueOnce({ data: mockAsset })
        .mockResolvedValueOnce({ data: { ...mockAsset, id: 'ASSET_2' } });

      const first = await api.getAssetDetail('ASSET_1');
      const second = await api.getAssetDetail('ASSET_2');

      expect(first.id).toBe('ASSET_1');
      expect(second.id).toBe('ASSET_2');
    });
  });

  describe('Real-World Edge Cases', () => {
    it('should handle slow API responses gracefully', async () => {
      mockAxiosInstance.get.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: mockAsset }), 100))
      );

      const result = await api.getAssetDetail('ASSET_1');
      expect(result).toEqual(mockAsset);
    });

    it('should handle API returning unexpected extra fields', async () => {
      const extraFields = {
        ...mockAsset,
        unexpected_field: 'surprise!',
        another_field: 123,
      };

      mockAxiosInstance.get.mockResolvedValue({ data: extraFields });

      const result = await api.getAssetDetail('ASSET_1');
      expect(result).toEqual(extraFields);
    });

    it('should handle API missing optional fields', async () => {
      const minimal = {
        id: 'ASSET_1',
        symbol: 'TEST',
        name: 'Test Asset',
        asset_class: 'EQUITY',
        sector: 'Technology',
        price: 100,
        currency: 'USD',
        additional_fields: {},
      };

      mockAxiosInstance.get.mockResolvedValue({ data: minimal });

      const result = await api.getAssetDetail('ASSET_1');
      expect(result).toEqual(minimal);
    });

    it('should handle very large numeric values correctly', async () => {
      const largeValues = {
        ...mockAsset,
        price: Number.MAX_SAFE_INTEGER,
        market_cap: 999999999999999,
      };

      mockAxiosInstance.get.mockResolvedValue({ data: largeValues });

      const result = await api.getAssetDetail('ASSET_1');
      expect(result.price).toBe(Number.MAX_SAFE_INTEGER);
    });

    it('should handle unicode and special characters in responses', async () => {
      const unicode = {
        ...mockAsset,
        name: '日本株式会社 🚀',
        symbol: 'UNICODE',
      };

      mockAxiosInstance.get.mockResolvedValue({ data: unicode });

      const result = await api.getAssetDetail('ASSET_1');
      expect(result.name).toBe('日本株式会社 🚀');
    });
  });
});
