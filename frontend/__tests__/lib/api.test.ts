/**
 * Comprehensive unit tests for the API client library (app/lib/api.ts).
 *
 * Tests cover:
 * - All API methods (health check, assets, relationships, metrics, visualization)
 * - Request parameter handling (including pagination)
 * - AbortSignal / cancellation support
 * - Response type validation
 * - Error handling (network, HTTP 400/401/403/404/422/500)
 * - Concurrent requests
 * - Axios configuration (baseURL, timeout)
 */

// Mock axios with a factory that creates a stable instance internally.
// The factory runs when "axios" is first required (which happens when api.ts
// is imported below). We capture the instance reference in beforeAll via
// (axios.create as jest.Mock).mock.results[0].value.
jest.mock("axios", () => {
  const instance = {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  };
  return {
    __esModule: true,
    default: {
      create: jest.fn(() => instance),
      isAxiosError: jest.fn(
        (e: unknown) => (e as Record<string, unknown>)?.isAxiosError === true,
      ),
    },
  };
});

import axios from "axios";
import type { Metrics, VisualizationData } from "../../app/types/api";
import { api } from "../../app/lib/api";
import {
  mockAssets,
  mockAsset,
  mockRelationships,
  mockAllRelationships,
  mockMetrics,
  mockVizData,
  mockAssetClasses,
  mockSectors,
} from "../test-utils";

// Shared references captured once at suite startup (before clearAllMocks runs).
let mockAxiosInstance: {
  get: jest.Mock;
  post: jest.Mock;
  put: jest.Mock;
  delete: jest.Mock;
};
// Arguments passed to axios.create when api.ts was imported.
let axiosCreateConfig: Record<string, unknown>;

beforeAll(() => {
  const mockedCreate = axios.create as jest.Mock;
  axiosCreateConfig = mockedCreate.mock.calls[0]?.[0] as Record<
    string,
    unknown
  >;
  mockAxiosInstance = mockedCreate.mock.results[0].value;
});

beforeEach(() => {
  jest.clearAllMocks();
  // Re-prime axios.create so it returns the same stable instance if anything
  // calls axios.create again (and so the mock is reset cleanly each test).
  (axios.create as jest.Mock).mockReturnValue(mockAxiosInstance);
});

describe("API Client", () => {
  // ---------------------------------------------------------------------------
  // Client Configuration
  // ---------------------------------------------------------------------------
  describe("Client Configuration", () => {
    it("should create axios instance with exact baseURL", () => {
      expect(axiosCreateConfig).toMatchObject({
        baseURL: "http://localhost:8000",
      });
    });

    it("should create axios instance with timeout: 10_000", () => {
      expect(axiosCreateConfig).toMatchObject({ timeout: 10_000 });
    });

    it("should create axios instance with correct Content-Type header", () => {
      expect(axiosCreateConfig).toMatchObject({
        headers: { "Content-Type": "application/json" },
      });
    });
  });

  // ---------------------------------------------------------------------------
  // healthCheck
  // ---------------------------------------------------------------------------
  describe("healthCheck", () => {
    it("should call health check endpoint", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: { status: "healthy" } });

      const result = await api.healthCheck();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/health");
      expect(result).toEqual({ status: "healthy" });
    });

    it("should handle health check errors", async () => {
      mockAxiosInstance.get.mockRejectedValue(new Error("Network error"));

      await expect(api.healthCheck()).rejects.toThrow("Network error");
    });
  });

  // ---------------------------------------------------------------------------
  // getAssets
  // ---------------------------------------------------------------------------
  describe("getAssets", () => {
    it("should fetch all assets without filters", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      const result = await api.getAssets();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/assets", {
        params: undefined,
        signal: undefined,
      });
      expect(result).toEqual(mockAssets);
      expect(result).toHaveLength(2);
    });

    it("should fetch assets with asset_class filter", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      await api.getAssets({ asset_class: "EQUITY" });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/assets", {
        params: { asset_class: "EQUITY" },
        signal: undefined,
      });
    });

    it("should fetch assets with sector filter", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      await api.getAssets({ sector: "Technology" });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/assets", {
        params: { sector: "Technology" },
        signal: undefined,
      });
    });

    it("should fetch assets with both filters", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      await api.getAssets({ asset_class: "EQUITY", sector: "Technology" });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/assets", {
        params: { asset_class: "EQUITY", sector: "Technology" },
        signal: undefined,
      });
    });

    it("should forward page param", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      await api.getAssets({ page: 2 });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/assets", {
        params: { page: 2 },
        signal: undefined,
      });
    });

    it("should forward per_page param", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      await api.getAssets({ per_page: 50 });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/assets", {
        params: { per_page: 50 },
        signal: undefined,
      });
    });

    it("should forward combined pagination + filter params", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });

      await api.getAssets({
        asset_class: "EQUITY",
        sector: "Technology",
        page: 3,
        per_page: 25,
      });

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/assets", {
        params: {
          asset_class: "EQUITY",
          sector: "Technology",
          page: 3,
          per_page: 25,
        },
        signal: undefined,
      });
    });

    it("should handle empty asset list", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      const result = await api.getAssets();

      expect(result).toEqual([]);
      expect(result).toHaveLength(0);
    });

    it("should handle API errors when fetching assets", async () => {
      mockAxiosInstance.get.mockRejectedValue(new Error("API Error"));

      await expect(api.getAssets()).rejects.toThrow("API Error");
    });

    it("should forward AbortSignal to axios config", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssets });
      const controller = new AbortController();

      await api.getAssets(undefined, controller.signal);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/assets", {
        params: undefined,
        signal: controller.signal,
      });
    });

    it("should propagate AbortError when signal is aborted", async () => {
      const abortError = new DOMException("Aborted", "AbortError");
      mockAxiosInstance.get.mockRejectedValue(abortError);
      const controller = new AbortController();
      controller.abort();

      await expect(api.getAssets(undefined, controller.signal)).rejects.toThrow(
        "Aborted",
      );
    });
  });

  // ---------------------------------------------------------------------------
  // getAssetDetail
  // ---------------------------------------------------------------------------
  describe("getAssetDetail", () => {
    it("should fetch asset details by ID", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      const result = await api.getAssetDetail("ASSET_1");

      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        "/api/assets/ASSET_1",
        {
          signal: undefined,
        },
      );
      expect(result).toEqual(mockAsset);
      expect(result.additional_fields).toBeDefined();
    });

    it("should handle non-existent asset ID (404)", async () => {
      mockAxiosInstance.get.mockRejectedValue({
        response: { status: 404, data: { detail: "Asset not found" } },
      });

      await expect(api.getAssetDetail("NONEXISTENT")).rejects.toMatchObject({
        response: { status: 404 },
      });
    });

    it("should handle special characters in asset ID", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });

      await api.getAssetDetail("ASSET_1-2.3");

      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        "/api/assets/ASSET_1-2.3",
        { signal: undefined },
      );
    });

    it("should forward AbortSignal to axios config", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAsset });
      const controller = new AbortController();

      await api.getAssetDetail("ASSET_1", controller.signal);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        "/api/assets/ASSET_1",
        {
          signal: controller.signal,
        },
      );
    });
  });

  // ---------------------------------------------------------------------------
  // getAssetRelationships
  // ---------------------------------------------------------------------------
  describe("getAssetRelationships", () => {
    it("should fetch relationships for an asset", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockRelationships });

      const result = await api.getAssetRelationships("ASSET_1");

      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        "/api/assets/ASSET_1/relationships",
        { signal: undefined },
      );
      expect(result).toEqual(mockRelationships);
      expect(result).toHaveLength(2);
    });

    it("should handle asset with no relationships", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      const result = await api.getAssetRelationships("ASSET_ISOLATED");

      expect(result).toEqual([]);
      expect(result).toHaveLength(0);
    });

    it("should validate relationship structure", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockRelationships });

      const result = await api.getAssetRelationships("ASSET_1");

      result.forEach((rel) => {
        expect(rel).toHaveProperty("source_id");
        expect(rel).toHaveProperty("target_id");
        expect(rel).toHaveProperty("relationship_type");
        expect(rel).toHaveProperty("strength");
        expect(typeof rel.strength).toBe("number");
      });
    });

    it("should forward AbortSignal to axios config", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockRelationships });
      const controller = new AbortController();

      await api.getAssetRelationships("ASSET_1", controller.signal);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        "/api/assets/ASSET_1/relationships",
        { signal: controller.signal },
      );
    });
  });

  // ---------------------------------------------------------------------------
  // getAllRelationships
  // ---------------------------------------------------------------------------
  describe("getAllRelationships", () => {
    it("should fetch all relationships", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAllRelationships });

      const result = await api.getAllRelationships();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/relationships", {
        signal: undefined,
      });
      expect(result).toEqual(mockAllRelationships);
      expect(result).toHaveLength(2);
    });

    it("should handle empty relationships", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: [] });

      const result = await api.getAllRelationships();

      expect(result).toEqual([]);
    });

    it("should forward AbortSignal to axios config", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAllRelationships });
      const controller = new AbortController();

      await api.getAllRelationships(controller.signal);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/relationships", {
        signal: controller.signal,
      });
    });
  });

  // ---------------------------------------------------------------------------
  // getMetrics
  // ---------------------------------------------------------------------------
  describe("getMetrics", () => {
    it("should fetch network metrics", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockMetrics });

      const result = await api.getMetrics();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/metrics", {
        signal: undefined,
      });
      expect(result).toEqual(mockMetrics);
    });

    it("should validate metrics structure", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockMetrics });

      const result = await api.getMetrics();

      expect(result).toHaveProperty("total_assets");
      expect(result).toHaveProperty("total_relationships");
      expect(result).toHaveProperty("asset_classes");
      expect(result).toHaveProperty("avg_degree");
      expect(result).toHaveProperty("max_degree");
      expect(result).toHaveProperty("network_density");
      expect(result).toHaveProperty("relationship_density");
      expect(typeof result.total_assets).toBe("number");
      expect(typeof result.asset_classes).toBe("object");
    });

    it("should handle metrics with zero values", async () => {
      const emptyMetrics: Metrics = {
        total_assets: 0,
        total_relationships: 0,
        asset_classes: {},
        avg_degree: 0,
        max_degree: 0,
        network_density: 0,
        relationship_density: 0,
      };
      mockAxiosInstance.get.mockResolvedValue({ data: emptyMetrics });

      const result = await api.getMetrics();

      expect(result.total_assets).toBe(0);
      expect(result.network_density).toBe(0);
      expect(result.relationship_density).toBe(0);
    });

    it("should forward AbortSignal to axios config", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockMetrics });
      const controller = new AbortController();

      await api.getMetrics(controller.signal);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/metrics", {
        signal: controller.signal,
      });
    });
  });

  // ---------------------------------------------------------------------------
  // getVisualizationData
  // ---------------------------------------------------------------------------
  describe("getVisualizationData", () => {
    it("should fetch visualization data", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockVizData });

      const result = await api.getVisualizationData();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/visualization", {
        signal: undefined,
      });
      expect(result).toEqual(mockVizData);
    });

    it("should validate visualization node structure", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockVizData });

      const result = await api.getVisualizationData();

      expect(result.nodes).toHaveLength(2);
      result.nodes.forEach((node) => {
        expect(node).toHaveProperty("id");
        expect(node).toHaveProperty("name");
        expect(node).toHaveProperty("symbol");
        expect(node).toHaveProperty("asset_class");
        expect(node).toHaveProperty("x");
        expect(node).toHaveProperty("y");
        expect(node).toHaveProperty("z");
        expect(node).toHaveProperty("color");
        expect(node).toHaveProperty("size");
        expect(typeof node.x).toBe("number");
        expect(typeof node.y).toBe("number");
        expect(typeof node.z).toBe("number");
      });
    });

    it("should validate visualization edge structure", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockVizData });

      const result = await api.getVisualizationData();

      expect(result.edges).toHaveLength(1);
      result.edges.forEach((edge) => {
        expect(edge).toHaveProperty("source");
        expect(edge).toHaveProperty("target");
        expect(edge).toHaveProperty("relationship_type");
        expect(edge).toHaveProperty("strength");
        expect(typeof edge.strength).toBe("number");
      });
    });

    it("should handle empty visualization data", async () => {
      const emptyVizData: VisualizationData = { nodes: [], edges: [] };
      mockAxiosInstance.get.mockResolvedValue({ data: emptyVizData });

      const result = await api.getVisualizationData();

      expect(result.nodes).toHaveLength(0);
      expect(result.edges).toHaveLength(0);
    });

    it("should forward AbortSignal to axios config", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockVizData });
      const controller = new AbortController();

      await api.getVisualizationData(controller.signal);

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/visualization", {
        signal: controller.signal,
      });
    });
  });

  // ---------------------------------------------------------------------------
  // getAssetClasses
  // ---------------------------------------------------------------------------
  describe("getAssetClasses", () => {
    it("should fetch asset classes", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssetClasses });

      const result = await api.getAssetClasses();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/asset-classes");
      expect(result).toEqual(mockAssetClasses);
      expect(result.asset_classes).toHaveLength(4);
    });

    it("should validate asset classes are strings", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockAssetClasses });

      const result = await api.getAssetClasses();

      result.asset_classes.forEach((ac) => {
        expect(typeof ac).toBe("string");
      });
    });

    it("should handle empty asset classes", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: { asset_classes: [] } });

      const result = await api.getAssetClasses();

      expect(result.asset_classes).toHaveLength(0);
    });
  });

  // ---------------------------------------------------------------------------
  // getSectors
  // ---------------------------------------------------------------------------
  describe("getSectors", () => {
    it("should fetch sectors", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockSectors });

      const result = await api.getSectors();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith("/api/sectors");
      expect(result).toEqual(mockSectors);
      expect(result.sectors).toHaveLength(3);
    });

    it("should validate sectors are sorted", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: mockSectors });

      const result = await api.getSectors();

      const sortedSectors = [...result.sectors].sort();
      expect(result.sectors).toEqual(sortedSectors);
    });

    it("should handle empty sectors", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: { sectors: [] } });

      const result = await api.getSectors();

      expect(result.sectors).toHaveLength(0);
    });
  });

  // ---------------------------------------------------------------------------
  // Error Handling — HTTP status codes
  // ---------------------------------------------------------------------------
  describe("Error Handling", () => {
    it("should propagate network errors", async () => {
      mockAxiosInstance.get.mockRejectedValue(new Error("Network Error"));

      await expect(api.getAssets()).rejects.toThrow("Network Error");
    });

    it("should propagate 400 Bad Request", async () => {
      mockAxiosInstance.get.mockRejectedValue({
        response: { status: 400, data: { detail: "Bad Request" } },
      });

      await expect(api.getAssets()).rejects.toMatchObject({
        response: { status: 400 },
      });
    });

    it("should propagate 401 Unauthorized", async () => {
      mockAxiosInstance.get.mockRejectedValue({
        response: { status: 401, data: { detail: "Unauthorized" } },
      });

      await expect(api.getMetrics()).rejects.toMatchObject({
        response: { status: 401 },
      });
    });

    it("should propagate 403 Forbidden", async () => {
      mockAxiosInstance.get.mockRejectedValue({
        response: { status: 403, data: { detail: "Forbidden" } },
      });

      await expect(api.getMetrics()).rejects.toMatchObject({
        response: { status: 403 },
      });
    });

    it("should propagate 404 Not Found", async () => {
      mockAxiosInstance.get.mockRejectedValue({
        response: { status: 404, data: { detail: "Not Found" } },
      });

      await expect(api.getAssetDetail("MISSING")).rejects.toMatchObject({
        response: { status: 404 },
      });
    });

    it("should propagate 422 Unprocessable Entity", async () => {
      mockAxiosInstance.get.mockRejectedValue({
        response: { status: 422, data: { detail: "Unprocessable Entity" } },
      });

      await expect(api.getAssets({ page: -1 })).rejects.toMatchObject({
        response: { status: 422 },
      });
    });

    it("should propagate 500 Internal Server Error", async () => {
      mockAxiosInstance.get.mockRejectedValue({
        response: { status: 500, data: { detail: "Internal Server Error" } },
      });

      await expect(api.getMetrics()).rejects.toMatchObject({
        response: { status: 500 },
      });
    });

    it("should propagate timeout errors", async () => {
      mockAxiosInstance.get.mockRejectedValue(
        new Error("timeout of 10000ms exceeded"),
      );

      await expect(api.getVisualizationData()).rejects.toThrow("timeout");
    });

    it("should handle malformed response data", async () => {
      mockAxiosInstance.get.mockResolvedValue({ data: null });

      const result = await api.healthCheck();

      expect(result).toBeNull();
    });
  });

  // ---------------------------------------------------------------------------
  // Concurrent requests
  // ---------------------------------------------------------------------------
  describe("Concurrent requests", () => {
    it("should resolve concurrent getAssets and getMetrics independently", async () => {
      mockAxiosInstance.get
        .mockResolvedValueOnce({ data: mockAssets })
        .mockResolvedValueOnce({ data: mockMetrics });

      const [assets, metrics] = await Promise.all([
        api.getAssets(),
        api.getMetrics(),
      ]);

      expect(assets).toEqual(mockAssets);
      expect(metrics).toEqual(mockMetrics);
      expect(mockAxiosInstance.get).toHaveBeenCalledTimes(2);
    });

    it("should handle mixed success and failure in concurrent requests", async () => {
      mockAxiosInstance.get
        .mockResolvedValueOnce({ data: mockAssets })
        .mockRejectedValueOnce({
          response: { status: 500, data: { detail: "Server Error" } },
        });

      const results = await Promise.allSettled([
        api.getAssets(),
        api.getMetrics(),
      ]);

      expect(results[0].status).toBe("fulfilled");
      expect(results[1].status).toBe("rejected");
    });
  });
});
