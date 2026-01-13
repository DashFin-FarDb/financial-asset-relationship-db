"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { api } from "../lib/api";
import type { Asset } from "../types/api";

interface PaginatedAssetsResponse {
  items: Asset[];
  total: number;
  page: number;
  per_page: number;
}

const DEFAULT_PAGE_SIZE = 20;

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

const parsePositiveInteger = (value: string | null, fallback: number) => {
  const parsed = Number.parseInt(value || "", 10);
  return Number.isNaN(parsed) || parsed <= 0 ? fallback : parsed;
};

const buildQuerySummary = (
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
 * Renders an asset list UI with filter controls and data fetching.
 *
 * Loads asset classes and sectors on mount and reloads the asset list whenever the selected
 * asset class or sector changes. Displays loading and empty states and, when available,
 * a table of assets showing symbol, name, class, sector, price, and market capitalization.
 *
 * @returns The rendered JSX element for the asset list component.
 */
export default function AssetList() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState({ asset_class: "", sector: "" });
  const [assetClasses, setAssetClasses] = useState<string[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState<number | null>(null);

  const querySummary = useMemo(
    () => buildQuerySummary(page, pageSize, filter),
    [filter, page, pageSize],
  );

  const loadMetadata = async () => {
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

  const loadAssets = useCallback(async () => {
    setLoading(true);
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
        setTotal(typeof data.total === "number" ? data.total : null);
      } else {
        setAssets(data);
        setTotal(Array.isArray(data) ? data.length : null);
      }
    } catch (error) {
      console.error("Error loading assets:", error);
      setAssets([]);
      setTotal(null);
      setError(`Unable to load assets for ${querySummary}. Please try again.`);
    } finally {
      setLoading(false);
    }
  }, [filter, page, pageSize]);

  const syncStateFromParams = useCallback(() => {
    const nextAssetClass = searchParams.get("asset_class") ?? "";
    const nextSector = searchParams.get("sector") ?? "";
    const nextPage = parsePositiveInteger(searchParams.get("page"), 1);
    const nextPageSize = parsePositiveInteger(
      searchParams.get("per_page"),
      DEFAULT_PAGE_SIZE,
    );

    setFilter((prev) => {
      if (prev.asset_class === nextAssetClass && prev.sector === nextSector) {
        return prev;
      }
      return { asset_class: nextAssetClass, sector: nextSector };
    });
    setPage((prev) => (prev === nextPage ? prev : nextPage));
    setPageSize((prev) => (prev === nextPageSize ? prev : nextPageSize));
  }, [searchParams]);

  useEffect(() => {
    syncStateFromParams();
  }, [syncStateFromParams]);

  const updateQueryParams = useCallback(
    (updates: Record<string, string | null>) => {
      if (!pathname) return;
      const params = new URLSearchParams(searchParams.toString());

      Object.entries(updates).forEach(([key, value]) => {
        if (value === null || value === "") {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      });

      const queryString = params.toString();
      const currentQueryString = searchParams.toString();
      if (queryString !== currentQueryString) {
        router.replace(`${pathname}${queryString ? `?${queryString}` : ""}`, {
          scroll: false,
        });
      }
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    loadMetadata();
  }, []);

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  const totalPages = useMemo(() => {
    if (!total || total <= 0) return null;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [pageSize, total]);

  const canGoNext = !loading && totalPages !== null && page < totalPages;

  const canGoPrev = !loading && page > 1;

  const handleFilterChange =
    (field: "asset_class" | "sector") =>
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      const { value } = event.target;
      setFilter((prev) => ({ ...prev, [field]: value }));
      setPage(1);
      updateQueryParams({ [field]: value || null, page: "1" });
    };

  const handlePageSizeChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    const nextSize = parsePositiveInteger(
      event.target.value,
      DEFAULT_PAGE_SIZE,
    );
    setPageSize(nextSize);
    setPage(1);
    updateQueryParams({ per_page: String(nextSize), page: "1" });
  };

  const goToPage = (requestedPage: number) => {
    const lowerBounded = Math.max(1, requestedPage);
    const bounded =
      totalPages !== null ? Math.min(lowerBounded, totalPages) : lowerBounded;

    if (bounded === page) {
      return;
    }

    setPage(bounded);
    updateQueryParams({ page: String(bounded) });
  };

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold mb-4">Filters</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="asset-class-filter"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Asset Class
            </label>
            <select
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              id="asset-class-filter"
              value={filter.asset_class}
              onChange={handleFilterChange("asset_class")}
            >
              <option value="">All Classes</option>
              {assetClasses.map((ac) => (
                <option key={ac} value={ac}>
                  {ac}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              htmlFor="sector-filter"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Sector
            </label>
            <select
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              id="sector-filter"
              value={filter.sector}
              onChange={handleFilterChange("sector")}
            >
              <option value="">All Sectors</option>
              {sectors.map((sector) => (
                <option key={sector} value={sector}>
                  {sector}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Asset List */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        {(loading || error) && (
          <div
            className={`px-6 py-3 text-sm ${
              error
                ? "bg-red-50 text-red-700 border-b border-red-100"
                : "bg-blue-50 text-blue-700 border-b border-blue-100"
            }`}
            role={error ? "alert" : "status"}
          >
            {error || `Loading results for ${querySummary}...`}
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Symbol
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Class
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Sector
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Price
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Market Cap
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-4 text-center text-gray-500"
                  >
                    Loading...
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-4 text-center text-red-600"
                  >
                    {error}
                  </td>
                </tr>
              ) : assets.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-4 text-center text-gray-500"
                  >
                    No assets found
                  </td>
                </tr>
              ) : (
                assets.map((asset) => (
                  <tr key={asset.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {asset.symbol}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {asset.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {asset.asset_class}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {asset.sector}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {asset.currency} {asset.price.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {asset.market_cap
                        ? `$${(asset.market_cap / 1e9).toFixed(2)}B`
                        : "N/A"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-gray-50 px-6 py-4 border-t border-gray-100">
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => goToPage(page - 1)}
              disabled={!canGoPrev}
              className={`px-3 py-1 rounded-md border ${
                canGoPrev
                  ? "border-gray-300 text-gray-700 hover:bg-gray-100"
                  : "border-gray-200 text-gray-400 cursor-not-allowed"
              }`}
            >
              Previous
            </button>
            <span className="text-sm text-gray-600">
              Page {page}
              {totalPages ? ` of ${totalPages}` : ""}
            </span>
            <button
              type="button"
              onClick={() => goToPage(page + 1)}
              disabled={!canGoNext}
              className={`px-3 py-1 rounded-md border ${
                canGoNext
                  ? "border-gray-300 text-gray-700 hover:bg-gray-100"
                  : "border-gray-200 text-gray-400 cursor-not-allowed"
              }`}
            >
              Next
            </button>
          </div>
          <div className="flex items-center space-x-2">
            <label htmlFor="asset-page-size" className="text-sm text-gray-600">
              Rows per page
            </label>
            <select
              id="asset-page-size"
              value={pageSize}
              onChange={handlePageSizeChange}
              className="border border-gray-300 rounded-md px-2 py-1 text-sm"
            >
              {[10, 20, 50, 100].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
