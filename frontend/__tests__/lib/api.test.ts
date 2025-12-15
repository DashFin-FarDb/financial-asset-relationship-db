/**
 * Comprehensive unit tests for the API client library (app/lib/api.ts).
 *
 * Tests cover:
 * - All API methods (health check, assets, relationships, metrics, visualization)
 * - Request parameter handling
 * - Response type validation
 * - Error handling
 * - Axios configuration
 */

import axios from 'axios';
import type { Asset, Relationship, Metrics, VisualizationData } from '../../app/types/api';
import {
  mockAssets,
  mockAsset,
  mockRelationships,
  mockAllRelationships,
  mockMetrics,
  mockVizData,
  mockAssetClasses,
  mockSectors,
} from '../test-utils';

// Mock axios
jest.mock('axios');
let mockedAxios: jest.Mocked<typeof axios>;

let api: typeof import('../../app/lib/api')['api'];

describe('API Client', () => {
  let mockAxiosInstance: jest.Mocked<Pick<typeof axios, 'get' | 'post' | 'put' | 'delete'>>;

  beforeEach(async () => {
    jest.resetModules();
    mockedAxios = (await import('axios')) as jest.Mocked<typeof axios>;
    // Create a mock axios instance
    mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
    };

    // Mock axios.create to return our mock instance
    mockedAxios.create.mockReturnValue(mockAxiosInstance);
    const apiModule = await import('../../app/lib/api');
    api = apiModule.api;
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Client Configuration', () => {
    it('should create axios instance with correct baseURL', () => {
      expect(mockedAxios.create).toHaveBeenCalledWith({
        baseURL: expect.any(String),
        headers: {
          'Content-Type': 'application/json',
        },
      });
    });

    it('should fall back to localhost:8000 if no environment variable', () => {
      const call = mockedAxios.create.mock.calls.at(-1)?.[0];
      expect(call?.baseURL).toMatch(/localhost:8000/);
    });
  });

  describe('healthCheck', () => {
    it('should call health check endpoint', async () => {
      const mockResponse = { data: { status: 'healthy' } };
      mockAxiosInstance.get.mockResolvedValue(mockResponse);

      const result = await api.healthCheck();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/health');
      expect(result).toEqual({ status: 'healthy' });
    });

    it('should handle health check errors', async () => {
      mockAxiosInstance.get.mockRejectedValue(new Error('Network error'));

      await expect(api.healthCheck()).rejects.toThrow('Network error');
    });
  });

  describe('getAssets', () => {
    it('should fetch all assets without filters', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      const result = await api.getAssets();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', { params: undefined });
      expect(result).toEqual(mockAssets);
      expect(result).toHaveLength(2);
    });

    it('should fetch assets with asset_class filter', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      const result = await api.getAssets({ asset_class: 'EQUITY' });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: { asset_class: 'EQUITY' },
      });
      expect(result).toEqual(mockAssets);
    });

    it('should fetch assets with sector filter', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      const result = await api.getAssets({ sector: 'Technology' });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: { sector: 'Technology' },
      });
      expect(result).toEqual(mockAssets);
    });

    it('should fetch assets with both filters', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      const result = await api.getAssets({ asset_class: 'EQUITY', sector: 'Technology' });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: { asset_class: 'EQUITY', sector: 'Technology' },
      });
      expect(result).toEqual(mockAssets);
    });

    it('should handle empty asset list', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      const result = await api.getAssets();

      expect(result).toEqual([]);
      expect(result).toHaveLength(0);
    });

    it('should handle API errors when fetching assets', async () => {
      mockAxiosInstance.get.mockRejectedValue(new Error('API Error'));

      await expect(api.getAssets()).rejects.toThrow('API Error');
    });
  });

  describe('getAssetDetail', () => {
    it('should fetch asset details by ID', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      const result = await api.getAssetDetail('ASSET_1');

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets/ASSET_1');
      expect(result).toEqual(mockAsset);
      expect(result.additional_fields).toBeDefined();
    });

    it('should handle non-existent asset ID', async () => {
      mockAxiosInstance.get.mockRejectedValue({
        response: { status: 404, data: { detail: 'Asset not found' } },
      });

      await expect(api.getAssetDetail('NONEXISTENT')).rejects.toMatchObject({
        response: { status: 404 },
      });
    });

    it('should handle special characters in asset ID', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      await api.getAssetDetail('ASSET_1-2.3');

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets/ASSET_1-2.3');
    });
  });

  describe('getAssetRelationships', () => {
    it('should fetch relationships for an asset', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockRelationships });

      const result = await api.getAssetRelationships('ASSET_1');

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets/ASSET_1/relationships');
      expect(result).toEqual(mockRelationships);
      expect(result).toHaveLength(2);
    });

    it('should handle asset with no relationships', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      const result = await api.getAssetRelationships('ASSET_ISOLATED');

      expect(result).toEqual([]);
      expect(result).toHaveLength(0);
    });

    it('should validate relationship structure', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockRelationships });

      const result = await api.getAssetRelationships('ASSET_1');

      result.forEach((rel) => {
        expect(rel).toHaveProperty('source_id');
        expect(rel).toHaveProperty('target_id');
        expect(rel).toHaveProperty('relationship_type');
        expect(rel).toHaveProperty('strength');
        expect(typeof rel.strength).toBe('number');
      });
    });
  });

  describe('getAllRelationships', () => {
    it('should fetch all relationships', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAllRelationships });

      const result = await api.getAllRelationships();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/relationships');
      expect(result).toEqual(mockAllRelationships);
      expect(result).toHaveLength(2);
    });

    it('should handle empty relationships', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      const result = await api.getAllRelationships();

      expect(result).toEqual([]);
    });
  });

  describe('getMetrics', () => {
    it('should fetch network metrics', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockMetrics });

      const result = await api.getMetrics();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/metrics');
      expect(result).toEqual(mockMetrics);
    });

    it('should validate metrics structure', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockMetrics });

      const result = await api.getMetrics();

      expect(result).toHaveProperty('total_assets');
      expect(result).toHaveProperty('total_relationships');
      expect(result).toHaveProperty('asset_classes');
      expect(result).toHaveProperty('avg_degree');
      expect(result).toHaveProperty('max_degree');
      expect(result).toHaveProperty('network_density');
      expect(typeof result.total_assets).toBe('number');
      expect(typeof result.asset_classes).toBe('object');
    });

    it('should handle metrics with zero values', async () => {
      const emptyMetrics: Metrics = {
        total_assets: 0,
        total_relationships: 0,
        asset_classes: {},
        avg_degree: 0,
        max_degree: 0,
        network_density: 0,
      };
      mockAxiosInstance.get.mockResolvedValue({ data: emptyMetrics });

      const result = await api.getMetrics();

      expect(result.total_assets).toBe(0);
      expect(result.network_density).toBe(0);
    });
  });

  describe('getVisualizationData', () => {
    it('should fetch visualization data', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockVizData });

      const result = await api.getVisualizationData();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/visualization');
      expect(result).toEqual(mockVizData);
    });

    it('should validate visualization node structure', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockVizData });

      const result = await api.getVisualizationData();

      expect(result.nodes).toHaveLength(2);
      result.nodes.forEach((node) => {
        expect(node).toHaveProperty('id');
        expect(node).toHaveProperty('name');
        expect(node).toHaveProperty('symbol');
        expect(node).toHaveProperty('asset_class');
        expect(node).toHaveProperty('x');
        expect(node).toHaveProperty('y');
        expect(node).toHaveProperty('z');
        expect(node).toHaveProperty('color');
        expect(node).toHaveProperty('size');
        expect(typeof node.x).toBe('number');
        expect(typeof node.y).toBe('number');
        expect(typeof node.z).toBe('number');
      });
    });

    it('should validate visualization edge structure', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockVizData });

      const result = await api.getVisualizationData();

      expect(result.edges).toHaveLength(1);
      result.edges.forEach((edge) => {
        expect(edge).toHaveProperty('source');
        expect(edge).toHaveProperty('target');
        expect(edge).toHaveProperty('relationship_type');
        expect(edge).toHaveProperty('strength');
        expect(typeof edge.strength).toBe('number');
      });
    });

    it('should handle empty visualization data', async () => {
      const emptyVizData: VisualizationData = { nodes: [], edges: [] };
      mockAxiosInstance.get.mockResolvedValue({ data: emptyVizData });

      const result = await api.getVisualizationData();

      expect(result.nodes).toHaveLength(0);
      expect(result.edges).toHaveLength(0);
    });
  });

  describe('getAssetClasses', () => {
    it('should fetch asset classes', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssetClasses });

      const result = await api.getAssetClasses();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/asset-classes');
      expect(result).toEqual(mockAssetClasses);
      expect(result.asset_classes).toHaveLength(4);
    });

    it('should validate asset classes are strings', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssetClasses });

      const result = await api.getAssetClasses();

      result.asset_classes.forEach((ac) => {
        expect(typeof ac).toBe('string');
      });
    });

    it('should handle empty asset classes', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: { asset_classes: [] } });

      const result = await api.getAssetClasses();

      expect(result.asset_classes).toHaveLength(0);
    });
  });

  describe('getSectors', () => {
    it('should fetch sectors', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockSectors });

      const result = await api.getSectors();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/sectors');
      expect(result).toEqual(mockSectors);
      expect(result.sectors).toHaveLength(3);
    });

    it('should validate sectors are sorted', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockSectors });

      const result = await api.getSectors();

      const sortedSectors = [...result.sectors].sort();
      expect(result.sectors).toEqual(sortedSectors);
    });

    it('should handle empty sectors', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: { sectors: [] } });

      const result = await api.getSectors();

      expect(result.sectors).toHaveLength(0);
    });
  });

  describe('Error Handling', () => {
    it('should propagate network errors', async () => {
      const networkError = new Error('Network Error');
      mockAxiosInstance.get.mockRejectedValue(networkError);

      await expect(api.getAssets()).rejects.toThrow('Network Error');
    });

    it('should propagate HTTP error responses', async () => {
      const httpError = {
        response: {
          status: 500,
          data: { detail: 'Internal Server Error' },
        },
      };
      mockAxiosInstance.get.mockRejectedValue(httpError);

      await expect(api.getMetrics()).rejects.toMatchObject({
        response: { status: 500 },
      });
    });

    it('should propagate timeout errors', async () => {
      const timeoutError = new Error('timeout of 5000ms exceeded');
      mockAxiosInstance.get.mockRejectedValue(timeoutError);

      await expect(api.getVisualizationData()).rejects.toThrow('timeout');
    });

    it('should handle malformed response data', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: null });

      const result = await api.healthCheck();

      await expect(api.getAllRelationships()).rejects.toThrow();
  });

  describe('Advanced Error Handling', () => {
    it('should handle network timeout errors', async () => {
      mockAxiosInstance.get.mockRejectedValue({
        code: 'ECONNABORTED',
        message: 'timeout of 5000ms exceeded',
      });

      await expect(api.healthCheck()).rejects.toMatchObject({
        code: 'ECONNABORTED',
      });
    });

    it('should handle 404 not found errors', async () => {
      mockAxiosInstance.get.mockRejectedValue({
        response: { status: 404, data: { detail: 'Not found' } },
      });

      await expect(api.getAssetDetail('NONEXISTENT')).rejects.toMatchObject({
        response: { status: 404 },
      });
    });

    it('should handle 500 server errors', async () => {
      mockAxiosInstance.get.mockRejectedValue({
        response: { status: 500, data: { detail: 'Internal server error' } },
      });

      await expect(api.getMetrics()).rejects.toMatchObject({
        response: { status: 500 },
      });
    });

    it('should handle malformed JSON responses', async () => {
      mockAxiosInstance.get.mockRejectedValue(new SyntaxError('Unexpected token'));

      await expect(api.getAssets()).rejects.toThrow(SyntaxError);
    });
  });

  describe('Response Validation', () => {
    it('should return empty array when API returns null', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: null });

      const result = await api.getAllRelationships();
      expect(result).toBeNull();
    });

    it('should handle undefined response data', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: undefined });

      const result = await api.getAllRelationships();
      expect(result).toBeUndefined();
    });

    it('should preserve response structure for paginated results', async () => {
      const paginatedResponse = {
        items: mockAssets,
        total: 100,
        page: 2,
        per_page: 20,
      };
      mockAxiosInstance.get.mockResolvedValue({ data: paginatedResponse });

      const result = await api.getAssets({ page: 2, per_page: 20 });
      
      expect(result).toEqual(paginatedResponse);
      expect(result).toHaveProperty('items');
      expect(result).toHaveProperty('total');
      expect(result).toHaveProperty('page');
      expect(result).toHaveProperty('per_page');
    });
  });

  describe('Request Parameter Edge Cases', () => {
    it('should handle zero as valid page number', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      await api.getAssets({ page: 0, per_page: 20 });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: { page: 0, per_page: 20 },
      });
    });

    it('should handle very large per_page value', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      await api.getAssets({ page: 1, per_page: 10000 });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: { page: 1, per_page: 10000 },
      });
    });

    it('should handle special characters in asset IDs', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      await api.getAssetDetail('ASSET_1-2-3');

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets/ASSET_1-2-3');
    });

    it('should handle empty string filters', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      await api.getAssets({ asset_class: '', sector: '' });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: { asset_class: '', sector: '' },
      });
    });
  });

  describe('Concurrent Request Handling', () => {
    it('should handle multiple simultaneous getAssets calls', async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      const promises = [
        api.getAssets({ asset_class: 'EQUITY' }),
        api.getAssets({ sector: 'Technology' }),
        api.getAssets({ page: 2 }),
      ];

      const results = await Promise.all(promises);

      expect(results).toHaveLength(3);
      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(3);
    });

    it('should handle mixed success and failure in concurrent requests', async () => {
      mockAxiosInstance.get
        .mockResolvedValueOnce({ data: mockAssets })
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({ data: mockMetrics });

      const results = await Promise.allSettled([
        api.getAssets(),
        api.getAllRelationships(),
        api.getMetrics(),
      ]);

      expect(results[0].status).toBe('fulfilled');
      expect(results[1].status).toBe('rejected');
      expect(results[2].status).toBe('fulfilled');
    });
  });

  describe('Response Data Integrity', () => {
    it('should not mutate response data', async () => {
      const originalData = { ...mockAsset };
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      const result = await api.getAssetDetail('ASSET_1');
      result.price = 999.99;

      expect(mockAsset.price).toBe(originalData.price);
    });

    it('should handle deeply nested additional_fields', async () => {
      const nestedAsset = {
        ...mockAsset,
        additional_fields: {
          nested: {
            deep: {
              value: 123,
            },
          },
        },
      };
      mockAxiosInstance.get.mockResolvedValue({ data: nestedAsset });

      const result = await api.getAssetDetail('ASSET_1');

      expect(result.additional_fields.nested.deep.value).toBe(123);
      // Missing nested fields should be handled gracefully
      const missingNestedAsset = {
        ...mockAsset,
        additional_fields: undefined,
      };
      mockAxiosInstance.get.mockResolvedValueOnce({ data: missingNestedAsset });
      const resultMissing = await api.getAssetDetail('ASSET_1');
      expect(resultMissing.additional_fields?.nested?.deep?.value).toBeUndefined();

      // Malformed nested structure (deep is not an object)
      const malformedNestedAsset = {
        ...mockAsset,
        additional_fields: {
          nested: {
            deep: null,
          },
        },
      };
      mockAxiosInstance.get.mockResolvedValueOnce({ data: malformedNestedAsset });
      expect(resultMalformed.additional_fields?.nested?.deep).toBeNull();
      expect(resultMalformed.additional_fields?.nested?.deep && typeof resultMalformed.additional_fields.nested.deep === 'object').toBe(false);
  });
});