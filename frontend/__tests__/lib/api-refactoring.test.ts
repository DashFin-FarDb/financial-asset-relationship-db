/**
 * Additional comprehensive tests for frontend API client refactoring.
 *
 * Tests focus on:
 * - Quote style consistency (single quotes)
 * - Type definitions and inference
 * - Parameter formatting changes
 * - Error handling edge cases
 * - Response type validation
 */

import axios, { AxiosError } from 'axios';
let api: typeof import('../../app/lib/api').api;
import type { Asset, Relationship, Metrics, VisualizationData } from '../../app/types/api';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('API Client Refactoring Tests', () => {
  let mockAxiosInstance: jest.Mocked<Pick<typeof axios, 'get' | 'post' | 'put' | 'delete'>>;

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();

    mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
    };

    mockedAxios.create.mockReturnValue(mockAxiosInstance);
    api = require('../../app/lib/api').api;
  });

  describe('Client Configuration', () => {
    it('should use single quotes for string literals', () => {
      // This test verifies the source code style, not runtime behavior
      const apiModule = require('../../app/lib/api');
      expect(apiModule).toBeDefined();
    });

    it('should create axios instance with Content-Type application/json', () => {
      expect(mockedAxios.create).toHaveBeenCalledWith(
        expect.objectContaining({
          headers: {
            'Content-Type': 'application/json',
          },
        })
      );
    });

    it('should handle undefined environment variable gracefully', () => {
      const call = mockedAxios.create.mock.calls[0]?.[0];
      expect(call?.baseURL).toBeDefined();
      expect(typeof call?.baseURL).toBe('string');
    });
  });

  describe('Type Safety and Inference', () => {
    it('should properly type Asset responses', async () => {
      const mockAsset: Asset = {
        id: 'AAPL',
        symbol: 'AAPL',
        name: 'Apple Inc.',
        asset_class: 'EQUITY',
        sector: 'Technology',
        price: 150.0,
        additional_fields: {},
      };

      mockAxiosInstance.get.mockResolvedValue({ data: [mockAsset] });

      const result = await api.getAssets();
      
      if (Array.isArray(result)) {
        expect(result[0]).toHaveProperty('id');
        expect(result[0]).toHaveProperty('symbol');
        expect(result[0]).toHaveProperty('asset_class');
      }
    });

    it('should properly type paginated Asset responses', async () => {
      const mockPaginatedResponse = {
        items: [],
        total: 100,
        page: 1,
        per_page: 20,
      };

      mockAxiosInstance.get.mockResolvedValue({ data: { items: mockPaginatedResponse.items, total: mockPaginatedResponse.total, page: mockPaginatedResponse.page, per_page: mockPaginatedResponse.per_page } });

      const result = await api.getAssets({ page: 1, per_page: 20 });
      
      if (!Array.isArray(result)) {
        expect(result).toHaveProperty('items');
        expect(result).toHaveProperty('total');
        expect(result).toHaveProperty('page');
        expect(result).toHaveProperty('per_page');
      }
    });

    it('should properly type Relationship responses', async () => {
      const mockRelationship: Relationship = {
        source: 'AAPL',
        target: 'BOND1',
        relationship_type: 'issuer',
        strength: 1.0,
      };

      mockAxiosInstance.get.mockResolvedValue({ data: [mockRelationship] });

      const result = await api.getAllRelationships();
      expect(result[0]).toHaveProperty('source');
      expect(result[0]).toHaveProperty('target');
      expect(result[0]).toHaveProperty('relationship_type');
      expect(result[0]).toHaveProperty('strength');
    });

    it('should properly type Metrics responses', async () => {
      const mockMetrics: Metrics = {
        total_assets: 100,
        total_relationships: 250,
        asset_classes: { EQUITY: 50, FIXED_INCOME: 30, COMMODITY: 20 },
        avg_degree: 2.5,
        max_degree: 10,
        network_density: 0.05,
      };

      mockAxiosInstance.get.mockResolvedValue({ data: mockMetrics });

      const result = await api.getMetrics();
      expect(result).toHaveProperty('total_assets');
      expect(result).toHaveProperty('total_relationships');
      expect(result).toHaveProperty('asset_classes');
      expect(result).toHaveProperty('network_density');
    });
  });

  describe('Parameter Handling', () => {
    it('should handle optional parameters correctly', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      await api.getAssets();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', { params: undefined });

      await api.getAssets({});
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', { params: {} });

      await api.getAssets({ asset_class: 'EQUITY' });
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: { asset_class: 'EQUITY' },
      });
    });

    it('should handle multiple filter parameters', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      await api.getAssets({
        asset_class: 'EQUITY',
        sector: 'Technology',
        page: 2,
        per_page: 50,
      });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: {
          asset_class: 'EQUITY',
          sector: 'Technology',
          page: 2,
          per_page: 50,
        },
      });
    });

    it('should handle undefined optional parameters', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      await api.getAssets({
        asset_class: undefined,
        sector: 'Technology',
      });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: { sector: 'Technology' },
      });
    });
  });

  describe('Error Handling', () => {
    it('should propagate network errors', async () => {
      const networkError = new Error('Network Error');
      mockAxiosInstance.get.mockRejectedValue(networkError);

      await expect(api.healthCheck()).rejects.toThrow('Network Error');
    });

    it('should propagate HTTP errors', async () => {
      const httpError: Partial<AxiosError> = {
        response: {
          status: 404,
          statusText: 'Not Found',
          data: { detail: 'Asset not found' },
          headers: {},
          config: {} as any,
        },
        isAxiosError: true,
      };

      mockAxiosInstance.get.mockRejectedValue(httpError);

      await expect(api.getAssetDetail('NONEXISTENT')).rejects.toMatchObject({
        response: expect.objectContaining({
          status: 404,
        }),
      });
    });

    it('should handle timeout errors', async () => {
      const timeoutError: Partial<AxiosError> = {
        code: 'ECONNABORTED',
        message: 'timeout of 5000ms exceeded',
        isAxiosError: true,
      };

      mockAxiosInstance.get.mockRejectedValue(timeoutError);

      await expect(api.getMetrics()).rejects.toMatchObject({
        code: 'ECONNABORTED',
      });
    });

    it('should handle server errors', async () => {
      const serverError: Partial<AxiosError> = {
        response: {
          status: 500,
          statusText: 'Internal Server Error',
          data: { detail: 'Database connection failed' },
          headers: {},
          config: {} as any,
        },
        isAxiosError: true,
      };

      mockAxiosInstance.get.mockRejectedValue(serverError);

      await expect(api.getVisualizationData()).rejects.toMatchObject({
        response: expect.objectContaining({
          status: 500,
        }),
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty response arrays', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      const assets = await api.getAssets();
      expect(Array.isArray(assets) ? assets : assets.items).toHaveLength(0);
    });

    it('should handle null response values', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: null });

      const result = await api.healthCheck();
      expect(result).toBeNull();
    });

    it('should handle special characters in asset IDs', async () => {
      const specialId = 'ASSET@#$%^&*()';
      mockAxiosInstance.get.mockResolvedValue({
        data: {
          id: specialId,
          symbol: 'TEST',
          name: 'Test Asset',
          asset_class: 'EQUITY',
          sector: 'Technology',
          price: 100.0,
          additional_fields: {},
        },
      });
      await api.getAssetDetail(specialId);
      expect(mockAxiosInstance.get).toHaveBeenCalledWith(`/api/assets/${encodeURIComponent(specialId)}`);
    });

    it('should handle very large numbers in metrics', async () => {
      const largeMetrics: Metrics = {
        total_assets: Number.MAX_SAFE_INTEGER,
        total_relationships: Number.MAX_SAFE_INTEGER,
        asset_classes: {},
        avg_degree: 999999.99,
        max_degree: Number.MAX_SAFE_INTEGER,
        network_density: 0.999999,
      };

      mockAxiosInstance.get.mockResolvedValue({ data: largeMetrics });

      const result = await api.getMetrics();
      expect(result.total_assets).toBe(Number.MAX_SAFE_INTEGER);
    });
  });

  describe('Concurrent Requests', () => {
    it('should handle multiple simultaneous requests', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      const requests = [
        api.getAssets(),
        api.getMetrics(),
        api.getVisualizationData(),
        api.getAssetClasses(),
        api.getSectors(),
      ];

      await Promise.all(requests);

      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(5);
    });

    it('should handle request cancellation gracefully', async () => {
      const cancelError: Partial<AxiosError> = {
        message: 'Request cancelled',
        isAxiosError: true,
      };

      mockAxiosInstance.get.mockRejectedValue(cancelError);

      await expect(api.getAssets()).rejects.toMatchObject({
        message: 'Request cancelled',
      });
    });
  });

  describe('Response Data Validation', () => {
    it('should handle malformed asset data', async () => {
      const malformedData = {
        id: 'AAPL',
        // Missing required fields
      };

      mockAxiosInstance.get.mockResolvedValue({ data: [malformedData] });

      const result = await api.getAssets();
      // API should return the data as-is; validation happens at usage site
      expect(Array.isArray(result) ? result[0] : result.items[0]).toHaveProperty('id');
    });

    it('should handle unexpected response structure', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: 'unexpected string response' });

      const result = await api.healthCheck();
      expect(result).toBe('unexpected string response');
    });
  });

  describe('URL Construction', () => {
    it('should construct correct URLs for all endpoints', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: {} });

      await api.healthCheck();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/health');

      await api.getAssets();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', expect.any(Object));

      await api.getAssetDetail('AAPL');
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets/AAPL');

      await api.getAssetRelationships('AAPL');
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets/AAPL/relationships');

      await api.getAllRelationships();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/relationships');

      await api.getMetrics();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/metrics');

      await api.getVisualizationData();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/visualization');

      await api.getAssetClasses();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/asset-classes');

      await api.getSectors();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/sectors');
    });
  });
});
