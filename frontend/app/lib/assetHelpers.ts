import { api } from "./api";
import type { Asset } from "../types/api";

interface PaginatedAssetsResponse {
  items: Asset[];
  total: number;
  page: number;
  per_page: number;
}

/**
 * Type guard to check if a value is a PaginatedAssetsResponse.
 *
 * @param value - The value to check.
 * @returns True if the value conforms to PaginatedAssetsResponse, otherwise false.
 */
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

/**
 * Parses a string into a positive integer or returns a fallback if parsing fails or result is non-positive.
 *
 * @param value - The string value to parse.
 * @param fallback - The fallback number to return if parsing fails or is non-positive.
 * @returns The parsed positive integer or the fallback.
 */
export const parsePositiveInteger = (
  value: string | null,
  fallback: number,
) => {
  const parsed = Number.parseInt(value || "", 10);
  return Number.isNaN(parsed) || parsed <= 0 ? fallback : parsed;
};

/**
 * Builds a summary string for query parameters.
 *
 * @param page - The current page number.
 * @param pageSize - The number of items per page.
 * @param filter - The filter object containing asset_class and sector.
 * @returns A summary string of the query parameters.
 */
export const buildQuerySummary = (
  page: number,
  pageSize: number,
  filter: { asset_class: string; sector: string },
) => {
  const summaryParts = [`page ${page}`, `${pageSize} per page`];

  if (filter.asset_class) {
    summaryParts.push(`asset class "${filter.asset_class}"`);
  }

  if (filter.sector) {
    summaryParts.push(`sector "${filter.sector}"`);
  }

  return summaryParts.join(", ");
};

/**
 * Loads asset classes and sectors metadata and sets state with provided setters.
 *
 * @param setAssetClasses - Callback to set the list of asset classes.
 * @param setSectors - Callback to set the list of sectors.
 * @returns A promise that resolves when metadata is loaded.
 */
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

/**
 * Loads assets based on pagination and filter, sets assets, total, error and optional query summary.
 *
 * @param page - The current page number.
 * @param pageSize - The number of items per page.
 * @param filter - The filter object containing asset_class and sector.
 * @param setAssets - Callback to set the list of loaded assets.
 * @param setTotal - Callback to set the total number of assets.
 * @param setError - Callback to set error messages.
 * @param querySummary - Optional summary of the query.
 * @returns A promise that resolves when assets are loaded.
 */
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
