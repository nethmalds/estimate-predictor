import { test, expect } from "@playwright/test";

/**
 * Auth E2E smoke tests.
 * Requires a running backend + database with a seeded test user.
 * Set TEST_USER_EMAIL and TEST_USER_PASSWORD env vars for real creds.
 */

const EMAIL = process.env.TEST_USER_EMAIL ?? "test@example.com";
const PASSWORD = process.env.TEST_USER_PASSWORD ?? "testpassword123";

test.describe("Login flow", () => {
  test("login page renders correctly", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /sign in|log in/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in|log in/i })).toBeVisible();
  });

  test("shows error on wrong credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("wrong@example.com");
    await page.getByLabel(/password/i).fill("wrongpassword");
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    // NextAuth error surfaces in the URL or as an inline message
    await expect(
      page.getByText(/invalid|incorrect|wrong|try again/i).or(page.getByRole("alert"))
    ).toBeVisible({ timeout: 8_000 });
  });

  test("redirects unauthenticated users from /dashboard to /login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/login/);
  });
});

test.describe("Register flow", () => {
  test("register page renders correctly", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByRole("heading", { name: /register|sign up|create/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
  });
});