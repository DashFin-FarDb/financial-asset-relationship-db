/**
 * Unit tests for asset loading helper functions, focusing on page clamping behavior.
 */

import { api } from "../../app/lib/api";
import { loadAssets } from "../../app/lib/assetHelpers";

jest.mock("../../app/lib/api");

const mockedApi = api as jest.Mocked<typeof api>;

describe("loadAssets - page clamping", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it.each([
    { page: 1, expectedPage: 1 },
    { page: 0, expectedPage: 1 },
    { page: -1, expectedPage: 1 },
  ])(
    "requests page $expectedPage when loadAssets receives page $page",
    async ({ page, expectedPage }) => {
      mockedApi.getAssets.mockResolvedValue({
        items: [],
        total: 0,
        page: 1,
        per_page: 20,
        hasMore: false,
      });

      const setAssets = jest.fn();
      const setTotal = jest.fn();
      const setError = jest.fn();

      await loadAssets({
        page,
        pageSize: 20,
        filter: { asset_class: "", sector: "" },
        setAssets,
        setTotal,
        setError,
      });

      expect(mockedApi.getAssets).toHaveBeenCalledWith({
        page: expectedPage,
        per_page: 20,
      });
    },
  );
});
