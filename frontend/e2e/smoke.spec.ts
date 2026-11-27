import { expect, test } from "@playwright/test";

const API_URL = (process.env.E2E_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

test.describe("FarDB Full-Stack E2E Smoke Suite", () => {
  test("backend liveness and bounded detailed readiness respond cleanly", async ({ request }) => {
    const healthResp = await request.get(`${API_URL}/api/health`);
    expect(healthResp.ok()).toBeTruthy();

    const detailedResp = await request.get(`${API_URL}/api/health/detailed`);
    expect(detailedResp.status()).toBe(200);
    const body = await detailedResp.json();
    expect(["healthy", "degraded"]).toContain(body.status);
    expect(typeof body.graph_persistence_configured).toBe("boolean");
    expect(body.graph).toBeTruthy();
    expect(body.database).toBeTruthy();
  });

  test("paginated assets and graph metrics API contracts succeed", async ({ request }) => {
    const assetsResp = await request.get(`${API_URL}/api/assets?page=1&per_page=5`);
    expect(assetsResp.ok()).toBeTruthy();
    const assetsPayload = await assetsResp.json();
    expect(Array.isArray(assetsPayload.items ?? assetsPayload)).toBeTruthy();

    const metricsResp = await request.get(`${API_URL}/api/graph/metrics`);
    expect(metricsResp.ok()).toBeTruthy();
    const metricsPayload = await metricsResp.json();
    expect(typeof metricsPayload.total_assets).toBe("number");
    expect(typeof metricsPayload.total_relationships).toBe("number");
  });

  test("Next.js dashboard loads and navigates all four tabs without uncaught errors", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/");

    const tabs = [
      "GRAC Demonstrator",
      "3D Visualization",
      "Metrics & Analytics",
      "Asset Explorer",
    ];
    for (const label of tabs) {
      await expect(page.getByRole("tab", { name: label })).toBeVisible();
    }

    await page.getByRole("tab", { name: "3D Visualization" }).click();
    await expect(page.locator("#tabpanel-visualization")).toBeVisible();

    await page.getByRole("tab", { name: "Metrics & Analytics" }).click();
    await expect(page.locator("#tabpanel-metrics")).toBeVisible();

    await page.getByRole("tab", { name: "Asset Explorer" }).click();
    await expect(page.locator("#tabpanel-assets")).toBeVisible();

    expect(pageErrors).toEqual([]);
  });

  test("authenticated login, /api/users/me, and /api/auth/logout revocation lifecycle", async ({ request }) => {
    const username = process.env.E2E_ADMIN_USERNAME;
    const password = process.env.E2E_ADMIN_PASSWORD;
    test.skip(!username || !password, "Set E2E_ADMIN_USERNAME and E2E_ADMIN_PASSWORD to run auth E2E flow");

    const tokenResp = await request.post(`${API_URL}/token`, {
      form: { username: username!, password: password! },
    });
    expect(tokenResp.status()).toBe(200);
    const { access_token: token } = await tokenResp.json();
    expect(typeof token).toBe("string");

    const authHeaders = { Authorization: `Bearer ${token}` };
    const meBefore = await request.get(`${API_URL}/api/users/me`, { headers: authHeaders });
    expect(meBefore.status()).toBe(200);

    const logoutResp = await request.post(`${API_URL}/api/auth/logout`, { headers: authHeaders });
    expect(logoutResp.status()).toBe(200);

    const meAfter = await request.get(`${API_URL}/api/users/me`, { headers: authHeaders });
    expect(meAfter.status()).toBe(401);
  });
});
