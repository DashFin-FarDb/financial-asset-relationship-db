import axios from "axios";
import type { AxiosRequestConfig } from "axios";
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

async function getData<T>(
  path: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await apiClient.get<T>(path, config);
  return response.data;
}

export const api = {
  // Health check
  healthCheck: async () => {
    return getData("/api/health");
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
    return getData<Asset[]>("/api/assets", { params, signal });
  },

  getAssetDetail: async (
    assetId: string,
    signal?: AbortSignal,
  ): Promise<Asset> => {
    return getData<Asset>(`/api/assets/${assetId}`, { signal });
  },

  getAssetRelationships: async (
    assetId: string,
    signal?: AbortSignal,
  ): Promise<Relationship[]> => {
    return getData<Relationship[]>(
      `/api/assets/${assetId}/relationships`,
      { signal },
    );
  },

  // Relationships
  getAllRelationships: async (
    signal?: AbortSignal,
  ): Promise<Relationship[]> => {
    return getData<Relationship[]>("/api/relationships", { signal });
  },

  // Metrics
  getMetrics: async (signal?: AbortSignal): Promise<Metrics> => {
    return getData<Metrics>("/api/metrics", { signal });
  },

  // Visualization
  getVisualizationData: async (
    signal?: AbortSignal,
  ): Promise<VisualizationData> => {
    return getData<VisualizationData>("/api/visualization", { signal });
  },

  // Metadata
  getAssetClasses: async (): Promise<{ asset_classes: string[] }> => {
    return getData<{ asset_classes: string[] }>("/api/asset-classes");
  },

  getSectors: async (): Promise<{ sectors: string[] }> => {
    return getData<{ sectors: string[] }>("/api/sectors");
  },
};
