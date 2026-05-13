import { describe, it, expect } from "vitest";
import {
  step1Schema,
  step2Schema,
  step3ResidentialSchema,
  step3CommercialSchema,
  step3IndustrialSchema,
  step4Schema,
  validateStep,
} from "@/lib/schemas/wizard";
import type { WizardFormData } from "@/types/wizard";

// ── Helpers ───────────────────────────────────────────────────────────────────

const baseForm = (): WizardFormData => ({
  projectBasics: {
    building_type: "residential",
    floor_count: 2,
    description: "",
    floorplan_urls: [],
  },
  floorAreas: { floor_areas: [{ floor_label: "Ground Floor", area_value: 150, area_unit: "m2" }] },
  buildingProgram: { bedrooms: 3, bathrooms: 2 },
  constructionDetails: {
    finish_level: "standard",
    structural_system: "framed",
    roof_type: "rc_flat_slab",
    ceiling_type: "gypsum_mineral_fibre",
    location: "",
    soil_condition: "",
    drainage_type: "",
    external_works_scope: "",
  },
});

// ── Step 1 ────────────────────────────────────────────────────────────────────

describe("step1Schema", () => {
  it("accepts a valid residential payload", () => {
    const result = step1Schema.safeParse({ building_type: "residential", floor_count: 2 });
    expect(result.success).toBe(true);
  });

  it("rejects missing building_type", () => {
    const result = step1Schema.safeParse({ floor_count: 2 });
    expect(result.success).toBe(false);
  });

  it("rejects floor_count = 0", () => {
    const result = step1Schema.safeParse({ building_type: "residential", floor_count: 0 });
    expect(result.success).toBe(false);
  });

  it("rejects floor_count > 100", () => {
    const result = step1Schema.safeParse({ building_type: "residential", floor_count: 101 });
    expect(result.success).toBe(false);
  });

  it("rejects unknown building_type", () => {
    const result = step1Schema.safeParse({ building_type: "mixed_use", floor_count: 1 });
    expect(result.success).toBe(false);
  });
});

// ── Step 2 ────────────────────────────────────────────────────────────────────

describe("step2Schema", () => {
  it("accepts a valid single-floor entry", () => {
    const result = step2Schema.safeParse({
      floor_areas: [{ floor_label: "Ground Floor", area_value: 200, area_unit: "m2" }],
    });
    expect(result.success).toBe(true);
  });

  it("rejects empty floor_areas array", () => {
    const result = step2Schema.safeParse({ floor_areas: [] });
    expect(result.success).toBe(false);
  });

  it("rejects zero area_value", () => {
    const result = step2Schema.safeParse({
      floor_areas: [{ floor_label: "Ground Floor", area_value: 0, area_unit: "sqft" }],
    });
    expect(result.success).toBe(false);
  });

  it("coerces string area_value to number", () => {
    const result = step2Schema.safeParse({
      floor_areas: [{ floor_label: "Ground Floor", area_value: "120.5", area_unit: "m2" }],
    });
    expect(result.success).toBe(true);
  });
});

// ── Step 3 ────────────────────────────────────────────────────────────────────

describe("step3ResidentialSchema", () => {
  it("accepts valid bedrooms + bathrooms", () => {
    expect(step3ResidentialSchema.safeParse({ bedrooms: 3, bathrooms: 2 }).success).toBe(true);
  });

  it("rejects bedrooms = 0", () => {
    expect(step3ResidentialSchema.safeParse({ bedrooms: 0, bathrooms: 2 }).success).toBe(false);
  });

  it("rejects bedrooms > 50", () => {
    expect(step3ResidentialSchema.safeParse({ bedrooms: 51, bathrooms: 2 }).success).toBe(false);
  });
});

describe("step3CommercialSchema", () => {
  it("accepts valid washroom_count", () => {
    expect(step3CommercialSchema.safeParse({ washroom_count: 4 }).success).toBe(true);
  });

  it("rejects washroom_count = 0", () => {
    expect(step3CommercialSchema.safeParse({ washroom_count: 0 }).success).toBe(false);
  });
});

describe("step3IndustrialSchema", () => {
  it("accepts all optional fields absent", () => {
    expect(step3IndustrialSchema.safeParse({}).success).toBe(true);
  });

  it("accepts valid industrial flags", () => {
    const result = step3IndustrialSchema.safeParse({
      facility_type: "Factory",
      heavy_machinery_load: "yes",
      hazardous_materials: "no",
      specialized_ventilation: "yes",
    });
    expect(result.success).toBe(true);
  });
});

// ── Step 4 ────────────────────────────────────────────────────────────────────

describe("step4Schema", () => {
  it("accepts a valid construction details payload", () => {
    const result = step4Schema.safeParse({
      finish_level: "luxury",
      structural_system: "framed",
      roof_type: "clay_tile",
      ceiling_type: "timber",
    });
    expect(result.success).toBe(true);
  });

  it("rejects missing finish_level", () => {
    const result = step4Schema.safeParse({
      structural_system: "framed",
      roof_type: "clay_tile",
      ceiling_type: "timber",
    });
    expect(result.success).toBe(false);
  });
});

// ── validateStep integration ──────────────────────────────────────────────────

describe("validateStep", () => {
  it("returns no errors for a valid step 1", () => {
    const errors = validateStep(1, baseForm());
    expect(errors).toEqual({});
  });

  it("returns building_type error when empty on step 1", () => {
    const form = baseForm();
    form.projectBasics.building_type = "";
    const errors = validateStep(1, form);
    expect(errors.building_type).toBeDefined();
  });

  it("returns no errors for a valid step 2", () => {
    const errors = validateStep(2, baseForm());
    expect(errors).toEqual({});
  });

  it("returns no errors for a valid residential step 3", () => {
    const errors = validateStep(3, baseForm());
    expect(errors).toEqual({});
  });

  it("returns no errors for a valid step 4", () => {
    const errors = validateStep(4, baseForm());
    expect(errors).toEqual({});
  });

  it("returns no errors for step 5 (review — no validation)", () => {
    const errors = validateStep(5, baseForm());
    expect(errors).toEqual({});
  });
});