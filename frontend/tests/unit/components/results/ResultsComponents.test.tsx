/**
 * Unit tests for ResultsComponents.
 *
 * Recharts and XLSX are mocked since they use canvas/binary APIs unavailable
 * in JSDOM. Tests focus on data-driven rendering: item rows, totals, filtering,
 * and the match confidence badges.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { BoqItem } from "@/components/results/ResultsComponents";

// ── Mock heavy dependencies ───────────────────────────────────────────────────

vi.mock("recharts", () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: () => null,
}));

vi.mock("xlsx", () => ({
  utils: {
    book_new: vi.fn(() => ({})),
    aoa_to_sheet: vi.fn(() => ({})),
    book_append_sheet: vi.fn(),
  },
  write: vi.fn(() => new Uint8Array([]).buffer),
}));

import React from "react";
import { FullBoqTable, ConfidenceBreakdownCard, CostBreakdownChart } from "@/components/results/ResultsComponents";

// ── Fixtures ──────────────────────────────────────────────────────────────────

function makeItems(count: number): BoqItem[] {
  return Array.from({ length: count }, (_, i) => ({
    description: `Item ${i + 1}`,
    section: i % 2 === 0 ? "Masonry" : "Concrete",
    unit: "m2",
    quantity: 10 + i,
    rate: 1000 + i * 100,
    cost: (10 + i) * (1000 + i * 100),
    bsr_item_no: `A${i + 1}.1`,
    match_type: "confirmed",
    match_confidence: 0.85,
  }));
}

// ── FullBoqTable ──────────────────────────────────────────────────────────────

describe("FullBoqTable", () => {
  it("renders the item count in the card title", () => {
    render(<FullBoqTable items={makeItems(5)} grandTotal={50000} />);
    expect(screen.getByText(/5 items/i)).toBeDefined();
  });

  it("renders a row for each item", () => {
    render(<FullBoqTable items={makeItems(3)} grandTotal={30000} />);
    expect(screen.getByText("Item 1")).toBeDefined();
    expect(screen.getByText("Item 2")).toBeDefined();
    expect(screen.getByText("Item 3")).toBeDefined();
  });

  it("renders the grand total in the footer", () => {
    render(<FullBoqTable items={makeItems(2)} grandTotal={99_000} />);
    expect(screen.getByText(/99,000/)).toBeDefined();
  });

  it("shows the section for each item", () => {
    render(<FullBoqTable items={makeItems(2)} grandTotal={0} />);
    expect(screen.getByText("Masonry")).toBeDefined();
    expect(screen.getByText("Concrete")).toBeDefined();
  });

  it("filters items by description when filter input changes", () => {
    render(<FullBoqTable items={makeItems(10)} grandTotal={0} />);
    const input = screen.getByPlaceholderText(/filter/i);
    fireEvent.change(input, { target: { value: "Item 5" } });
    expect(screen.getByText("Item 5")).toBeDefined();
    expect(screen.queryByText("Item 1")).toBeNull();
  });

  it("renders pagination controls when items exceed page size", () => {
    // Page size is 25 — need 26+ items to trigger pagination
    render(<FullBoqTable items={makeItems(30)} grandTotal={0} />);
    expect(screen.getByText(/Next/i)).toBeDefined();
    expect(screen.getByText(/Prev/i)).toBeDefined();
  });

  it("does not show pagination for fewer items than page size", () => {
    render(<FullBoqTable items={makeItems(5)} grandTotal={0} />);
    expect(screen.queryByText(/Next/i)).toBeNull();
  });

  it("renders empty table without crashing when items is empty", () => {
    expect(() => render(<FullBoqTable items={[]} grandTotal={0} />)).not.toThrow();
  });

  it("falls back to bsr_description when description is absent", () => {
    const item: BoqItem = { bsr_description: "Brick masonry wall", unit: "m2", match_type: "confirmed" };
    render(<FullBoqTable items={[item]} grandTotal={0} />);
    expect(screen.getByText("Brick masonry wall")).toBeDefined();
  });
});

// ── ConfidenceBreakdownCard ───────────────────────────────────────────────────

describe("ConfidenceBreakdownCard", () => {
  it("displays the confidence score as a percentage", () => {
    render(<ConfidenceBreakdownCard confidence={{ score: 0.82, breakdown: {}, section_breakdown: {} }} />);
    expect(screen.getByText(/82\.0%/)).toBeDefined();
  });

  it("renders breakdown entries when provided", () => {
    render(
      <ConfidenceBreakdownCard
        confidence={{
          score: 0.75,
          breakdown: { quantity_coverage: 0.1, match_rate: -0.05 },
          section_breakdown: {},
        }}
      />
    );
    expect(screen.getByText("quantity coverage")).toBeDefined();
    expect(screen.getByText("match rate")).toBeDefined();
  });

  it("renders section confidence bars when section_breakdown is provided", () => {
    render(
      <ConfidenceBreakdownCard
        confidence={{
          score: 0.8,
          breakdown: {},
          section_breakdown: { Masonry: { item_count: 4, matched: 3, unmatched: 1, contractual: 0 } },
        }}
      />
    );
    expect(screen.getByText(/Masonry/i)).toBeDefined();
  });

  it("handles zero confidence score without crashing", () => {
    expect(() =>
      render(<ConfidenceBreakdownCard confidence={{ score: 0, breakdown: {}, section_breakdown: {} }} />)
    ).not.toThrow();
  });
});

// ── CostBreakdownChart ────────────────────────────────────────────────────────

describe("CostBreakdownChart", () => {
  it("renders the mocked bar chart", () => {
    render(<CostBreakdownChart subtotals={{ masonry: 500000, concrete: 300000 }} />);
    expect(screen.getByTestId("bar-chart")).toBeDefined();
  });

  it("renders without crashing on empty subtotals", () => {
    expect(() => render(<CostBreakdownChart subtotals={{}} />)).not.toThrow();
  });
});
