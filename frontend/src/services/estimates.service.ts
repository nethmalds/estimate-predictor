/**
 * Estimates service — the single service file for all estimate-related
 * and wizard-flow backend endpoints.
 *
 * Covers:
 *  - Wizard form validation, submission, and SSE streaming
 *  - Estimate CRUD (list, get, patch, delete, duplicate)
 *  - Dashboard summary
 */

import { apiClient, buildBackendUrl } from "@/lib/api-client";
import type {
  CancelEstimateResponse,
  DashboardSummary,
  DuplicateEstimateResponse,
  EstimateDetail,
  EstimateListResponse,
  EstimatePatchRequest,
  RegenerateEstimateResponse,
} from "@/types/estimate";

// ---------------------------------------------------------------------------
// Wizard response types
// ---------------------------------------------------------------------------

export type WizardSubmitResponse = {
  session_id: string;
  status: string;
  estimate_id?: string;
};

export type WizardValidateResponse = {
  valid: boolean;
  errors: Record<string, string>;
};

// ---------------------------------------------------------------------------
// Query key factory — used by React Query hooks for cache management
// ---------------------------------------------------------------------------

export const estimateKeys = {
  all: ["estimates"] as const,
  lists: () => [...estimateKeys.all, "list"] as const,
  list: (page: number, pageSize: number) => [...estimateKeys.lists(), { page, pageSize }] as const,
  details: () => [...estimateKeys.all, "detail"] as const,
  detail: (id: string) => [...estimateKeys.details(), id] as const,
  dashboard: () => ["dashboard", "summary"] as const,
};

// ---------------------------------------------------------------------------
// Wizard flow
// ---------------------------------------------------------------------------

/**
 * Validate a wizard form payload against the backend rules.
 * Returns field-level errors if invalid.
 */
export async function validateWizardForm(
  payload: Record<string, unknown>,
  signal?: AbortSignal
): Promise<WizardValidateResponse> {
  return apiClient.post<WizardValidateResponse>(
    "/api/estimate-project/form/validate",
    { payload },
    undefined,
    signal
  );
}

/**
 * Submit a completed wizard form and start the estimation pipeline.
 * Returns the session_id for SSE streaming and the estimate_id for navigation.
 */
export async function submitWizardForm(
  payload: Record<string, unknown>,
  token?: string,
  signal?: AbortSignal
): Promise<WizardSubmitResponse> {
  return apiClient.post<WizardSubmitResponse>(
    "/api/estimate-project/form/submit",
    payload,
    token,
    signal
  );
}

/**
 * Open an SSE EventSource for the given estimation session.
 * The caller is responsible for closing the EventSource when done.
 */
export function openFormEstimateStream(sessionId: string): EventSource {
  return new EventSource(buildBackendUrl(`/api/estimate-project/form/stream/${sessionId}`));
}

// ---------------------------------------------------------------------------
// Estimate CRUD
// ---------------------------------------------------------------------------

/**
 * Fetch a paginated list of estimates for the authenticated user.
 */
export async function listEstimates(
  token: string,
  page = 1,
  pageSize = 20,
  signal?: AbortSignal
): Promise<EstimateListResponse> {
  return apiClient.get<EstimateListResponse>(
    `/api/estimates?page=${page}&page_size=${pageSize}`,
    token,
    signal
  );
}

/**
 * Fetch a single estimate by ID.
 */
export async function getEstimate(
  id: string,
  token: string,
  signal?: AbortSignal
): Promise<EstimateDetail> {
  return apiClient.get<EstimateDetail>(`/api/estimates/${id}`, token, signal);
}

/**
 * Update project_name and/or notes on an estimate.
 */
export async function patchEstimate(
  id: string,
  body: EstimatePatchRequest,
  token: string
): Promise<{ id: string; project_name: string | null; notes: string | null }> {
  return apiClient.patch(`/api/estimates/${id}`, body, token);
}

/**
 * Soft-delete an estimate.
 */
export async function deleteEstimate(id: string, token: string): Promise<{ message: string }> {
  return apiClient.delete(`/api/estimates/${id}`, token);
}

/**
 * Duplicate an estimate (clone project_info to a new estimate record).
 */
export async function duplicateEstimate(
  id: string,
  token: string
): Promise<DuplicateEstimateResponse> {
  return apiClient.post(`/api/estimates/${id}/duplicate`, undefined, token);
}

/**
 * Cancel an in-progress estimation run.
 */
export async function cancelEstimate(id: string, token: string): Promise<CancelEstimateResponse> {
  return apiClient.post(`/api/estimates/${id}/cancel`, undefined, token);
}

/**
 * Regenerate a new estimate from the original wizard payload.
 * Returns the new estimate's metadata.
 */
export async function regenerateEstimate(
  id: string,
  token: string
): Promise<RegenerateEstimateResponse> {
  return apiClient.post(`/api/estimates/${id}/regenerate`, undefined, token);
}

/**
 * Fetch dashboard summary cards (totals, confidence, monthly count).
 */
export async function getDashboardSummary(
  token: string,
  signal?: AbortSignal
): Promise<DashboardSummary> {
  return apiClient.get<DashboardSummary>("/api/dashboard/summary", token, signal);
}
