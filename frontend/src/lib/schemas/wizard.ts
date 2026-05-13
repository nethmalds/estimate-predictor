/**
 * Zod schemas for wizard form validation — single source of truth for the frontend.
 * Shapes mirror the backend WizardFormPayload Pydantic model (H10).
 */
import { z } from "zod";

// ── Enum literals (kept in sync with backend and wizard.ts types) ─────────────

export const BUILDING_TYPES = ["residential", "commercial", "industrial"] as const;
export const FINISH_LEVELS = ["standard", "semi_luxury", "luxury"] as const;
export const STRUCTURAL_SYSTEMS = ["framed", "load_bearing", "hybrid"] as const;
export const ROOF_TYPES = [
  "rc_flat_slab",
  "clay_tile",
  "asbestos_sheet",
  "metal_sheet",
  "other",
] as const;
export const CEILING_TYPES = [
  "gypsum_mineral_fibre",
  "timber",
  "asbestos_flat",
  "concrete",
  "other",
] as const;
export const AREA_UNITS = ["sqft", "m2"] as const;
export const SOIL_CONDITIONS = ["normal", "expansive", "rocky", "waterlogged"] as const;
export const DRAINAGE_TYPES = ["mains_sewer", "septic_tank", "soakpit", "none"] as const;
export const EXTERNAL_WORKS_SCOPES = ["none", "minimal", "standard", "extensive"] as const;

// ── Step 1 — Project Basics ────────────────────────────────────────────────────

export const step1Schema = z.object({
  building_type: z.enum(BUILDING_TYPES, {
    required_error: "Please select a building type.",
    invalid_type_error: "Please select a valid building type.",
  }),
  floor_count: z.coerce
    .number({ invalid_type_error: "Floor count must be a number." })
    .int("Floor count must be a whole number.")
    .min(1, "Floor count must be at least 1.")
    .max(100, "Floor count cannot exceed 100."),
  description: z.string().optional().default(""),
  floorplan_urls: z.array(z.string()).default([]),
});

export type Step1Data = z.infer<typeof step1Schema>;

// ── Step 2 — Floor Areas ───────────────────────────────────────────────────────

export const floorAreaRowSchema = z.object({
  floor_label: z.string().min(1, "Floor label is required."),
  area_value: z.coerce
    .number({ invalid_type_error: "Area must be a number." })
    .positive("Area must be greater than zero."),
  area_unit: z.enum(AREA_UNITS),
});

export const step2Schema = z.object({
  floor_areas: z.array(floorAreaRowSchema).min(1, "Please enter area for at least one floor."),
});

export type Step2Data = z.infer<typeof step2Schema>;

// ── Step 3 — Building Program (building-type conditional) ─────────────────────

export const step3ResidentialSchema = z.object({
  bedrooms: z.coerce
    .number({ invalid_type_error: "Bedrooms must be a number." })
    .int()
    .min(1, "Please enter a valid number of bedrooms (1–50).")
    .max(50, "Please enter a valid number of bedrooms (1–50)."),
  bathrooms: z.coerce
    .number({ invalid_type_error: "Bathrooms must be a number." })
    .int()
    .min(1, "Please enter a valid number of bathrooms (1–50).")
    .max(50, "Please enter a valid number of bathrooms (1–50)."),
});

export const step3CommercialSchema = z.object({
  primary_use_type: z.string().optional(),
  washroom_count: z.coerce
    .number({ invalid_type_error: "Washroom count must be a number." })
    .int()
    .min(1, "Commercial buildings must have at least 1 washroom."),
});

export const step3IndustrialSchema = z.object({
  facility_type: z.string().optional(),
  heavy_machinery_load: z.enum(["yes", "no"]).optional(),
  hazardous_materials: z.enum(["yes", "no"]).optional(),
  specialized_ventilation: z.enum(["yes", "no"]).optional(),
});

// ── Step 4 — Construction Details ─────────────────────────────────────────────

export const step4Schema = z.object({
  finish_level: z.enum(FINISH_LEVELS, {
    required_error: "Please select a finish level.",
  }),
  structural_system: z.enum(STRUCTURAL_SYSTEMS, {
    required_error: "Please select a structural system.",
  }),
  roof_type: z.enum(ROOF_TYPES, {
    required_error: "Please select a roof type.",
  }),
  ceiling_type: z.enum(CEILING_TYPES, {
    required_error: "Please select a ceiling type.",
  }),
  location: z.string().optional().default(""),
  soil_condition: z.enum(SOIL_CONDITIONS).optional(),
  drainage_type: z.enum(DRAINAGE_TYPES).optional(),
  external_works_scope: z.enum(EXTERNAL_WORKS_SCOPES).optional(),
});

export type Step4Data = z.infer<typeof step4Schema>;

// ── validateStep helper — returns a flat error map ─────────────────────────────

import type { WizardFormData, WizardStepId } from "@/types/wizard";

export function validateStep(step: WizardStepId, form: WizardFormData): Record<string, string> {
  const flatten = (result: z.SafeParseReturnType<unknown, unknown>): Record<string, string> => {
    if (result.success) return {};
    return Object.fromEntries(result.error.errors.map((e) => [e.path.join(".") || "_", e.message]));
  };

  if (step === 1) {
    return flatten(
      step1Schema.safeParse({
        building_type: form.projectBasics.building_type || undefined,
        floor_count: form.projectBasics.floor_count,
        description: form.projectBasics.description,
        floorplan_urls: form.projectBasics.floorplan_urls,
      })
    );
  }

  if (step === 2) {
    return flatten(step2Schema.safeParse(form.floorAreas));
  }

  if (step === 3) {
    const buildingType = form.projectBasics.building_type;
    if (buildingType === "residential") {
      return flatten(step3ResidentialSchema.safeParse(form.buildingProgram));
    }
    if (buildingType === "commercial") {
      return flatten(step3CommercialSchema.safeParse(form.buildingProgram));
    }
    if (buildingType === "industrial") {
      return flatten(step3IndustrialSchema.safeParse(form.buildingProgram));
    }
  }

  if (step === 4) {
    return flatten(
      step4Schema.safeParse({
        finish_level: form.constructionDetails.finish_level || undefined,
        structural_system: form.constructionDetails.structural_system || undefined,
        roof_type: form.constructionDetails.roof_type || undefined,
        ceiling_type: form.constructionDetails.ceiling_type || undefined,
        location: form.constructionDetails.location,
        soil_condition: form.constructionDetails.soil_condition || undefined,
        drainage_type: form.constructionDetails.drainage_type || undefined,
        external_works_scope: form.constructionDetails.external_works_scope || undefined,
      })
    );
  }

  return {};
}
