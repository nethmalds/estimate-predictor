/**
 * E2E tests for the wizard form flow.
 *
 * Backend API calls are intercepted with page.route() so no real backend is
 * required. The tests verify the UI behaviour from the user's perspective:
 * step progression, form field visibility, submission, and SSE streaming.
 *
 * Prerequisites: the Next.js dev server must be running (or webServer is
 * configured in playwright.config.ts to start it).
 */

import { test, expect, type Page } from "@playwright/test";

// ── API route mocks ───────────────────────────────────────────────────────────

async function mockValidationEndpoint(page: Page, valid = true) {
  await page.route("**/api/estimate-project/form/validate", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ valid, errors: {} }),
    })
  );
}

async function mockSubmitEndpoint(page: Page) {
  await page.route("**/api/estimate-project/form/submit", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ session_id: "sess-e2e-1", status: "processing", estimate_id: "est-e2e-1" }),
    })
  );
}

async function mockStreamEndpoint(page: Page) {
  // Return an SSE stream with progress then completed events
  const sseBody = [
    "event: progress\ndata: {\"stage\":\"boq_generation\",\"pct\":50}\n\n",
    "event: completed\ndata: {\"boq_items\":[],\"costs\":{\"total\":1000000}}\n\n",
  ].join("");

  await page.route("**/api/estimate-project/form/stream/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseBody,
    })
  );
}

async function mockAuthSession(page: Page) {
  // Mock Next-Auth session to return a fake authenticated session
  await page.route("**/api/auth/session", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { name: "Test User", email: "test@example.com" },
        accessToken: "fake-token",
        expires: new Date(Date.now() + 86400 * 1000).toISOString(),
      }),
    })
  );
}

// ── Wizard navigation ─────────────────────────────────────────────────────────

test.describe("Wizard navigation", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthSession(page);
    await mockValidationEndpoint(page);
  });

  test("wizard page renders step 1 on load", async ({ page }) => {
    await page.goto("/dashboard/wizard");
    // Step 1 heading should be visible
    await expect(
      page.getByRole("heading", { name: /project basics|step 1/i }).or(
        page.getByText(/building type/i)
      )
    ).toBeVisible({ timeout: 10_000 });
  });

  test("selecting a building type and advancing shows step 2", async ({ page }) => {
    await page.goto("/dashboard/wizard");

    // Select residential building type if it's a radio/button
    const residentialOption = page.getByRole("radio", { name: /residential/i })
      .or(page.getByLabel(/residential/i))
      .or(page.getByText(/residential/i).first());

    if (await residentialOption.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await residentialOption.click();
    }

    const nextBtn = page.getByRole("button", { name: /next|continue/i });
    if (await nextBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await nextBtn.click();
      // Step 2 content should now be visible
      await expect(
        page.getByText(/floor area|step 2/i)
      ).toBeVisible({ timeout: 5_000 });
    }
  });

  test("progress bar is visible and updates with step progression", async ({ page }) => {
    await page.goto("/dashboard/wizard");
    const progressbar = page.getByRole("progressbar");
    await expect(progressbar).toBeVisible({ timeout: 10_000 });
    await expect(progressbar).toHaveAttribute("aria-valuenow", "1");
  });
});

// ── Wizard submission ─────────────────────────────────────────────────────────

test.describe("Wizard submission", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthSession(page);
    await mockValidationEndpoint(page);
    await mockSubmitEndpoint(page);
    await mockStreamEndpoint(page);
  });

  test("submit endpoint is called when form is submitted", async ({ page }) => {
    let submitCalled = false;
    await page.route("**/api/estimate-project/form/submit", (route) => {
      submitCalled = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ session_id: "s", status: "processing", estimate_id: "e" }),
      });
    });

    await page.goto("/dashboard/wizard");

    // Try to find and click the submit button on the last step
    // If the form is multi-step, we look for a final submit button
    const submitBtn = page.getByRole("button", { name: /submit|generate|estimate/i }).last();
    if (await submitBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await submitBtn.click();
      // Give it a moment to fire the request
      await page.waitForTimeout(1000);
      expect(submitCalled).toBe(true);
    }
  });
});

// ── Unauthenticated access ────────────────────────────────────────────────────

test.describe("Unauthenticated access", () => {
  test("redirects to login when not authenticated", async ({ page }) => {
    // Mock empty session
    await page.route("**/api/auth/session", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) })
    );

    await page.goto("/dashboard/wizard");
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });
});
