/**
 * Estimates hooks — React Query hooks for estimate list, detail, and mutations.
 *
 * Usage (client components):
 *   const { data, isLoading } = useEstimateList(accessToken, 1);
 *   const { data } = useEstimateDetail(accessToken, estimateId);
 *   patchMutation.mutate({ id, body });
 */

"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listEstimates,
  getEstimate,
  patchEstimate,
  deleteEstimate,
  duplicateEstimate,
  estimateKeys,
} from "@/services/estimates.service";
import type { EstimatePatchRequest } from "@/types/estimate";

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

/**
 * Fetch a paginated list of estimates for the authenticated user.
 */
export function useEstimateList(
  token: string | undefined,
  page = 1,
  pageSize = 20
) {
  return useQuery({
    queryKey: estimateKeys.list(page, pageSize),
    queryFn: ({ signal }) => listEstimates(token!, page, pageSize, signal),
    enabled: !!token,
  });
}

/**
 * Fetch a single estimate by ID.
 */
export function useEstimateDetail(
  token: string | undefined,
  estimateId: string | undefined
) {
  return useQuery({
    queryKey: estimateKeys.detail(estimateId!),
    queryFn: ({ signal }) => getEstimate(estimateId!, token!, signal),
    enabled: !!token && !!estimateId,
  });
}

// ---------------------------------------------------------------------------
// Mutation hooks
// ---------------------------------------------------------------------------

/**
 * Update project_name / notes on an estimate.
 * Automatically invalidates the list and detail caches on success.
 */
export function usePatchEstimate(token: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: EstimatePatchRequest }) =>
      patchEstimate(id, body, token!),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: estimateKeys.lists() });
      queryClient.invalidateQueries({ queryKey: estimateKeys.detail(id) });
    },
  });
}

/**
 * Soft-delete an estimate.
 * Removes the item from all list caches on success.
 */
export function useDeleteEstimate(token: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteEstimate(id, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: estimateKeys.lists() });
    },
  });
}

/**
 * Duplicate an estimate.
 * Invalidates the list cache so the new estimate appears.
 */
export function useDuplicateEstimate(token: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => duplicateEstimate(id, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: estimateKeys.lists() });
    },
  });
}
