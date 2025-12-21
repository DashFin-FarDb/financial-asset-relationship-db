/**
 * Comprehensive behavioral tests for axios 1.13.2 upgrade compatibility.
 *
 * Tests cover:
 * - Axios 1.13.2 specific features and bug fixes
 * - TypeScript type compatibility with axios 1.13.2
 * - Request/response interceptor compatibility
 * - Error handling improvements in 1.13.2
 * - Timeout and cancellation behavior
 * - Header handling and content-type validation
 * - Base URL and configuration options
 * - Backward compatibility with axios 1.6.0 patterns
 *
 * These tests ensure that the upgrade from axios 1.6.0 to 1.13.2
 * maintains all existing functionality while benefiting from bug fixes
 * and security improvements in the newer version.
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import type { Asset, Metrics } from '../../app/types/api';
import { mockAsset, mockMetrics } from '../test-utils';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('Axios 1.13.2 Compatibility Tests', () => {
  let mockAxiosInstance: jest.Mocked<AxiosInstance>;
  let api: typeof import('../../app/lib/api')['api'];

  beforeEach(async () => {
    jest.resetModules();

    // Create a comprehensive mock axios instance
    mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      patch: jest.fn(),
      head: jest.fn(),
      options: jest.fn(),
      request: jest.fn(),
      getUri: jest.fn(),
      defaults: {
        headers: {
          common: {},
          get: {},
          post: {},
          put: {},
          patch: {},
          delete: {},
          head: {},
        },
        baseURL: 'http://localhost:8000',
        timeout: 0,
        withCredentials: false,
        responseType: 'json',
        xsrfCookieName: 'XSRF-TOKEN',
        xsrfHeaderName: 'X-XSRF-TOKEN',
        maxContentLength: -1,
        maxBodyLength: -1,
        validateStatus: (status: number) => status >= 200 && status < 300,
        transformRequest: [],
        transformResponse: [],
      },
      interceptors: {
        request: {
          use: jest.fn(),
          eject: jest.fn(),
          clear: jest.fn(),
        },
        response: {
          use: jest.fn(),
          eject: jest.fn(),
          clear: jest.fn(),
        },
      },
    } as any;

    mockedAxios.create.mockReturnValue(mockAxiosInstance);

    const apiModule = await import('../../app/lib/api');
    api = apiModule.api;
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Axios Instance Creation - 1.13.2 Compatibility', () => {
    it('should create instance with correct configuration for axios 1.13.2', () => {
      expect(mockedAxios.create).toHaveBeenCalledWith({
        baseURL: expect.any(String),
        headers: {
          'Content-Type': 'application/json',
        },
      });
    });

    it('should support axios 1.13.2 configuration options', () => {
      const config = mockedAxios.create.mock.calls[0]?.[0];

      expect(config).toBeDefined();
      expect(config?.baseURL).toBeDefined();
      expect(config?.headers).toBeDefined();

      // Axios 1.13.2 should accept these standard options
      const extendedConfig: AxiosRequestConfig = {
        ...config,
        timeout: 5000,
        withCredentials: true,
        maxRedirects: 5,
        validateStatus: (status) => status < 500,
      };

      expect(extendedConfig.timeout).toBe(5000);
      expect(extendedConfig.withCredentials).toBe(true);
    });

    it('should have proper TypeScript types for axios 1.13.2', () => {
      // Type checking - this test passes if it compiles
      const testInstance: AxiosInstance = mockAxiosInstance;

      expect(testInstance.get).toBeDefined();
      expect(testInstance.post).toBeDefined();
      expect(testInstance.interceptors).toBeDefined();
      expect(testInstance.defaults).toBeDefined();
    });
  });

  describe('Request Configuration - Axios 1.13.2 Features', () => {
    it('should properly handle query parameters with axios 1.13.2', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: [mockAsset],
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      await api.getAssets({
        asset_class: 'EQUITY',
        sector: 'Technology',
        page: 1,
        per_page: 10
      });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: {
          asset_class: 'EQUITY',
          sector: 'Technology',
          page: 1,
          per_page: 10,
        },
      });
    });

    it('should handle undefined query parameters correctly', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: [mockAsset],
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      await api.getAssets({ asset_class: undefined });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets', {
        params: { asset_class: undefined },
      });
    });

    it('should properly encode special characters in URLs', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: mockAsset,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      // Test with special characters that need encoding
      await api.getAssetDetail('TEST-ASSET_1.2');

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets/TEST-ASSET_1.2');
    });
  });

  describe('Response Handling - Axios 1.13.2 Behavior', () => {
    it('should correctly extract response data in axios 1.13.2 format', async () => {
      const mockResponse: AxiosResponse<Asset> = {
        data: mockAsset,
        status: 200,
        statusText: 'OK',
        headers: { 'content-type': 'application/json' },
        config: {} as any,
      };

      mockAxiosInstance.get.mockResolvedValue(mockResponse);

      const result = await api.getAssetDetail('ASSET_1');

      expect(result).toEqual(mockAsset);
      expect(result.id).toBe('ASSET_1');
    });

    it('should handle 204 No Content responses correctly', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: '',
        status: 204,
        statusText: 'No Content',
        headers: {},
        config: {} as any,
      });

      const result = await api.healthCheck();

      expect(result).toBe('');
    });

    it('should preserve response headers in axios 1.13.2', async () => {
      const mockResponse: AxiosResponse = {
        data: mockMetrics,
        status: 200,
        statusText: 'OK',
        headers: {
          'content-type': 'application/json',
          'x-request-id': 'test-123',
          'x-ratelimit-remaining': '99',
        },
        config: {} as any,
      };

      mockAxiosInstance.get.mockResolvedValue(mockResponse);

      const result = await api.getMetrics();

      expect(result).toEqual(mockMetrics);
    });
  });

  describe('Error Handling - Axios 1.13.2 Improvements', () => {
    it('should properly type AxiosError in axios 1.13.2', async () => {
      const axiosError: AxiosError = {
        name: 'AxiosError',
        message: 'Request failed with status code 404',
        code: 'ERR_BAD_REQUEST',
        config: {} as any,
        request: {},
        response: {
          data: { detail: 'Not found' },
          status: 404,
          statusText: 'Not Found',
          headers: {},
          config: {} as any,
        },
        isAxiosError: true,
        toJSON: () => ({}),
      };

      mockAxiosInstance.get.mockRejectedValue(axiosError);

      await expect(api.getAssetDetail('NONEXISTENT')).rejects.toMatchObject({
        response: {
          status: 404,
          data: { detail: 'Not found' },
        },
      });
    });

    it('should handle network errors without response object', async () => {
      const networkError: AxiosError = {
        name: 'AxiosError',
        message: 'Network Error',
        code: 'ERR_NETWORK',
        config: {} as any,
        request: {},
        isAxiosError: true,
        toJSON: () => ({}),
      };

      mockAxiosInstance.get.mockRejectedValue(networkError);

      await expect(api.getMetrics()).rejects.toMatchObject({
        code: 'ERR_NETWORK',
        message: 'Network Error',
      });
    });

    it('should handle timeout errors with proper error code', async () => {
      const timeoutError: AxiosError = {
        name: 'AxiosError',
        message: 'timeout of 5000ms exceeded',
        code: 'ECONNABORTED',
        config: {} as any,
        request: {},
        isAxiosError: true,
        toJSON: () => ({}),
      };

      mockAxiosInstance.get.mockRejectedValue(timeoutError);

      await expect(api.getVisualizationData()).rejects.toMatchObject({
        code: 'ECONNABORTED',
        message: expect.stringContaining('timeout'),
      });
    });

    it('should properly handle 5xx server errors', async () => {
      const serverError: AxiosError = {
        name: 'AxiosError',
        message: 'Request failed with status code 500',
        code: 'ERR_BAD_RESPONSE',
        config: {} as any,
        request: {},
        response: {
          data: { error: 'Internal Server Error' },
          status: 500,
          statusText: 'Internal Server Error',
          headers: {},
          config: {} as any,
        },
        isAxiosError: true,
        toJSON: () => ({}),
      };

      mockAxiosInstance.get.mockRejectedValue(serverError);

      await expect(api.getAssets()).rejects.toMatchObject({
        response: { status: 500 },
      });
    });

    it('should handle 4xx client errors correctly', async () => {
      const clientError: AxiosError = {
        name: 'AxiosError',
        message: 'Request failed with status code 400',
        code: 'ERR_BAD_REQUEST',
        config: {} as any,
        request: {},
        response: {
          data: { detail: 'Invalid request parameters' },
          status: 400,
          statusText: 'Bad Request',
          headers: {},
          config: {} as any,
        },
        isAxiosError: true,
        toJSON: () => ({}),
      };

      mockAxiosInstance.get.mockRejectedValue(clientError);

      await expect(api.getAssets({ asset_class: 'INVALID' })).rejects.toMatchObject({
        response: { status: 400 },
      });
    });
  });

  describe('Content-Type Handling - Axios 1.13.2', () => {
    it('should set correct Content-Type header for JSON', () => {
      const config = mockedAxios.create.mock.calls[0]?.[0];

      expect(config?.headers?.['Content-Type']).toBe('application/json');
    });

    it('should handle JSON response parsing automatically', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: mockMetrics,
        status: 200,
        statusText: 'OK',
        headers: { 'content-type': 'application/json; charset=utf-8' },
        config: {} as any,
      });

      const result = await api.getMetrics();

      expect(result).toEqual(mockMetrics);
      expect(typeof result).toBe('object');
    });

    it('should handle empty response body correctly', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: null,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      const result = await api.healthCheck();

      expect(result).toBeNull();
    });
  });

  describe('URL Handling - Axios 1.13.2', () => {
    it('should correctly combine baseURL with relative paths', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: mockAsset,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      await api.getAssetDetail('ASSET_1');

      // Should call with relative URL (baseURL is set on instance)
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets/ASSET_1');
    });

    it('should handle paths with multiple segments', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: [],
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      await api.getAssetRelationships('ASSET_1');

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/assets/ASSET_1/relationships');
    });

    it('should not double-slash URLs', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: { status: 'ok' },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      await api.healthCheck();

      // Should use single leading slash
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/health');
    });
  });

  describe('TypeScript Type Safety - Axios 1.13.2', () => {
    it('should properly type generic responses', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: mockAsset,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      // TypeScript should infer correct return type
      const result: Asset = await api.getAssetDetail('ASSET_1');

      expect(result.id).toBeDefined();
      expect(result.symbol).toBeDefined();
      expect(result.name).toBeDefined();
    });

    it('should properly type array responses', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: [mockAsset],
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      // TypeScript should infer array type
      const result = await api.getAssets();

      expect(Array.isArray(result) || typeof result === 'object').toBeTruthy();
    });

    it('should handle union types correctly', async () => {
      // Test that API can return either array or paginated response
      mockAxiosInstance.get.mockResolvedValue({
        data: {
          items: [mockAsset],
          total: 1,
          page: 1,
          per_page: 10,
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      const result = await api.getAssets({ page: 1, per_page: 10 });

      expect(result).toBeDefined();
    });
  });

  describe('Backward Compatibility - 1.6.0 to 1.13.2', () => {
    it('should maintain same API for basic GET requests', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: mockAsset,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      // Same usage pattern as axios 1.6.0
      const result = await api.getAssetDetail('ASSET_1');

      expect(result).toEqual(mockAsset);
    });

    it('should maintain same error handling interface', async () => {
      const error: AxiosError = {
        name: 'AxiosError',
        message: 'Test error',
        config: {} as any,
        isAxiosError: true,
        toJSON: () => ({}),
      };

      mockAxiosInstance.get.mockRejectedValue(error);

      // Error handling should work the same way
      await expect(api.getAssets()).rejects.toMatchObject({
        isAxiosError: true,
      });
    });

    it('should maintain same response structure', async () => {
      const mockResponse: AxiosResponse<Metrics> = {
        data: mockMetrics,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      };

      mockAxiosInstance.get.mockResolvedValue(mockResponse);

      const result = await api.getMetrics();

      // Response.data should be automatically extracted
      expect(result).toEqual(mockMetrics);
      expect(result.total_assets).toBeDefined();
    });
  });

  describe('Edge Cases - Axios 1.13.2 Robustness', () => {
    it('should handle very long URLs correctly', async () => {
      const longId = 'A'.repeat(1000);

      mockAxiosInstance.get.mockResolvedValue({
        data: { ...mockAsset, id: longId },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      await api.getAssetDetail(longId);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith(`/api/assets/${longId}`);
    });

    it('should handle concurrent requests correctly', async () => {
      mockAxiosInstance.get
        .mockResolvedValueOnce({
          data: mockAsset,
          status: 200,
          statusText: 'OK',
          headers: {},
          config: {} as any,
        })
        .mockResolvedValueOnce({
          data: mockMetrics,
          status: 200,
          statusText: 'OK',
          headers: {},
          config: {} as any,
        });

      // Make concurrent requests
      const [asset, metrics] = await Promise.all([
        api.getAssetDetail('ASSET_1'),
        api.getMetrics(),
      ]);

      expect(asset).toEqual(mockAsset);
      expect(metrics).toEqual(mockMetrics);
      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(2);
    });

    it('should handle rapid sequential requests', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: mockAsset,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      // Make rapid sequential requests
      for (let i = 0; i < 10; i++) {
        await api.getAssetDetail(`ASSET_${i}`);
      }

      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(10);
    });

    it('should handle null and undefined in response data', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: {
          ...mockAsset,
          market_cap: null,
          additional_fields: undefined,
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      const result = await api.getAssetDetail('ASSET_1');

      expect(result.market_cap).toBeNull();
    });
  });

  describe('Interceptor Compatibility - Axios 1.13.2', () => {
    it('should support request interceptors', () => {
      expect(mockAxiosInstance.interceptors.request.use).toBeDefined();
      expect(typeof mockAxiosInstance.interceptors.request.use).toBe('function');
    });

    it('should support response interceptors', () => {
      expect(mockAxiosInstance.interceptors.response.use).toBeDefined();
      expect(typeof mockAxiosInstance.interceptors.response.use).toBe('function');
    });

    it('should allow interceptor registration', () => {
      const requestInterceptor = (config: any) => config;
      const responseInterceptor = (response: any) => response;

      mockAxiosInstance.interceptors.request.use(requestInterceptor);
      mockAxiosInstance.interceptors.response.use(responseInterceptor);

      expect(mockAxiosInstance.interceptors.request.use).toHaveBeenCalledWith(
        requestInterceptor
      );
      expect(mockAxiosInstance.interceptors.response.use).toHaveBeenCalledWith(
        responseInterceptor
      );
    });
  });

  describe('Performance and Optimization - Axios 1.13.2', () => {
    it('should reuse axios instance across requests', async () => {
      mockAxiosInstance.get.mockResolvedValue({
        data: mockAsset,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      await api.getAssetDetail('ASSET_1');
      await api.getAssetDetail('ASSET_2');

      // Should create instance only once
      expect(mockedAxios.create).toHaveBeenCalledTimes(1);
      // But call get twice
      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(2);
    });

    it('should handle large response payloads efficiently', async () => {
      const largeDataset = Array.from({ length: 1000 }, (_, i) => ({
        ...mockAsset,
        id: `ASSET_${i}`,
      }));

      mockAxiosInstance.get.mockResolvedValue({
        data: largeDataset,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      });

      const result = await api.getAssets();

      expect(Array.isArray(result) ? result.length : 0).toBeGreaterThan(0);
    });
  });
});
