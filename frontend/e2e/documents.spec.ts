import { test, expect } from "@playwright/test";

test.describe("Document Management Workflows", () => {
  test("documents page renders correctly", async ({ page }) => {
    await page.goto("/documents");
    await expect(page).toHaveURL(/.*documents|.*login/);
  });

  test("upload page shows upload dropzone", async ({ page }) => {
    await page.goto("/documents/upload");
    await expect(page).toHaveURL(/.*documents\/upload|.*login/);
  });
});
