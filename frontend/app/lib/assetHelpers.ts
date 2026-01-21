import { api } from "./api";
import type { Asset } from "../types/api";

interface PaginatedAssetsResponse {
  items: Asset[];
  total: number;
  page: number;
  per_page: number;
}

const isPaginatedResponse = (
  value: unknown,
): value is PaginatedAssetsResponse => {
  return (
    typeof value === "object" &&
    value !== null &&
    "items" in value &&
    "total" in value &&
    "page" in value &&
    "per_page" in value &&
    Array.isArray((value as PaginatedAssetsResponse).items) &&
    typeof (value as PaginatedAssetsResponse).total === "number" &&
    typeof (value as PaginatedAssetsResponse).page === "number" &&
    typeof (value as PaginatedAssetsResponse).per_page === "number"
  );
};

export const parsePositiveInteger = (
  value: string | null,
  fallback: number,
) => {
  const parsed = Number.parseInt(value || "", 10);
  return Number.isNaN(parsed) || parsed <= 0 ? fallback : parsed;
};

export const buildQuerySummary = (
  page: number,
  pageSize: number,
  filter: { asset_class: string; sector: string },
) => {
  const summaryParts = [`page ${page}`, `${pageSize} per page`];

  if (filter.asset_class) {
    summaryParts.push(`asset class \"${filter.asset_class}\"`);
  }

  if (filter.sector) {
    summaryParts.push(`sector \"${filter.sector}\"`);
  }

  return summaryParts.join(", ");
};

export const loadMetadata = async (
  setAssetClasses: (next: string[]) => void,
  setSectors: (next: string[]) => void,
) => {
  try {
    const [classesData, sectorsData] = await Promise.all([
      api.getAssetClasses(),
      api.getSectors(),
    ]);

    setAssetClasses(classesData.asset_classes);
    setSectors(sectorsData.sectors);
  } catch (error) {
    console.error("Error loading metadata:", error);
  }
};

export const loadAssets = async (
  page: number,
  pageSize: number,
  filter: { asset_class: string; sector: string },
  setAssets: (next: Asset[]) => void,
  setTotal: (next: number | null) => void,
  setError: (next: string | null) => void,
  querySummary?: string,
) => {
  setError(null);

  try {
    const params: {
      asset_class?: string;
      sector?: string;
      page: number;
      per_page: number;
    } = {
      page,
      per_page: pageSize,
    };

    if (filter.asset_class) params.asset_class = filter.asset_class;
    if (filter.sector) params.sector = filter.sector;

    const data = await api.getAssets(params);

    if (isPaginatedResponse(data)) {
      setAssets(data.items);
      setTotal(data.total);
    } else {
      setAssets(data);
      setTotal(Array.isArray(data) ? data.length : null);
    }
  } catch (error) {
    console.error("Error loading assets:", error);
    setAssets([]);
    setTotal(null);
    setError(
      `Unable to load assets${querySummary ? ` for ${querySummary}` : ""}. Please try again.`,
    );
  }
};
