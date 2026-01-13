/**
 * Comprehensive unit tests for AssetList component.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import AssetList from "../../app/components/AssetList";
import { api } from "../../app/lib/api";
import { mockAssetClasses, mockSectors } from "../test-utils";

jest.mock("../../app/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const mockRouterReplace = jest.fn((url: string) => {
  const queryString = url.split("?")[1] ?? "";
  mockSearch = queryString;
});
let mockSearch = "";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
  useSearchParams: () => new URLSearchParams(mockSearch),
  usePathname: () => "/assets",
}));

describe("AssetList Component", () => {
  const mockAssets = [
    {
      id: "ASSET_1",
      symbol: "AAPL",
      name: "Apple Inc.",
      asset_class: "EQUITY",
      sector: "Technology",
      price: 150.0,
      market_cap: 2400000000000,
      currency: "USD",
      additional_fields: {},
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    mockRouterReplace.mockClear();
    mockRouterReplace.mockImplementation((url: string) => {
      const queryString = url.split("?")[1] ?? "";
      mockSearch = queryString;
    });
    mockSearch = "";
    mockedApi.getAssets.mockResolvedValue({
      items: mockAssets,
      total: mockAssets.length,
      page: 1,
      per_page: 20,
    });
    mockedApi.getAssetClasses.mockResolvedValue(mockAssetClasses);
    mockedApi.getSectors.mockResolvedValue(mockSectors);
  });

  it("should render filters section", async () => {
    render(<AssetList />);

    await waitFor(() => {
      expect(screen.getByText("Filters")).toBeInTheDocument();
    });
  });

  it("should load and display assets", async () => {
    render(<AssetList />);

    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
      expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    });
  });

  it("should filter by asset class", async () => {
    render(<AssetList />);

    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });

    const assetClassSelect = screen.getByLabelText(/Asset Class/i);
    mockedApi.getAssets.mockResolvedValue({
      items: mockAssets,
      total: mockAssets.length,
      page: 1,
      per_page: 20,
    });

    fireEvent.change(assetClassSelect, { target: { value: "EQUITY" } });

    await waitFor(() => {
      expect(mockedApi.getAssets).toHaveBeenLastCalledWith({
        asset_class: "EQUITY",
        page: 1,
        per_page: 20,
      });
    });
  });

  it("should display loading state", () => {
    render(<AssetList />);
    expect(screen.getByText(/Loading results for page 1/)).toBeInTheDocument();
  });

  it("should handle empty assets", async () => {
    mockedApi.getAssets.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      per_page: 20,
    });
    render(<AssetList />);

    await waitFor(() => {
      expect(screen.getByText("No assets found")).toBeInTheDocument();
    });
  });

  it("should handle API errors gracefully", async () => {
    const consoleError = jest.spyOn(console, "error").mockImplementation();
    mockedApi.getAssets.mockRejectedValue(new Error("API Error"));

    render(<AssetList />);

    await waitFor(() => {
      expect(consoleError).toHaveBeenCalled();
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Unable to load assets for page 1, 20 per page. Please try again.",
      );
    });

    consoleError.mockRestore();
  });

  it("should request next page when pagination control is used", async () => {
    mockedApi.getAssets
      .mockResolvedValueOnce({
        items: mockAssets,
        total: 40,
        page: 1,
        per_page: 20,
      })
      .mockResolvedValueOnce({
        items: mockAssets,
        total: 40,
        page: 2,
        per_page: 20,
      });

    render(<AssetList />);

    await waitFor(() => {
      expect(mockedApi.getAssets).toHaveBeenCalled();
    });

    const nextButton = await screen.findByRole("button", { name: /Next/i });
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(mockedApi.getAssets).toHaveBeenLastCalledWith({
        page: 2,
        per_page: 20,
      });
    });
  });

  it("should respect existing query params on mount", async () => {
    mockSearch = "page=3&per_page=50&asset_class=EQUITY";
    mockedApi.getAssets.mockResolvedValue({
      items: mockAssets,
      total: 150,
      page: 3,
      per_page: 50,
    });

    render(<AssetList />);

    await waitFor(() => {
      expect(mockedApi.getAssets).toHaveBeenCalledWith({
        asset_class: "EQUITY",
        page: 3,
        per_page: 50,
      });
      expect(screen.getByDisplayValue("EQUITY")).toBeInTheDocument();
      expect(screen.getByText(/Page 3 of 3/)).toBeInTheDocument();
    });
  });
});
