/**
 * Floorplan service — wraps the OCR endpoint that extracts dimensions
 * from uploaded floor plan images.
 */

import { apiClient } from "@/lib/api-client";

export interface FloorplanDimension {
  floor_label: string;
  area_value: number;
  area_unit: "sqft" | "m2";
}

export interface FloorplanOcrResponse {
  dimensions: FloorplanDimension[];
  raw_text?: string;
  confidence?: number;
}

/**
 * Send one or more floor plan image files to the backend OCR endpoint
 * and receive extracted floor area dimensions.
 */
export async function extractFloorplanDimensions(
  files: File[],
  token: string,
  signal?: AbortSignal
): Promise<FloorplanOcrResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return apiClient.postForm<FloorplanOcrResponse>(
    "/api/floorplan-ocr",
    formData,
    token,
    signal
  );
}
