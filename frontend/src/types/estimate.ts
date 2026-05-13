/**
 * Type definitions for the Estimates domain.
 * Mirrors the Pydantic schemas in backend/app/api/schemas/estimate_schemas.py.
 */

export type EstimateStatus = "in_progress" | "completed" | "failed" | "cancelled";

export interface EstimateListItem {
  id: string;
  project_name: string | null;
  status: EstimateStatus;
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
  // Lifecycle fields
  progress?: Record<string, unknown> | null;
  error_message?: string | null;
  cancelled_at?: string | null;
  regenerated_from_estimate_id?: string | null;
}

export interface EstimateDetail {
  id: string;
  project_name: string | null;
  notes: string | null;
  status: EstimateStatus;
  project_info: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  confidence: number | null;
  grand_total: number | null;
  item_count: number | null;
  created_at: string;
  updated_at: string;
  // Lifecycle fields
  progress?: Record<string, unknown> | null;
  error_message?: string | null;
  cancelled_at?: string | null;
  regenerated_from_estimate_id?: string | null;
  wizard_payload?: Record<string, unknown> | null;
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

export interface CancelEstimateResponse {
  id: string;
  status: EstimateStatus;
  cancelled_at: string | null;
}

export interface RegenerateEstimateResponse {
  id: string;
  status: EstimateStatus;
  project_name: string | null;
  created_at: string;
  regenerated_from_estimate_id: string | null;
}
