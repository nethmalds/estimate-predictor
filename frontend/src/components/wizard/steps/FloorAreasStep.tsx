"use client";

import { FloorAreas, FloorAreaRow, AreaUnit } from "@/types/wizard";
import { useEffect } from "react";

interface Props {
  data: FloorAreas;
  floorCount: number;
  onChange: (data: FloorAreas) => void;
  errors: Record<string, string>;
}

function getFloorLabel(index: number, total: number): string {
  if (total === 1) return "Ground Floor";
  if (index === 0) return "Ground Floor";
  const ordinals = [
    "First",
    "Second",
    "Third",
    "Fourth",
    "Fifth",
    "Sixth",
    "Seventh",
    "Eighth",
    "Ninth",
    "Tenth",
  ];
  return `${ordinals[index - 1] || index + "th"} Floor`;
}

export function FloorAreasStep({ data, floorCount, onChange, errors }: Props) {
  // Sync rows when floorCount changes
  useEffect(() => {
    const currentLen = data.floor_areas.length;
    if (currentLen === floorCount) return;
    const newRows: FloorAreaRow[] = Array.from({ length: floorCount }, (_, i) => ({
      floor_label: getFloorLabel(i, floorCount),
      area_value: data.floor_areas[i]?.area_value ?? "",
      area_unit: data.floor_areas[i]?.area_unit ?? "sqft",
    }));
    onChange({ floor_areas: newRows });
  }, [floorCount]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateRow = (i: number, patch: Partial<FloorAreaRow>) => {
    const newRows = data.floor_areas.map((row, idx) => (idx === i ? { ...row, ...patch } : row));
    onChange({ floor_areas: newRows });
  };

  // Compute live total
  const totalSqft = data.floor_areas.reduce((sum, row) => {
    const v =
      typeof row.area_value === "number" ? row.area_value : parseFloat(String(row.area_value)) || 0;
    return sum + (row.area_unit === "m2" ? v / 0.0929 : v);
  }, 0);
  const totalM2 = totalSqft * 0.0929;

  return (
    <div className="space-y-6">
      <p className="text-muted-foreground text-sm">
        Enter the built-up area for each floor of the building.
      </p>

      <div className="space-y-3">
        {data.floor_areas.map((row, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-foreground w-36 shrink-0 text-sm">
              {row.floor_label} <span className="text-destructive">*</span>
            </span>
            <input
              type="number"
              min={1}
              value={row.area_value}
              onChange={(e) =>
                updateRow(i, {
                  area_value: e.target.value === "" ? "" : parseFloat(e.target.value),
                })
              }
              placeholder="Area"
              className={`bg-background text-foreground focus:ring-ring w-32 rounded-lg border px-3 py-2 focus:ring-2 focus:outline-none ${
                errors[`floor_areas[${i}]`] ? "border-destructive" : "border-input"
              }`}
            />
            <select
              value={row.area_unit}
              onChange={(e) => updateRow(i, { area_unit: e.target.value as AreaUnit })}
              className="bg-background border-input text-foreground focus:ring-ring rounded-lg border px-2 py-2 focus:ring-2 focus:outline-none"
            >
              <option value="sqft">sq ft</option>
              <option value="m2">m²</option>
            </select>
            {errors[`floor_areas[${i}]`] && (
              <span className="text-destructive text-xs">{errors[`floor_areas[${i}]`]}</span>
            )}
          </div>
        ))}
      </div>

      {/* Live total */}
      {totalSqft > 0 && (
        <div className="bg-muted/50 border-border rounded-lg border p-3">
          <p className="text-foreground text-sm">
            Total Built-Up Area: <span className="font-semibold">{totalSqft.toFixed(0)} sq ft</span>
            <span className="text-muted-foreground ml-2">({totalM2.toFixed(1)} m²)</span>
          </p>
        </div>
      )}
      {errors.floor_areas && <p className="text-destructive text-xs">{errors.floor_areas}</p>}
    </div>
  );
}
