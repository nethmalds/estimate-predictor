"use client";

import { ConstructionDetails } from "@/types/wizard";

interface Props {
  data: ConstructionDetails;
  onChange: (data: ConstructionDetails) => void;
  errors: Record<string, string>;
}

const selectClass = "w-full bg-background border border-input text-foreground rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ring";
const inputClass = selectClass;
const labelClass = "block text-sm font-medium text-foreground mb-2";

export function ConstructionDetailsStep({ data, onChange, errors }: Props) {
  const field = <K extends keyof ConstructionDetails>(key: K, value: ConstructionDetails[K]) =>
    onChange({ ...data, [key]: value });

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-6">
        <div>
          <label className={labelClass}>Finish Level <span className="text-red-400">*</span></label>
          <select value={data.finish_level} onChange={(e) => field("finish_level", e.target.value as ConstructionDetails["finish_level"])} className={`${selectClass} ${errors.finish_level ? "border-red-500" : ""}`}>
            <option value="">Select...</option>
            <option value="standard">Standard</option>
            <option value="semi_luxury">Semi-Luxury</option>
            <option value="luxury">Luxury</option>
          </select>
          {errors.finish_level && <p className="mt-1 text-xs text-destructive">{errors.finish_level}</p>}
        </div>

        <div>
          <label className={labelClass}>Structural System <span className="text-red-400">*</span></label>
          <select value={data.structural_system} onChange={(e) => field("structural_system", e.target.value as ConstructionDetails["structural_system"])} className={`${selectClass} ${errors.structural_system ? "border-red-500" : ""}`}>
            <option value="">Select...</option>
            <option value="framed">Framed (RC Columns &amp; Beams)</option>
            <option value="load_bearing">Load Bearing Masonry</option>
            <option value="hybrid">Hybrid</option>
          </select>
          {errors.structural_system && <p className="mt-1 text-xs text-destructive">{errors.structural_system}</p>}
        </div>

        <div>
          <label className={labelClass}>Roof Type <span className="text-red-400">*</span></label>
          <select value={data.roof_type} onChange={(e) => field("roof_type", e.target.value as ConstructionDetails["roof_type"])} className={`${selectClass} ${errors.roof_type ? "border-red-500" : ""}`}>
            <option value="">Select...</option>
            <option value="rc_flat_slab">Flat Concrete Slab (RC)</option>
            <option value="clay_tile">Clay Tile Roof</option>
            <option value="asbestos_sheet">Asbestos Sheet Roof</option>
            <option value="metal_sheet">Metal Sheet Roof</option>
            <option value="other">Other</option>
          </select>
          {errors.roof_type && <p className="mt-1 text-xs text-destructive">{errors.roof_type}</p>}
        </div>

        <div>
          <label className={labelClass}>Ceiling Type <span className="text-red-400">*</span></label>
          <select value={data.ceiling_type} onChange={(e) => field("ceiling_type", e.target.value as ConstructionDetails["ceiling_type"])} className={`${selectClass} ${errors.ceiling_type ? "border-red-500" : ""}`}>
            <option value="">Select...</option>
            <option value="gypsum_mineral_fibre">Gypsum / Mineral Fibre Board</option>
            <option value="timber">Timber Board</option>
            <option value="asbestos_flat">Asbestos Flat Sheet</option>
            <option value="concrete">Exposed Concrete (No Ceiling)</option>
            <option value="other">Other</option>
          </select>
          {errors.ceiling_type && <p className="mt-1 text-xs text-destructive">{errors.ceiling_type}</p>}
        </div>

        <div>
          <label className={labelClass}>Location (Sri Lanka)</label>
          <input
            type="text"
            value={data.location}
            onChange={(e) => field("location", e.target.value)}
            placeholder="e.g. Colombo, Kandy, Galle"
            className={inputClass}
          />
        </div>

        <div>
          <label className={labelClass}>Soil Condition</label>
          <select value={data.soil_condition} onChange={(e) => field("soil_condition", e.target.value as ConstructionDetails["soil_condition"])} className={selectClass}>
            <option value="">Select...</option>
            <option value="normal">Normal</option>
            <option value="expansive">Expansive</option>
            <option value="rocky">Rocky</option>
            <option value="waterlogged">Waterlogged</option>
          </select>
        </div>

        <div>
          <label className={labelClass}>Drainage Type</label>
          <select value={data.drainage_type} onChange={(e) => field("drainage_type", e.target.value as ConstructionDetails["drainage_type"])} className={selectClass}>
            <option value="">Select...</option>
            <option value="mains_sewer">Mains Sewer Connection</option>
            <option value="septic_tank">Septic Tank</option>
            <option value="soakpit">Soakpit</option>
            <option value="none">None / Not Applicable</option>
          </select>
        </div>

        <div>
          <label className={labelClass}>External Works Scope</label>
          <select value={data.external_works_scope} onChange={(e) => field("external_works_scope", e.target.value as ConstructionDetails["external_works_scope"])} className={selectClass}>
            <option value="">Select...</option>
            <option value="none">None</option>
            <option value="minimal">Minimal (Boundary Wall Only)</option>
            <option value="standard">Standard (Wall + Gate + Paths)</option>
            <option value="extensive">Extensive (Full Landscaping &amp; Paving)</option>
          </select>
        </div>
      </div>
    </div>
  );
}
