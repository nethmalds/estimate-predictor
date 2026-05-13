// Canonical enum types matching backend canonical slugs
export type BuildingType = "residential" | "commercial" | "industrial";
export type FinishLevel = "standard" | "semi_luxury" | "luxury";
export type RoofType = "rc_flat_slab" | "clay_tile" | "asbestos_sheet" | "metal_sheet" | "other";
export type CeilingType =
  | "gypsum_mineral_fibre"
  | "timber"
  | "asbestos_flat"
  | "concrete"
  | "other";
export type AreaUnit = "sqft" | "m2";
export type StructuralSystem = "framed" | "load_bearing" | "hybrid";
export type SoilCondition = "normal" | "expansive" | "rocky" | "waterlogged";
export type DrainageType = "mains_sewer" | "septic_tank" | "soakpit" | "none";
export type ExternalWorksScope = "none" | "minimal" | "standard" | "extensive";
export type ConstructionScope = "new_build" | "extension" | "renovation" | "fit_out_only";
export type ConcreteGrade = "C20" | "C25" | "C30" | "C35";
export type WallType = "brick" | "block" | "timber_frame" | "other";
export type SanitaryFittingGrade = "basic" | "standard" | "premium";
export type ElectricalScopeLevel = "basic" | "standard" | "full";
export type WaterproofingRequirement = "none" | "wet_areas" | "full";

export interface FloorAreaRow {
  floor_label: string;
  area_value: number | "";
  area_unit: AreaUnit;
}

// Step 1
export interface ProjectBasics {
  building_type: BuildingType | "";
  floor_count: number | "";
  description: string;
  floorplan_urls: string[];
}

// Step 2
export interface FloorAreas {
  floor_areas: FloorAreaRow[];
}

// Step 3
export interface BuildingProgram {
  // Residential
  bedrooms?: number | "";
  bathrooms?: number | "";
  // Commercial
  primary_use_type?: string;
  washroom_count?: number | "";
  // Industrial
  facility_type?: string;
  heavy_machinery_load?: "yes" | "no" | "";
  hazardous_materials?: "yes" | "no" | "";
  specialized_ventilation?: "yes" | "no" | "";
}

// Step 4
export interface ConstructionDetails {
  finish_level: FinishLevel | "";
  structural_system: StructuralSystem | "";
  roof_type: RoofType | "";
  ceiling_type: CeilingType | "";
  location: string;
  soil_condition: SoilCondition | "";
  drainage_type: DrainageType | "";
  external_works_scope: ExternalWorksScope | "";
}

export interface WizardFormData {
  projectBasics: ProjectBasics;
  floorAreas: FloorAreas;
  buildingProgram: BuildingProgram;
  constructionDetails: ConstructionDetails;
}

export type WizardStepId = 1 | 2 | 3 | 4 | 5;

export interface WizardStep {
  id: WizardStepId;
  title: string;
  description: string;
}

export const WIZARD_STEPS: WizardStep[] = [
  { id: 1, title: "Project Basics", description: "Building type and floor count" },
  { id: 2, title: "Floor Areas", description: "Area per floor" },
  { id: 3, title: "Building Program", description: "Rooms and spaces" },
  { id: 4, title: "Construction Details", description: "Materials and finishes" },
  { id: 5, title: "Review & Submit", description: "Confirm and estimate" },
];

export interface EstimateStreamEvent {
  event: "progress" | "completed" | "error" | "info";
  data: Record<string, unknown>;
}

export type ExcelPreviewRow = {
  description: string;
  unit: string;
  quantity: number;
  rate: number;
  cost: number;
};

export interface WizardValidationErrors {
  [field: string]: string;
}
