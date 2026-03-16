"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { Asset } from "../types/api";
import {
  buildQuerySummary,
  loadAssets,
  loadMetadata,
  parsePositiveInteger,
} from "../lib/assetHelpers";

const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

type AssetFilter = {
  asset_class: string;
  sector: string;
};

type SelectFilterProps = {
  id: string;
  label: string;
  options: string[];
  value: string;
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  placeholder: string;
};

/**
 * Renders a select filter input with a label and list of options.
 * @param {string} id - The id attribute for the select element.
 * @param {string} label - The text label for the select input.
 * @param {string[]} options - Array of options to display in the dropdown.
 * @param {string} value - The current selected value.
 * @param {(e: React.ChangeEvent<HTMLSelectElement>) => void} onChange - Handler for change events.
 * @param {string} placeholder - Placeholder text for the default empty option.
 * @returns {JSX.Element} The SelectFilter component.
 */
const SelectFilter = ({
  id,
  label,
  options,
  value,
  onChange,
  placeholder,
}: SelectFilterProps) => (
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

type AssetListStatusProps = Readonly<{
  loading: boolean;
  error: string | null;
}>;

type AssetListTableProps = Readonly<{
  assets: Asset[];
  loading: boolean;
  error: string | null;
}>;

type AssetListController = {
  assets: Asset[];
  loading: boolean;
  error: string | null;
  filter: AssetFilter;
  assetClasses: string[];
  sectors: string[];
  page: number;
  pageSize: number;
  totalPages: number | null;
  canGoPrev: boolean;
  canGoNext: boolean;
  handleFilterChange: (
    field: keyof AssetFilter,
  ) => (e: React.ChangeEvent<HTMLSelectElement>) => void;
  handlePageSizeChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  handlePrevClick: () => void;
  handleNextClick: () => void;
};

const renderPageSizeOption = (size: number) => (
  <option key={size} value={size}>
    {size}
  </option>
);

function AssetListStatus({ loading, error }: AssetListStatusProps) {
  const hasError = error !== null;
  if (!loading && !hasError) {
    return null;
  }

  return (
    <div
      className={`px-6 py-3 text-sm ${
        hasError ? "text-red-500" : "text-gray-500"
      }`}
    >
      {hasError ? `Error: ${error}` : "Loading..."}
    </div>
  );
}

function AssetListTable({ assets, loading, error }: AssetListTableProps) {
  let tableRows: React.ReactNode;
  if (loading) {
    tableRows = (
      <tr>
        <td colSpan={6} className="px-6 py-4 text-center text-gray-500">
          Loading...
        </td>
      </tr>
    );
  } else if (error) {
    tableRows = (
      <tr>
        <td colSpan={6} className="px-6 py-4 text-center text-red-600">
          {error}
        </td>
      </tr>
    );
  } else if (assets.length === 0) {
    tableRows = (
      <tr>
        <td colSpan={6} className="px-6 py-4 text-center text-gray-500">
          No assets found
        </td>
      </tr>
    );
  } else {
    tableRows = assets.map((asset) => (
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
          {typeof asset.price === "number"
            ? `${asset.currency} ${asset.price.toFixed(2)}`
            : "N/A"}
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
          {typeof asset.market_cap === "number"
            ? `$${(asset.market_cap / 1e9).toFixed(2)}B`
            : "N/A"}
        </td>
      </tr>
    ));
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {["Symbol", "Name", "Class", "Sector", "Price", "Market Cap"].map(
              (col) => (
                <th
                  key={col}
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {col}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">{tableRows}</tbody>
      </table>
    </div>
  );
}

type SearchState = {
  filter: AssetFilter;
  page: number;
  pageSize: number;
};

function computeTotalPages(
  total: number | null,
  pageSize: number,
): number | null {
  if (!total || total <= 0) {
    return null;
  }
  return Math.max(1, Math.ceil(total / pageSize));
}

function createUpdatedSearchParams(
  currentParams: URLSearchParams,
  updates: Record<string, string | null>,
): URLSearchParams {
  const params = new URLSearchParams(currentParams.toString());
  Object.entries(updates).forEach(([key, value]) => {
    if (value === null || value === "") {
      params.delete(key);
    } else {
      params.set(key, value);
    }
  });
  return params;
}

function readSearchState(searchParams: URLSearchParams): SearchState {
  return {
    filter: {
      asset_class: searchParams.get("asset_class") ?? "",
      sector: searchParams.get("sector") ?? "",
    },
    page: parsePositiveInteger(searchParams.get("page"), 1),
    pageSize: parsePositiveInteger(
      searchParams.get("per_page"),
      DEFAULT_PAGE_SIZE,
    ),
  };
}

type NavigationControls = {
  canGoPrev: boolean;
  canGoNext: boolean;
  handleFilterChange: (
    field: keyof AssetFilter,
  ) => (e: React.ChangeEvent<HTMLSelectElement>) => void;
  handlePageSizeChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  handlePrevClick: () => void;
  handleNextClick: () => void;
};

type NavigationControlsParams = Readonly<{
  pathname: string | null;
  searchParams: URLSearchParams;
  router: ReturnType<typeof useRouter>;
  page: number;
  totalPages: number | null;
  loading: boolean;
  setPage: React.Dispatch<React.SetStateAction<number>>;
  setPageSize: React.Dispatch<React.SetStateAction<number>>;
  setFilter: React.Dispatch<React.SetStateAction<AssetFilter>>;
}>;

type AssetDataLoadingParams = Readonly<{
  page: number;
  pageSize: number;
  filter: AssetFilter;
  querySummary: string;
  setAssets: React.Dispatch<React.SetStateAction<Asset[]>>;
  setTotal: React.Dispatch<React.SetStateAction<number | null>>;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
}>;

type QueryUpdaterParams = Readonly<{
  pathname: string | null;
  searchParams: URLSearchParams;
  router: ReturnType<typeof useRouter>;
}>;

function useSearchStateSync(
  searchParams: URLSearchParams,
  setFilter: React.Dispatch<React.SetStateAction<AssetFilter>>,
  setPage: React.Dispatch<React.SetStateAction<number>>,
  setPageSize: React.Dispatch<React.SetStateAction<number>>,
) {
  useEffect(() => {
    const stateFromSearch = readSearchState(searchParams);
    setFilter((prev) =>
      prev.asset_class === stateFromSearch.filter.asset_class &&
      prev.sector === stateFromSearch.filter.sector
        ? prev
        : stateFromSearch.filter,
    );
    setPage((prev) =>
      prev === stateFromSearch.page ? prev : stateFromSearch.page,
    );
    setPageSize((prev) =>
      prev === stateFromSearch.pageSize ? prev : stateFromSearch.pageSize,
    );
  }, [searchParams, setFilter, setPage, setPageSize]);
}

function useAssetDataLoading({
  page,
  pageSize,
  filter,
  querySummary,
  setAssets,
  setTotal,
  setError,
  setLoading,
}: AssetDataLoadingParams) {
  const fetchAssets = useCallback(async () => {
    setLoading(true);
    await loadAssets({
      page,
      pageSize,
      filter,
      setAssets,
      setTotal,
      setError,
      querySummary,
    });
    setLoading(false);
  }, [
    filter,
    page,
    pageSize,
    querySummary,
    setAssets,
    setError,
    setLoading,
    setTotal,
  ]);

  useEffect(() => {
    void fetchAssets().catch((err) => {
      setError(err instanceof Error ? err.message : "Failed to load assets");
      setLoading(false);
    });
  }, [fetchAssets, setError, setLoading]);
}

function useQueryParamUpdater({
  pathname,
  searchParams,
  router,
}: QueryUpdaterParams) {
  return useCallback(
    (updates: Record<string, string | null>) => {
      if (!pathname) return;
      const params = createUpdatedSearchParams(searchParams, updates);
      const queryString = params.toString();
      if (queryString !== searchParams.toString()) {
        const nextPath = queryString ? `${pathname}?${queryString}` : pathname;
        router.replace(nextPath, { scroll: false });
      }
    },
    [pathname, router, searchParams],
  );
}

function useNavigationControls({
  pathname,
  searchParams,
  router,
  page,
  totalPages,
  loading,
  setPage,
  setPageSize,
  setFilter,
}: NavigationControlsParams): NavigationControls {
  const updateQueryParams = useQueryParamUpdater({
    pathname,
    searchParams,
    router,
  });

  const handleFilterChange =
    (field: keyof AssetFilter) => (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value;
      setFilter((prev) => ({ ...prev, [field]: value }));
      setPage(1);
      updateQueryParams({ [field]: value || null, page: "1" });
    };

  const handlePageSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextSize = parsePositiveInteger(e.target.value, DEFAULT_PAGE_SIZE);
    setPageSize(nextSize);
    setPage(1);
    updateQueryParams({ per_page: String(nextSize), page: "1" });
  };

  const goToPage = useCallback(
    (requestedPage: number) => {
      const boundedPage =
        totalPages === null
          ? Math.max(1, requestedPage)
          : Math.min(Math.max(1, requestedPage), totalPages);
      if (boundedPage === page) return;
      setPage(boundedPage);
      updateQueryParams({ page: String(boundedPage) });
    },
    [page, totalPages, setPage, updateQueryParams],
  );

  const canGoPrev = page > 1 && !loading;
  const canGoNext = totalPages !== null && page < totalPages && !loading;

  const handlePrevClick = useCallback(() => {
    goToPage(page - 1);
  }, [goToPage, page]);

  const handleNextClick = useCallback(() => {
    goToPage(page + 1);
  }, [goToPage, page]);

  return {
    canGoPrev,
    canGoNext,
    handleFilterChange,
    handlePageSizeChange,
    handlePrevClick,
    handleNextClick,
  };
}

function useAssetListController(): AssetListController {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<AssetFilter>({
    asset_class: "",
    sector: "",
  });
  const [assetClasses, setAssetClasses] = useState<string[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState<number | null>(null);

  const totalPages = useMemo(
    () => computeTotalPages(total, pageSize),
    [pageSize, total],
  );

  const querySummary = useMemo(
    () => buildQuerySummary(page, pageSize, filter),
    [filter, page, pageSize],
  );

  useEffect(() => {
    loadMetadata(setAssetClasses, setSectors);
  }, []);

  useSearchStateSync(searchParams, setFilter, setPage, setPageSize);
  useAssetDataLoading({
    page,
    pageSize,
    filter,
    querySummary,
    setAssets,
    setTotal,
    setError,
    setLoading,
  });

  const {
    canGoPrev,
    canGoNext,
    handleFilterChange,
    handlePageSizeChange,
    handlePrevClick,
    handleNextClick,
  } = useNavigationControls({
    pathname,
    searchParams,
    router,
    page,
    totalPages,
    loading,
    setPage,
    setPageSize,
    setFilter,
  });

  return {
    assets,
    loading,
    error,
    filter,
    assetClasses,
    sectors,
    page,
    pageSize,
    totalPages,
    canGoPrev,
    canGoNext,
    handleFilterChange,
    handlePageSizeChange,
    handlePrevClick,
    handleNextClick,
  };
}

/**
 * Fetches and displays a list of assets with filtering and pagination.
 *
 * @returns {JSX.Element} The AssetList component.
 */
export default function AssetList() {
  const {
    assets,
    loading,
    error,
    filter,
    assetClasses,
    sectors,
    page,
    pageSize,
    totalPages,
    canGoPrev,
    canGoNext,
    handleFilterChange,
    handlePageSizeChange,
    handlePrevClick,
    handleNextClick,
  } = useAssetListController();

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="bg-white rounded-lg shadow-md p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <SelectFilter
          id="asset-class-filter"
          label="Asset Class"
          options={assetClasses}
          value={filter.asset_class}
          onChange={handleFilterChange("asset_class")}
          placeholder="All Classes"
        />
        <SelectFilter
          id="sector-filter"
          label="Sector"
          options={sectors}
          value={filter.sector}
          onChange={handleFilterChange("sector")}
          placeholder="All Sectors"
        />
      </div>

      {/* Asset List */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <AssetListStatus loading={loading} error={error} />

        <AssetListTable assets={assets} loading={loading} error={error} />

        {/* Pagination */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-gray-50 px-6 py-4 border-t border-gray-100">
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={handlePrevClick}
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
              onClick={handleNextClick}
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
