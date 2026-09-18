import { test, expect } from "@playwright/test";

test.describe("Authentication Workflows", () => {
  test("navigates to login and shows authentication inputs", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("h1, h2")).toContainText(/Sign in|Welcome back/i);
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test("navigates from login to register page", async ({ page }) => {
    await page.goto("/login");
    await page.click('a[href="/register"]');
    await expect(page).toHaveURL(/.*register/);
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });
});
