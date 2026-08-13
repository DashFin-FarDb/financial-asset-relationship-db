import axios from "axios";
import type { AxiosRequestConfig } from "axios";
import type {
  Asset,
  AssetPageResponse,
  AssertionAsOfParams,
  AssertionExplanation,
  AssertionHistory,
  Relationship,
  Metrics,
  VisualizationData,
  PublishedEdgeExplanationResponse,
} from "../types/api";

const envUrl = process.env.NEXT_PUBLIC_API_URL;
const API_URL = envUrl ?? "http://localhost:8000";

const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 10_000,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * Retrieve data from the API at the given relative path.
 *
 * @param path - Relative path appended to the API client's baseURL
 * @param config - Optional Axios request configuration for query parameters, headers, or an abort signal
 * @returns The response data typed as `T`
 */
async function getData<T>(
  path: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = config
    ? await apiClient.get<T>(path, config)
    : await apiClient.get<T>(path);
  return response.data;
}

/**
 * Fetch a governed assertion read model (explanation or history) at the given
 * bitemporal path, forwarding identical `known_at`/`effective_at` bounds so
 * that callers can request both endpoints against the same as-of snapshot.
 */
function getAssertionResource<T>(
  assertionId: string,
  resourcePath: "" | "/history",
  params?: AssertionAsOfParams,
  signal?: AbortSignal,
): Promise<T> {
  return getData<T>(
    `/api/assertions/${encodeURIComponent(assertionId)}${resourcePath}`,
    { params, signal },
  );
}

/**
 * Build a single-purpose fetcher bound to one governed-assertion resource
 * path (the explanation itself, or its history). Generating both
 * `getAssertion`/`getAssertionHistory` from this one factory -- rather than
 * hand-writing two structurally identical wrapper functions -- keeps there
 * from being two near-duplicate function bodies to maintain in parallel.
 */
function makeAssertionFetcher<T>(resourcePath: "" | "/history") {
  return (
    assertionId: string,
    params?: AssertionAsOfParams,
    signal?: AbortSignal,
  ): Promise<T> =>
    getAssertionResource<T>(assertionId, resourcePath, params, signal);
}

export const api = {
  // Health check
  healthCheck: () => {
    return getData("/api/health");
  },

  // Assets
  getAssets: (
    params?: {
      asset_class?: string;
      sector?: string;
      page?: number;
      per_page?: number;
    },
    signal?: AbortSignal,
  ): Promise<AssetPageResponse> => {
    return getData<AssetPageResponse>("/api/assets", { params, signal });
  },

  getAssetDetail: (assetId: string, signal?: AbortSignal): Promise<Asset> => {
    return getData<Asset>(`/api/assets/${encodeURIComponent(assetId)}`, {
      signal,
    });
  },

  getAssetRelationships: (
    assetId: string,
    signal?: AbortSignal,
  ): Promise<Relationship[]> => {
    return getData<Relationship[]>(
      `/api/assets/${encodeURIComponent(assetId)}/relationships`,
      {
        signal,
      },
    );
  },

  // Relationships
  getAllRelationships: (signal?: AbortSignal): Promise<Relationship[]> => {
    return getData<Relationship[]>("/api/relationships", { signal });
  },

  // Metrics
  getMetrics: (signal?: AbortSignal): Promise<Metrics> => {
    return getData<Metrics>("/api/graph/metrics", { signal });
  },

  // Visualization
  getVisualizationData: (signal?: AbortSignal): Promise<VisualizationData> => {
    return getData<VisualizationData>("/api/visualization", { signal });
  },

  // Metadata
  getAssetClasses: (): Promise<{ asset_classes: string[] }> => {
    return getData<{ asset_classes: string[] }>("/api/asset-classes");
  },

  getSectors: (): Promise<{ sectors: string[] }> => {
    return getData<{ sectors: string[] }>("/api/sectors");
  },

  // Governed assertion explanation (GRAC v1)
  //
  // Callers should capture a single `known_at`/`effective_at` pair and pass
  // it to both calls below, so the explanation and history are resolved
  // against the same as-of snapshot rather than two independent server
  // "now" defaults.
  getAssertion: makeAssertionFetcher<AssertionExplanation>(""),

  getAssertionHistory: makeAssertionFetcher<AssertionHistory>("/history"),

  getPublishedEdgeExplanation: (
    publicationId: string,
    projectionEdgeId: string,
    signal?: AbortSignal,
  ): Promise<PublishedEdgeExplanationResponse> => {
    return getData<PublishedEdgeExplanationResponse>(
      `/api/publications/${encodeURIComponent(publicationId)}/edges/${encodeURIComponent(projectionEdgeId)}/explanation`,
      { signal },
    );
  },
};
