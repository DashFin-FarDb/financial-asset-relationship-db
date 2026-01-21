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
const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

/** Type guard to check if response is paginated */
const isPaginatedResponse = (
  value: unknown,
): value is PaginatedAssetsResponse =>
  typeof value === "object" &&
  value !== null &&
  "items" in value &&
  "total" in value &&
  "page" in value &&
  "per_page" in value &&
  Array.isArray((value as PaginatedAssetsResponse).items);

/** Parse positive integer or fallback */
const parsePositiveInteger = (value: string | null, fallback: number) => {
  const parsed = Number.parseInt(value || "", 10);
  return Number.isNaN(parsed) || parsed <= 0 ? fallback : parsed;
};

/** Build query summary string */
const buildQuerySummary = (
  page: number,
  pageSize: number,
  filter: { asset_class: string; sector: string },
) => {
  const parts = [`page ${page}`, `${pageSize} per page`];
  if (filter.asset_class) parts.push(`asset class "${filter.asset_class}"`);
  if (filter.sector) parts.push(`sector "${filter.sector}"`);
  return parts.join(", ");
};

/** Filter select component */
const FilterSelect = ({
  label,
  id,
  options,
  value,
  onChange,
  placeholder = "All",
}: {
  label: string;
  id: string;
  options: string[];
  value: string;
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  placeholder?: string;
}) => (
  <div>
    <label
      htmlFor={id}
      className="block text-sm font-medium text-gray-700 mb-2"
    >
      {label}
    </label>
    <select
      id={id}
      value={value}
      onChange={onChange}
      className="w-full border border-gray-300 rounded-md px-3 py-2"
    >
      <option value="">{placeholder}</option>
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  </div>
);

/** Main asset list component */
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

  /** Load metadata (asset classes + sectors) */
  const loadMetadata = useCallback(async () => {
    try {
      const [classesData, sectorsData] = await Promise.all([
        api.getAssetClasses(),
        api.getSectors(),
      ]);
      setAssetClasses(classesData.asset_classes);
      setSectors(sectorsData.sectors);
    } catch (err) {
      console.error("Error loading metadata:", err);
    }
  }, []);

  /** Load assets based on filters + pagination */
  const loadAssets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: {
        asset_class?: string;
        sector?: string;
        page: number;
        per_page: number;
      } = { page, per_page: pageSize };
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
    } catch (err) {
      console.error("Error loading assets:", err);
      setAssets([]);
      setTotal(null);
      setError(`Unable to load assets for ${querySummary}. Please try again.`);
    } finally {
      setLoading(false);
    }
  }, [filter, page, pageSize, querySummary]);

  /** Sync state from URL params */
  const syncStateFromParams = useCallback(() => {
    const nextAssetClass = searchParams.get("asset_class") ?? "";
    const nextSector = searchParams.get("sector") ?? "";
    const nextPage = parsePositiveInteger(searchParams.get("page"), 1);
    const nextPageSize = parsePositiveInteger(
      searchParams.get("per_page"),
      DEFAULT_PAGE_SIZE,
    );

    setFilter((prev) =>
      prev.asset_class === nextAssetClass && prev.sector === nextSector
        ? prev
        : { asset_class: nextAssetClass, sector: nextSector },
    );
    setPage((prev) => (prev === nextPage ? prev : nextPage));
    setPageSize((prev) => (prev === nextPageSize ? prev : nextPageSize));
  }, [searchParams]);

  /** Update URL query params */
  const updateQueryParams = useCallback(
    (updates: Record<string, string | null>) => {
      if (!pathname) return;
      const params = new URLSearchParams(searchParams.toString());
      Object.entries(updates).forEach(([key, value]) =>
        value === null || value === ""
          ? params.delete(key)
          : params.set(key, value),
      );
      const qs = params.toString();
      if (qs !== searchParams.toString()) {
        router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
      }
    },
    [pathname, router, searchParams],
  );

  /** Handlers */
  const handleFilterChange =
    (field: "asset_class" | "sector") =>
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const { value } = e.target;
      setFilter((prev) => ({ ...prev, [field]: value }));
      setPage(1);
      updateQueryParams({ [field]: value || null, page: "1" });
    };

  const handlePageSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const size = parsePositiveInteger(e.target.value, DEFAULT_PAGE_SIZE);
    setPageSize(size);
    setPage(1);
    updateQueryParams({ per_page: String(size), page: "1" });
  };

  const totalPages = useMemo(
    () => (total && total > 0 ? Math.ceil(total / pageSize) : null),
    [total, pageSize],
  );

  const canGoNext = !loading && totalPages !== null && page < totalPages;
  const canGoPrev = !loading && page > 1;

  const goToPage = (requestedPage: number) => {
    const bounded = totalPages
      ? Math.min(Math.max(1, requestedPage), totalPages)
      : Math.max(1, requestedPage);
    if (bounded !== page) {
      setPage(bounded);
      updateQueryParams({ page: String(bounded) });
    }
  };

  const handleNextPage = () => goToPage(page + 1);
  const handlePrevPage = () => goToPage(page - 1);

  /** Effects */
  useEffect(() => {
    syncStateFromParams();
  }, [syncStateFromParams]);

  useEffect(() => {
    loadMetadata();
  }, [loadMetadata]);

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  /** Render helpers */
  const renderPageSizeOption = (size: number) => (
    <option key={size} value={size}>
      {size}
    </option>
  );

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="bg-white rounded-lg shadow-md p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <FilterSelect
          label="Asset Class"
          id="asset-class-filter"
          options={assetClasses}
          value={filter.asset_class}
          onChange={handleFilterChange("asset_class")}
          placeholder="All Classes"
        />
        <FilterSelect
          label="Sector"
          id="sector-filter"
          options={sectors}
          value={filter.sector}
          onChange={handleFilterChange("sector")}
          placeholder="All Sectors"
        />
      </div>

      {/* Asset Table */}
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
                {[
                  "Symbol",
                  "Name",
                  "Class",
                  "Sector",
                  "Price",
                  "Market Cap",
                ].map((heading) => (
                  <th
                    key={heading}
                    className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    {heading}
                  </th>
                ))}
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

        {/* Pagination */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-gray-50 px-6 py-4 border-t border-gray-100">
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={handlePrevPage}
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
              onClick={handleNextPage}
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
              {PAGE_SIZE_OPTIONS.map(renderPageSizeOption)}
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
