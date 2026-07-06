import type { AssetPageResponse, VisualizationData } from "../../app/types/api";

describe("API contract seams", () => {
  it("uses hasMore as the frontend pagination key", () => {
    const page: AssetPageResponse = {
      items: [],
      total: 2,
      page: 1,
      per_page: 1,
      hasMore: true,
    };

    expect(Object.keys(page)).toEqual(
      expect.arrayContaining(["items", "total", "page", "per_page", "hasMore"]),
    );
  });

  it("requires visualization data to include network_density", () => {
    const data: VisualizationData = {
      nodes: [],
      edges: [],
      network_density: 0,
    };

    expect(data.network_density).toBe(0);
  });
});
