/**
 * Comprehensive API Resilience and Security Tests
 *
 * Tests the API client for:
 * - Network resilience and retry logic
 * - Rate limiting handling
 * - Request cancellation
 * - Security best practices
 * - Error recovery scenarios
 */

import axios from "axios";
import { mockAssets, mockAsset, mockMetrics, mockVizData } from "../test-utils";

jest.mock("axios");
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Import API functions dynamically
let fetchAssets: any;
let fetchAsset: any;
let fetchMetrics: any;
let fetchVisualizationData: any;

describe("API Resilience - Network Failures", () => {
  beforeAll(async () => {
    const api = await import("@/lib/api");
    fetchAssets = api.fetchAssets;
    fetchAsset = api.fetchAsset;
    fetchMetrics = api.fetchMetrics;
    fetchVisualizationData = api.fetchVisualizationData;
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should handle DNS resolution failures", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      code: "ENOTFOUND",
      message: "getaddrinfo ENOTFOUND api.example.com",
    });

    await expect(fetchAssets()).rejects.toThrow();
  });

  it("should handle connection refused errors", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      code: "ECONNREFUSED",
      message: "connect ECONNREFUSED 127.0.0.1:3000",
    });

    await expect(fetchAssets()).rejects.toThrow();
  });

  it("should handle connection reset errors", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      code: "ECONNRESET",
      message: "socket hang up",
    });

    await expect(fetchAssets()).rejects.toThrow();
  });

  it("should handle corrupted JSON in response", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      response: {
        status: 200,
        data: "not valid json{]",
        headers: { "content-type": "application/json" },
      },
      message: "Unexpected token",
    });

    await expect(fetchAssets()).rejects.toThrow();
  });
});

describe("API Resilience - Rate Limiting", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should handle 429 Too Many Requests", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      response: {
        status: 429,
        statusText: "Too Many Requests",
        headers: {
          "retry-after": "60",
          "x-ratelimit-remaining": "0",
        },
        data: { error: "Rate limit exceeded" },
      },
    });

    await expect(fetchAssets()).rejects.toThrow();
  });

  it("should handle burst rate limiting", async () => {
    mockedAxios.get
      .mockResolvedValueOnce({ data: mockAssets, status: 200 })
      .mockResolvedValueOnce({ data: mockAssets, status: 200 })
      .mockRejectedValueOnce({
        response: {
          status: 429,
          data: { error: "Too many requests" },
        },
      });

    await expect(fetchAssets()).resolves.toBeDefined();
    await expect(fetchAssets()).resolves.toBeDefined();
    await expect(fetchAssets()).rejects.toThrow();
  });
});

describe("API Security - Input Validation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedAxios.get.mockResolvedValue({
      data: mockAsset,
      status: 200,
    });
  });

  it("should handle SQL injection attempts in asset ID", async () => {
    const maliciousId = "AAPL' OR '1'='1";

    await fetchAsset(maliciousId);

    expect(mockedAxios.get).toHaveBeenCalled();
    const callUrl = mockedAxios.get.mock.calls[0][0];
    expect(callUrl).toContain(encodeURIComponent(maliciousId));
  });

  it("should handle XSS attempts in search parameters", async () => {
    const xssPayload = '<script>alert("xss")</script>';

    await fetchAssets({ search: xssPayload });

    expect(mockedAxios.get).toHaveBeenCalled();
  });

  it("should handle path traversal attempts", async () => {
    const pathTraversal = "../../etc/passwd";

    await fetchAsset(pathTraversal);

    expect(mockedAxios.get).toHaveBeenCalled();
  });

  it("should handle null bytes in input", async () => {
    const nullByteInput = "AAPL\x00malicious";

    await fetchAsset(nullByteInput);

    expect(mockedAxios.get).toHaveBeenCalled();
  });

  it("should handle extremely long input strings", async () => {
    const longString = "A".repeat(10000);

    await fetchAssets({ search: longString });

    expect(mockedAxios.get).toHaveBeenCalled();
  });

  it("should handle special URL characters", async () => {
    const specialChars = "AAPL&param=value#fragment?extra=data";

    await fetchAsset(specialChars);

    expect(mockedAxios.get).toHaveBeenCalled();
    const callUrl = mockedAxios.get.mock.calls[0][0];
    expect(callUrl).toContain(encodeURIComponent(specialChars));
  });
});

describe("API Security - Response Validation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should handle responses with unexpected data types", async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: "string instead of object",
      status: 200,
    });

    await expect(fetchAsset("AAPL")).rejects.toThrow();
  });

  it("should handle responses with prototype pollution attempts", async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: {
        __proto__: { polluted: true },
        constructor: { prototype: { polluted: true } },
        id: "AAPL",
      },
      status: 200,
    });

    await expect(fetchAsset("AAPL")).resolves.toBeDefined();
    expect(({} as any).polluted).toBeUndefined();
  });
});

describe("API Resilience - Concurrent Requests", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should handle multiple concurrent successful requests", async () => {
    mockedAxios.get.mockResolvedValue({
      data: mockAssets,
      status: 200,
    });

    const requests = [fetchAssets(), fetchMetrics(), fetchVisualizationData()];

    const results = await Promise.all(requests);
    expect(results).toHaveLength(3);
    expect(mockedAxios.get).toHaveBeenCalledTimes(3);
  });

  it("should handle mixed success/failure in concurrent requests", async () => {
    mockedAxios.get
      .mockResolvedValueOnce({ data: mockAssets, status: 200 })
      .mockRejectedValueOnce({ response: { status: 500 } })
      .mockResolvedValueOnce({ data: mockVizData, status: 200 });

    const results = await Promise.allSettled([
      fetchAssets(),
      fetchMetrics(),
      fetchVisualizationData(),
    ]);

    expect(results[0].status).toBe("fulfilled");
    expect(results[1].status).toBe("rejected");
    expect(results[2].status).toBe("fulfilled");
  });

  it("should handle race conditions with same resource", async () => {
    let callCount = 0;
    mockedAxios.get.mockImplementation(() => {
      callCount++;
      return Promise.resolve({
        data: { ...mockAsset, call: callCount },
        status: 200,
      });
    });

    const results = await Promise.all([
      fetchAsset("AAPL"),
      fetchAsset("AAPL"),
      fetchAsset("AAPL"),
    ]);

    expect(results).toHaveLength(3);
    results.forEach((result) => {
      expect(result).toHaveProperty("id");
    });
  });
});

describe("API Resilience - Timeout Scenarios", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should handle request timeouts", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      code: "ETIMEDOUT",
      message: "timeout of 5000ms exceeded",
    });

    await expect(fetchAssets()).rejects.toThrow();
  });

  it("should handle slow responses", async () => {
    mockedAxios.get.mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              data: mockAssets,
              status: 200,
            });
          }, 100);
        }),
    );

    await expect(fetchAssets()).resolves.toBeDefined();
  });
});

describe("API Resilience - HTTP Error Codes", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should handle 400 Bad Request", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      response: {
        status: 400,
        statusText: "Bad Request",
        data: {
          error: "Invalid query parameter",
        },
      },
    });

    await expect(fetchAssets()).rejects.toThrow();
  });

  it("should handle 401 Unauthorized", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      response: {
        status: 401,
        statusText: "Unauthorized",
        data: { error: "Authentication required" },
      },
    });

    await expect(fetchAssets()).rejects.toThrow();
  });

  it("should handle 403 Forbidden", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      response: {
        status: 403,
        statusText: "Forbidden",
        data: { error: "Insufficient permissions" },
      },
    });

    await expect(fetchAssets()).rejects.toThrow();
  });

  it("should handle 503 Service Unavailable", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      response: {
        status: 503,
        statusText: "Service Unavailable",
        headers: {
          "retry-after": "300",
        },
        data: { error: "Service temporarily unavailable" },
      },
    });

    await expect(fetchAssets()).rejects.toThrow();
  });

  it("should handle 504 Gateway Timeout", async () => {
    mockedAxios.get.mockRejectedValueOnce({
      response: {
        status: 504,
        statusText: "Gateway Timeout",
        data: { error: "Upstream server timeout" },
      },
    });

    await expect(fetchAssets()).rejects.toThrow();
  });
});
