"use client";

import { WizardFormData, WizardStepId } from "@/types/wizard";
import { Edit2 } from "lucide-react";

interface Props {
  data: WizardFormData;
  onEditStep: (step: WizardStepId) => void;
  isSubmitting: boolean;
  error: string | null;
}

const BUILDING_TYPE_LABELS: Record<string, string> = {
  residential: "Residential",
  commercial: "Commercial",
  industrial: "Industrial",
};

function SectionHeader({
  title,
  step,
  onEdit,
}: {
  title: string;
  step: WizardStepId;
  onEdit: (s: WizardStepId) => void;
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h3 className="text-foreground text-sm font-semibold">{title}</h3>
      <button
        type="button"
        onClick={() => onEdit(step)}
        className="flex items-center gap-1 text-xs text-blue-500 transition-colors hover:text-blue-600"
      >
        <Edit2 className="h-3 w-3" /> Edit
      </button>
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (!value && value !== 0) return null;
  return (
    <div className="border-border flex justify-between border-b py-1.5 last:border-0">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span className="text-foreground text-xs font-medium">{String(value)}</span>
    </div>
  );
}

export function ReviewSubmitStep({ data, onEditStep, isSubmitting, error }: Props) {
  const { projectBasics, floorAreas, buildingProgram, constructionDetails } = data;

  // Compute total area
  const totalSqft = floorAreas.floor_areas.reduce((sum, row) => {
    const v =
      typeof row.area_value === "number" ? row.area_value : parseFloat(String(row.area_value)) || 0;
    return sum + (row.area_unit === "m2" ? v / 0.0929 : v);
  }, 0);

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-destructive/10 border-destructive/30 text-destructive rounded-lg border p-3 text-sm">
          {error}
        </div>
      )}

      {/* Project Basics */}
      <div className="bg-muted/50 border-border rounded-lg border p-4">
        <SectionHeader title="Project Basics" step={1} onEdit={onEditStep} />
        <ReviewRow
          label="Building Type"
          value={
            BUILDING_TYPE_LABELS[String(projectBasics.building_type)] ||
            String(projectBasics.building_type)
          }
        />
        <ReviewRow label="Number of Floors" value={projectBasics.floor_count} />
        {projectBasics.description && (
          <ReviewRow label="Description" value={projectBasics.description} />
        )}
      </div>

      {/* Floor Areas */}
      <div className="bg-muted/50 border-border rounded-lg border p-4">
        <SectionHeader title="Floor Areas" step={2} onEdit={onEditStep} />
        {floorAreas.floor_areas.map((row, i) => (
          <ReviewRow key={i} label={row.floor_label} value={`${row.area_value} ${row.area_unit}`} />
        ))}
        <div className="border-border mt-2 border-t pt-2">
          <ReviewRow
            label="Total Built-Up Area"
            value={`${totalSqft.toFixed(0)} sqft (${(totalSqft * 0.0929).toFixed(1)} m²)`}
          />
        </div>
      </div>

      {/* Building Program */}
      <div className="bg-muted/50 border-border rounded-lg border p-4">
        <SectionHeader title="Building Program" step={3} onEdit={onEditStep} />
        {projectBasics.building_type === "residential" && (
          <>
            <ReviewRow label="Bedrooms" value={buildingProgram.bedrooms} />
            <ReviewRow label="Bathrooms" value={buildingProgram.bathrooms} />
          </>
        )}
        {projectBasics.building_type === "commercial" && (
          <>
            <ReviewRow label="Primary Use" value={buildingProgram.primary_use_type} />
            <ReviewRow label="Washrooms" value={buildingProgram.washroom_count} />
          </>
        )}
        {projectBasics.building_type === "industrial" && (
          <>
            <ReviewRow label="Facility Type" value={buildingProgram.facility_type} />
            <ReviewRow
              label="Heavy Machinery Load"
              value={
                buildingProgram.heavy_machinery_load
                  ? buildingProgram.heavy_machinery_load.toUpperCase()
                  : null
              }
            />
            <ReviewRow
              label="Hazardous Materials"
              value={
                buildingProgram.hazardous_materials
                  ? buildingProgram.hazardous_materials.toUpperCase()
                  : null
              }
            />
            <ReviewRow
              label="Specialized Ventilation"
              value={
                buildingProgram.specialized_ventilation
                  ? buildingProgram.specialized_ventilation.toUpperCase()
                  : null
              }
            />
          </>
        )}
      </div>

      {/* Construction Details */}
      <div className="bg-muted/50 border-border rounded-lg border p-4">
        <SectionHeader title="Construction Details" step={4} onEdit={onEditStep} />
        <ReviewRow label="Finish Level" value={constructionDetails.finish_level} />
        <ReviewRow label="Structural System" value={constructionDetails.structural_system} />
        <ReviewRow label="Roof Type" value={constructionDetails.roof_type} />
        <ReviewRow label="Ceiling Type" value={constructionDetails.ceiling_type} />
        <ReviewRow label="Location" value={constructionDetails.location} />
        <ReviewRow label="Soil Condition" value={constructionDetails.soil_condition} />
        <ReviewRow label="Drainage Type" value={constructionDetails.drainage_type} />
        <ReviewRow label="External Works" value={constructionDetails.external_works_scope} />
      </div>

      {isSubmitting && (
        <div className="text-muted-foreground py-4 text-center text-sm">
          Submitting and starting estimation...
        </div>
      )}
    </div>
  );
}
