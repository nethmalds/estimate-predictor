/**
 * Type definitions for the Estimates domain.
 * Mirrors the Pydantic schemas in backend/app/api/schemas/estimate_schemas.py.
 */

export interface EstimateListItem {
  id: string;
  project_name: string | null;
  status: "in_progress" | "completed" | "failed";
  confidence: number | null;
  grand_total: number | null;
  item_count: number | null;
  created_at: string;
  updated_at: string;
  // Enriched fields from the aligned pipeline result
  building_type?: string | null;
  floors?: number | null;
  built_up_area?: string | null;
  floorplan_accepted?: boolean | null;
  external_works_total?: number | null;
}

export interface EstimateDetail {
  id: string;
  project_name: string | null;
  notes: string | null;
  status: "in_progress" | "completed" | "failed";
  project_info: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  confidence: number | null;
  grand_total: number | null;
  item_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface EstimateListResponse {
  estimates: EstimateListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface EstimatePatchRequest {
  project_name?: string | null;
  notes?: string | null;
}

export interface DashboardSummary {
  total_estimates: number;
  estimates_this_month: number;
  average_confidence: number | null;
  total_estimated_value: number;
}

export interface DuplicateEstimateResponse {
  id: string;
  project_name: string | null;
  status: string;
}
