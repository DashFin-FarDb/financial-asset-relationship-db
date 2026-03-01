import axios from "axios";
import type {
  Asset,
  Relationship,
  Metrics,
  VisualizationData,
} from "../types/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 10_000,
  headers: {
    "Content-Type": "application/json",
  },
});

export const api = {
  // Health check
  healthCheck: async () => {
    const response = await apiClient.get("/api/health");
    return response.data;
  },

  // Assets
  getAssets: async (
    params?: {
      asset_class?: string;
      sector?: string;
      page?: number;
      per_page?: number;
    },
    signal?: AbortSignal,
  ): Promise<Asset[]> => {
    const response = await apiClient.get("/api/assets", { params, signal });
    return response.data;
  },

  getAssetDetail: async (
    assetId: string,
    signal?: AbortSignal,
  ): Promise<Asset> => {
    const response = await apiClient.get(`/api/assets/${assetId}`, { signal });
    return response.data;
  },

  getAssetRelationships: async (
    assetId: string,
    signal?: AbortSignal,
  ): Promise<Relationship[]> => {
    const response = await apiClient.get(
      `/api/assets/${assetId}/relationships`,
      { signal },
    );
    return response.data;
  },

  // Relationships
  getAllRelationships: async (
    signal?: AbortSignal,
  ): Promise<Relationship[]> => {
    const response = await apiClient.get("/api/relationships", { signal });
    return response.data;
  },

  // Metrics
  getMetrics: async (signal?: AbortSignal): Promise<Metrics> => {
    const response = await apiClient.get("/api/metrics", { signal });
    return response.data;
  },

  // Visualization
  getVisualizationData: async (
    signal?: AbortSignal,
  ): Promise<VisualizationData> => {
    const response = await apiClient.get("/api/visualization", { signal });
    return response.data;
  },

  // Metadata
  getAssetClasses: async (): Promise<{ asset_classes: string[] }> => {
    const response = await apiClient.get("/api/asset-classes");
    return response.data;
  },

  getSectors: async (): Promise<{ sectors: string[] }> => {
    const response = await apiClient.get("/api/sectors");
    return response.data;
  },
};
