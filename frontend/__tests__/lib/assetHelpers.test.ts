import { api } from "../../app/lib/api";
import { loadAssets } from "../../app/lib/assetHelpers";

jest.mock("../../app/lib/api");

const mockedApi = api as jest.Mocked<typeof api>;

describe("loadAssets", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("clamps invalid page values before requesting assets", async () => {
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
      page: 0,
      pageSize: 20,
      filter: { asset_class: "", sector: "" },
      setAssets,
      setTotal,
      setError,
    });

    expect(mockedApi.getAssets).toHaveBeenCalledWith(
      {
        page: 1,
        per_page: 20,
      },
      undefined,
    );
  });
});
