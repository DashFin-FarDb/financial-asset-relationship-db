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
  getAssets: async (params?: {
    asset_class?: string;
    sector?: string;
    page?: number;
    per_page?: number;
  }): Promise<
    Asset[] | { items: Asset[]; total: number; page: number; per_page: number }
  > => {
    const response = await apiClient.get("/api/assets", { params });
    return response.data;
  },

  getAssetDetail: async (assetId: string): Promise<Asset> => {
    const response = await apiClient.get(`/api/assets/${assetId}`);
    return response.data;
  },

  getAssetRelationships: async (assetId: string): Promise<Relationship[]> => {
    const response = await apiClient.get(
      `/api/assets/${assetId}/relationships`,
    );
    return response.data;
  },

  // Relationships
  getAllRelationships: async (): Promise<Relationship[]> => {
    const response = await apiClient.get("/api/relationships");
    return response.data;
  },

  // Metrics
  getMetrics: async (): Promise<Metrics> => {
    const response = await apiClient.get("/api/metrics");
    return response.data;
  },

  // Visualization
  getVisualizationData: async (): Promise<VisualizationData> => {
    const response = await apiClient.get("/api/visualization");
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
