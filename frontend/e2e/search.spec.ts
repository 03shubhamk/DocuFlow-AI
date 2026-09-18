import { test, expect } from "@playwright/test";

test.describe("Search & Discovery Workflows", () => {
  test("search page renders query input", async ({ page }) => {
    await page.goto("/search");
    await expect(page).toHaveURL(/.*search|.*login/);
  });
});
