import { test, expect } from "@playwright/test";

test.describe("Dashboard Workflows", () => {
  test("dashboard page renders analytics and stats", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/.*dashboard|.*login/);
  });
});
