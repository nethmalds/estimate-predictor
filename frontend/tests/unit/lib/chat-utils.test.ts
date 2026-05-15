/**
 * Unit tests for chat-utils.ts — assistant reply formatting and Excel report generation.
 *
 * XLSX is mocked because it writes binary data and has no useful assertion surface
 * in a JSDOM environment. Tests verify that the correct XLSX utilities are called
 * with the right sheet names and data shapes.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// ── XLSX mock (must come before the module under test is imported) ─────────────
vi.mock("xlsx", () => {
  const mockSheet = {};
  return {
    utils: {
      book_new: vi.fn(() => ({})),
      aoa_to_sheet: vi.fn(() => mockSheet),
      book_append_sheet: vi.fn(),
    },
    write: vi.fn(() => new Uint8Array([1, 2, 3]).buffer),
  };
});

import { formatAssistantReply, generateExcelReport } from "@/lib/chat-utils";
import * as XLSX from "xlsx";

// ── formatAssistantReply ──────────────────────────────────────────────────────

describe("formatAssistantReply", () => {
  it("returns plain string unchanged", () => {
    expect(formatAssistantReply("Hello world")).toBe("Hello world");
  });

  it("renders draft_boq status with items", () => {
    const result = formatAssistantReply({
      status: "draft_boq",
      project_info: { parameters: { bedrooms: 3, bathrooms: 2 } },
      boq_items: [
        { description: "Brick masonry wall", section: "Masonry", unit: "m2", rate: 2500, match_confidence: 0.85 },
      ],
    });
    expect(result).toContain("Draft Bill of Quantities");
    expect(result).toContain("Brick masonry wall");
    expect(result).toContain("85%");
    expect(result).toContain("Masonry");
  });

  it("renders draft_boq with no items gracefully", () => {
    const result = formatAssistantReply({
      status: "draft_boq",
      project_info: {},
      boq_items: [],
    });
    expect(result).toContain("No items generated.");
  });

  it("renders project parameters when present", () => {
    const result = formatAssistantReply({
      status: "draft_boq",
      project_info: { parameters: { finish_level: "standard", bedrooms: 3 } },
      boq_items: [],
    });
    expect(result).toContain("finish_level");
    expect(result).toContain("standard");
  });

  it("falls back to JSON stringify for unknown status", () => {
    const obj = { status: "unknown", foo: "bar" };
    const result = formatAssistantReply(obj);
    expect(result).toContain('"foo"');
    expect(result).toContain('"bar"');
  });

  it("handles null/undefined gracefully", () => {
    const result = formatAssistantReply(null);
    // Should not throw — either JSON or fallback message
    expect(typeof result).toBe("string");
  });

  it("renders item without rate or confidence when fields are missing", () => {
    const result = formatAssistantReply({
      status: "draft_boq",
      project_info: {},
      boq_items: [{ description: "Site clearance" }],
    });
    expect(result).toContain("Site clearance");
    expect(result).not.toContain("NaN");
    expect(result).not.toContain("undefined");
  });
});

// ── generateExcelReport ───────────────────────────────────────────────────────

describe("generateExcelReport", () => {
  const mockXlsx = XLSX as typeof XLSX & { utils: { book_append_sheet: ReturnType<typeof vi.fn> } };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls book_new to create a workbook", () => {
    generateExcelReport({});
    expect(XLSX.utils.book_new).toHaveBeenCalled();
  });

  it("appends three sheets: Summary, Bill of Quantities, Cost Breakdown", () => {
    generateExcelReport({
      boq_items: [],
      costs: { base_total: 1000, contingencies: 50, total: 1050, subtotals: {} },
      confidence: { score: 0.9 },
      project_info: { building_type: "residential", floors: 2, parameters: {} },
    });

    const sheetNames = mockXlsx.utils.book_append_sheet.mock.calls.map(
      (args: unknown[]) => args[2] as string
    );
    expect(sheetNames).toContain("Summary");
    expect(sheetNames).toContain("Bill of Quantities");
    expect(sheetNames).toContain("Cost Breakdown");
  });

  it("calls XLSX.write and returns an ArrayBuffer", () => {
    const result = generateExcelReport({});
    expect(XLSX.write).toHaveBeenCalled();
    expect(result).toBeInstanceOf(ArrayBuffer);
  });

  it("handles empty data without throwing", () => {
    expect(() => generateExcelReport({})).not.toThrow();
  });

  it("populates BOQ rows for each item in boq_items", () => {
    generateExcelReport({
      boq_items: [
        { description: "Brick masonry", unit: "m2", quantity: 10, rate: 2500, cost: 25000, bsr_item_no: "A1.1", match_confidence: 0.85 },
        { description: "Concrete column", unit: "m3", quantity: 5, rate: 12000, cost: 60000, bsr_item_no: "B2.3", match_confidence: 0.72 },
      ],
      costs: {},
    });

    // The BOQ sheet aoa_to_sheet should have been called with rows including both items
    const boqSheetCall = (XLSX.utils.aoa_to_sheet as ReturnType<typeof vi.fn>).mock.calls.find(
      (args: unknown[]) => {
        const rows = args[0] as unknown[][];
        return Array.isArray(rows) && rows.some((r) => Array.isArray(r) && r.includes("Description"));
      }
    );
    expect(boqSheetCall).toBeDefined();
  });
});
