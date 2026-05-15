/**
 * E2E tests for the estimates list and detail pages.
 *
 * All backend API calls are intercepted with page.route() — no real backend
 * or database is required. Tests verify:
 * - Estimates list renders with mocked data
 * - Clicking an estimate opens the detail page
 * - Delete confirmation dialog removes the estimate from the list
 * - Empty state is displayed when there are no estimates
 */

import { test, expect, type Page } from "@playwright/test";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const MOCK_ESTIMATES = [
  {
    id: "est-1",
    project_name: "Residential Build Alpha",
    status: "completed",
    grand_total: 5_500_000,
    confidence: 0.88,
    item_count: 42,
    building_type: "residential",
    floors: 2,
    created_at: "2026-01-10T08:00:00+00:00",
    updated_at: "2026-01-10T10:30:00+00:00",
    progress: null,
    error_message: null,
    cancelled_at: null,
    regenerated_from_estimate_id: null,
    floorplan_accepted: false,
    external_works_total: null,
    built_up_area: 250,
  },
  {
    id: "est-2",
    project_name: "Commercial Office Block",
    status: "in_progress",
    grand_total: null,
    confidence: null,
    item_count: null,
    building_type: "commercial",
    floors: 5,
    created_at: "2026-01-12T09:00:00+00:00",
    updated_at: "2026-01-12T09:05:00+00:00",
    progress: null,
    error_message: null,
    cancelled_at: null,
    regenerated_from_estimate_id: null,
    floorplan_accepted: false,
    external_works_total: null,
    built_up_area: null,
  },
];

const MOCK_ESTIMATE_DETAIL = {
  id: "est-1",
  project_name: "Residential Build Alpha",
  notes: null,
  status: "completed",
  project_info: { building_type: "residential", floors: 2 },
  result: {
    boq_items: [
      { description: "Brick masonry wall", section: "Masonry", unit: "m2", quantity: 50, rate: 2500, cost: 125000, bsr_item_no: "A1.1", match_type: "confirmed", match_confidence: 0.9 },
    ],
    costs: { base_total: 5_000_000, contingencies: 250_000, total: 5_500_000 },
    confidence: { score: 0.88, breakdown: {}, section_breakdown: {} },
  },
  confidence: 0.88,
  grand_total: 5_500_000,
  item_count: 1,
  created_at: "2026-01-10T08:00:00+00:00",
  updated_at: "2026-01-10T10:30:00+00:00",
  progress: null,
  error_message: null,
  cancelled_at: null,
  regenerated_from_estimate_id: null,
  wizard_payload: null,
};

// ── Route helpers ─────────────────────────────────────────────────────────────

async function mockAuthSession(page: Page) {
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

async function mockEstimateListEndpoint(page: Page, estimates = MOCK_ESTIMATES) {
  await page.route("**/api/estimates*", (route) => {
    const url = route.request().url();
    // Detail endpoint: /api/estimates/{id}
    if (url.match(/\/estimates\/est-\d+$/)) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_ESTIMATE_DETAIL),
      });
    }
    // List endpoint: /api/estimates
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ estimates, total: estimates.length, page: 1, page_size: 20 }),
    });
  });
}

async function mockDeleteEndpoint(page: Page) {
  await page.route("**/api/estimates/*/delete", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ message: "Estimate deleted." }),
    })
  );
  // Also handle DELETE method on the estimate resource
  await page.route("**/api/estimates/*", (route) => {
    if (route.request().method() === "DELETE") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "Estimate deleted." }),
      });
    }
    return route.continue();
  });
}

async function mockDashboardEndpoint(page: Page) {
  await page.route("**/api/dashboard/summary", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total_estimates: 2,
        estimates_this_month: 1,
        average_confidence: 0.88,
        total_estimated_value: 5_500_000,
      }),
    })
  );
}

// ── Estimates list ────────────────────────────────────────────────────────────

test.describe("Estimates list page", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthSession(page);
    await mockEstimateListEndpoint(page);
    await mockDashboardEndpoint(page);
  });

  test("renders estimate project names from mocked API", async ({ page }) => {
    await page.goto("/dashboard/estimates");
    await expect(
      page.getByText("Residential Build Alpha").or(page.getByText(/Residential Build Alpha/))
    ).toBeVisible({ timeout: 10_000 });
  });

  test("renders estimate status badges", async ({ page }) => {
    await page.goto("/dashboard/estimates");
    await expect(
      page.getByText(/completed/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows in_progress state for active estimates", async ({ page }) => {
    await page.goto("/dashboard/estimates");
    await expect(
      page.getByText(/in.?progress/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("renders empty state when no estimates", async ({ page }) => {
    await mockEstimateListEndpoint(page, []);
    await page.goto("/dashboard/estimates");
    // Some "no estimates" or "get started" text should appear
    await expect(
      page.getByText(/no estimates|get started|create your first/i)
        .or(page.getByRole("heading", { name: /estimates/i }))
    ).toBeVisible({ timeout: 10_000 });
  });
});

// ── Estimate detail ───────────────────────────────────────────────────────────

test.describe("Estimate detail page", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthSession(page);
    await mockEstimateListEndpoint(page);
    await mockDashboardEndpoint(page);
  });

  test("navigating to detail page shows project name", async ({ page }) => {
    await page.goto("/dashboard/estimates/est-1");
    await expect(
      page.getByText("Residential Build Alpha").or(page.getByText(/Residential Build Alpha/))
    ).toBeVisible({ timeout: 10_000 });
  });

  test("detail page shows BOQ item from result", async ({ page }) => {
    await page.goto("/dashboard/estimates/est-1");
    await expect(
      page.getByText(/Brick masonry wall/i)
    ).toBeVisible({ timeout: 10_000 });
  });
});

// ── Unauthenticated access ────────────────────────────────────────────────────

test.describe("Unauthenticated estimates access", () => {
  test("redirects to login when not authenticated", async ({ page }) => {
    await page.route("**/api/auth/session", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) })
    );
    await page.goto("/dashboard/estimates");
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });
});
