"use client";

import { BuildingProgram, BuildingType } from "@/types/wizard";

interface Props {
  data: BuildingProgram;
  buildingType: BuildingType | "";
  onChange: (data: BuildingProgram) => void;
  errors: Record<string, string>;
}

const inputClass = "w-full bg-zinc-800 border border-zinc-700 text-zinc-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500";
const selectClass = inputClass;
const labelClass = "block text-sm font-medium text-zinc-300 mb-2";

export function BuildingProgramStep({ data, buildingType, onChange, errors }: Props) {
  if (buildingType === "residential") {
    return (
      <div className="space-y-6">
        <p className="text-sm text-zinc-400">Provide room counts for the residential building.</p>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className={labelClass}>Bedrooms <span className="text-red-400">*</span></label>
            <input
              type="number" min={1} max={50}
              value={data.bedrooms ?? ""}
              onChange={(e) => onChange({ ...data, bedrooms: e.target.value === "" ? "" : parseInt(e.target.value) })}
              placeholder="e.g. 3"
              className={`${inputClass} ${errors.bedrooms ? "border-red-500" : ""}`}
            />
            {errors.bedrooms && <p className="mt-1 text-xs text-red-400">{errors.bedrooms}</p>}
          </div>
          <div>
            <label className={labelClass}>Bathrooms <span className="text-red-400">*</span></label>
            <input
              type="number" min={1} max={50}
              value={data.bathrooms ?? ""}
              onChange={(e) => onChange({ ...data, bathrooms: e.target.value === "" ? "" : parseInt(e.target.value) })}
              placeholder="e.g. 2"
              className={`${inputClass} ${errors.bathrooms ? "border-red-500" : ""}`}
            />
            {errors.bathrooms && <p className="mt-1 text-xs text-red-400">{errors.bathrooms}</p>}
          </div>
        </div>
      </div>
    );
  }

  if (buildingType === "commercial") {
    return (
      <div className="space-y-6">
        <p className="text-sm text-zinc-400">Describe the commercial building program.</p>
        <div>
          <label className={labelClass}>Primary Use Type</label>
          <select
            value={data.primary_use_type ?? ""}
            onChange={(e) => onChange({ ...data, primary_use_type: e.target.value })}
            className={selectClass}
          >
            <option value="">Select primary use...</option>
            <option value="Office">Office</option>
            <option value="Retail">Retail</option>
            <option value="Hotel">Hotel</option>
            <option value="Restaurant">Restaurant</option>
            <option value="Educational">Educational</option>
            <option value="Healthcare">Healthcare</option>
            <option value="Other">Other</option>
          </select>
        </div>

        <div>
          <label className={labelClass}>Number of Washrooms</label>
          <input
            type="number"
            min={1}
            value={data.washroom_count ?? ""}
            onChange={(e) => onChange({ ...data, washroom_count: e.target.value === "" ? "" : parseInt(e.target.value) })}
            placeholder="e.g. 4"
            className={`${inputClass} ${errors.washroom_count ? "border-red-500" : ""}`}
          />
          {errors.washroom_count && (
            <p className="text-xs text-red-400 mt-1">{errors.washroom_count}</p>
          )}
        </div>
      </div>
    );
  }

  if (buildingType === "industrial") {
    return (
      <div className="space-y-6">
        <p className="text-sm text-zinc-400">Describe the industrial facility and its specific requirements.</p>
        
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className={labelClass}>Facility Type</label>
            <select
              value={data.facility_type ?? ""}
              onChange={(e) => onChange({ ...data, facility_type: e.target.value })}
              className={selectClass}
            >
              <option value="">Select facility type...</option>
              <option value="Factory / Manufacturing">Factory / Manufacturing</option>
              <option value="Warehouse / Storage">Warehouse / Storage</option>
              <option value="Cold Storage">Cold Storage</option>
              <option value="Logistics Center">Logistics Center</option>
              <option value="Workshop">Workshop</option>
              <option value="Other">Other</option>
            </select>
          </div>

          <div>
            <label className={labelClass}>Heavy Machinery Load</label>
            <select
              value={data.heavy_machinery_load ?? ""}
              onChange={(e) => onChange({ ...data, heavy_machinery_load: e.target.value as "yes" | "no" | "" })}
              className={selectClass}
            >
              <option value="">Select...</option>
              <option value="yes">Yes (Requires reinforced flooring)</option>
              <option value="no">No (Standard loading)</option>
            </select>
          </div>

          <div>
            <label className={labelClass}>Hazardous Materials</label>
            <select
              value={data.hazardous_materials ?? ""}
              onChange={(e) => onChange({ ...data, hazardous_materials: e.target.value as "yes" | "no" | "" })}
              className={selectClass}
            >
              <option value="">Select...</option>
              <option value="yes">Yes (Requires special containment/fire safety)</option>
              <option value="no">No</option>
            </select>
          </div>

          <div>
            <label className={labelClass}>Specialized Ventilation</label>
            <select
              value={data.specialized_ventilation ?? ""}
              onChange={(e) => onChange({ ...data, specialized_ventilation: e.target.value as "yes" | "no" | "" })}
              className={selectClass}
            >
              <option value="">Select...</option>
              <option value="yes">Yes (Fume hoods, dust extraction, etc.)</option>
              <option value="no">No (Standard HVAC)</option>
            </select>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="text-zinc-400 text-sm">Please complete Step 1 first to select a building type.</div>
  );
}
