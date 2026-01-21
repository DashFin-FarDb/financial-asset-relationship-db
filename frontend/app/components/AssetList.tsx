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
 * SelectFilter component renders a dropdown select input with a label and options.
 *
 * @param {string} id - The id for the select element.
 * @param {string} label - The label text for the select.
 * @param {string[]} options - The options to display in the dropdown.
 * @param {string} value - The current selected value.
 * @param {(e: React.ChangeEvent<HTMLSelectElement>) => void} onChange - Handler for change events.
 * @param {string} placeholder - Placeholder text for the select input.
 * @returns {JSX.Element} The rendered select filter component.
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

/**
 * AssetList component fetches and displays a paginated list of assets with filters.
 *
 * @returns {JSX.Element} The asset list UI including filters and pagination controls.
 */
export default function AssetList() {
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

  const totalPages = useMemo(() => {
    if (!total || total <= 0) return null;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [pageSize, total]);

  const querySummary = useMemo(
    () => buildQuerySummary(page, pageSize, filter),
    [filter, page, pageSize],
  );

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
    loadMetadata(setAssetClasses, setSectors);
  }, []);

  useEffect(() => {
    const nextFilter: AssetFilter = {
      asset_class: searchParams.get("asset_class") ?? "",
      sector: searchParams.get("sector") ?? "",
    };

    const nextPage = parsePositiveInteger(searchParams.get("page"), 1);
    const nextPageSize = parsePositiveInteger(
      searchParams.get("per_page"),
      DEFAULT_PAGE_SIZE,
    );

    setFilter((prev) =>
      prev.asset_class === nextFilter.asset_class &&
      prev.sector === nextFilter.sector
        ? prev
        : nextFilter,
    );

    setPage((prev) => (prev === nextPage ? prev : nextPage));
    setPageSize((prev) => (prev === nextPageSize ? prev : nextPageSize));
  }, [searchParams]);

  const fetchAssets = useCallback(async () => {
    setLoading(true);
    await loadAssets(
      page,
      pageSize,
      filter,
      setAssets,
      setTotal,
      setError,
      querySummary,
    );
    setLoading(false);
  }, [filter, page, pageSize, querySummary]);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  /**
   * Creates an event handler to update the specified filter field.
   * @param field - The filter field key to update.
   * @returns A change event handler for HTMLSelectElement that updates filter and resets page.
   */
  const handleFilterChange =
    (field: keyof AssetFilter) => (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value;
      setFilter((prev) => ({ ...prev, [field]: value }));
      setPage(1);
      updateQueryParams({ [field]: value || null, page: "1" });
    };

  /**
   * Handles change event for page size select.
   * @param e - The change event from HTMLSelectElement.
   * @returns void
   */
  const handlePageSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextSize = parsePositiveInteger(e.target.value, DEFAULT_PAGE_SIZE);
    setPageSize(nextSize);
    setPage(1);
    updateQueryParams({ per_page: String(nextSize), page: "1" });
  };

  /**
   * Navigates to the specified page within valid bounds.
   * @param requestedPage - The page number requested.
   * @returns void
   */
  const goToPage = (requestedPage: number) => {
    const boundedPage =
        totalPages !== null
          ? Math.min(Math.max(1, requestedPage), totalPages)
          : Math.max(1, requestedPage);

      if (boundedPage === page) return;

      setPage(boundedPage);
      updateQueryParams({ page: String(boundedPage) });
    };

    const canGoPrev = page > 1 && !loading;
    const canGoNext = totalPages !== null && page < totalPages && !loading;

    /**
     * Renders an option element for page size selection.
     * @param size - The page size value.
     * @returns JSX.Element
     */
    const renderPageSizeOption = (size: number) => (
      <option key={size} value={size}>
        {size}
      </option>
    );

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
        <AssetListSection
          loading={loading}
          error={error}
          assets={assets}
          renderPageSizeOption={renderPageSizeOption}
          page={page}
          totalPages={totalPages}
          canGoPrev={canGoPrev}
          canGoNext={canGoNext}
          gotoPage={gotoPage}
        />
      </div>
    );
  }

  interface AssetListSectionProps {
    loading: boolean;
    error: Error | null;
    assets: Asset[];
    renderPageSizeOption: (size: number) => JSX.Element;
    page: number;
    totalPages: number | null;
    canGoPrev: boolean;
    canGoNext: boolean;
    gotoPage: (page: number) => void;
  }

  const AssetListSection: React.FC<AssetListSectionProps> = ({
    loading,
    error,
    assets,
    renderPageSizeOption,
    page,
    totalPages,
    canGoPrev,
    canGoNext,
    gotoPage,
  }) => (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      {(loading || error) && (
        <div
          className={`px-6 py-3 text-sm ${
            loading ? "text-gray-500" : "text-red-500"
          }`}
        >
          {loading ? "Loading assets..." : `Error: ${error?.message}`}
        </div>
      )}
      {!loading && !error && (
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Class
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Sector
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {assets.map((asset) => (
              <tr key={asset.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  <Link to={`/assets/${asset.id}`} className="text-blue-600">
                    {asset.name}
                  </Link>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {asset.asset_class}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {asset.sector}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => gotoPage(page)}
                    disabled={!canGoPrev}
                    className="text-indigo-600 hover:text-indigo-900"
                  >
                    Details
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="flex items-center justify-between border-t border-gray-200 px-6 py-3 bg-gray-50">
        <div>
          <label htmlFor="pageSize" className="sr-only">
            Rows per page
          </label>
          <select
            id="pageSize"
            value={pageSize}
            onChange={(e) => gotoPage(Number(e.target.value))}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
          >
            {[10, 20, 50, 100].map(renderPageSizeOption)}
          </select>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => gotoPage(page - 1)}
            disabled={!canGoPrev}
            className="px-2 py-1 bg-white border rounded"
          >
            Prev
          </button>
          <span className="text-sm text-gray-700">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => gotoPage(page + 1)}
            disabled={!canGoNext}
            className="px-2 py-1 bg-white border rounded"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
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
                ].map((col) => (
                  <th
                    key={col}
                    className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    {col}
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
                      {typeof asset.market_cap === "number"
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
