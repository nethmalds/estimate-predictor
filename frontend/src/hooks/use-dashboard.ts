/**
 * Dashboard hook — fetches and caches the dashboard summary card data.
 *
 * Usage:
 *   const { data: summary, isLoading } = useDashboardSummary(accessToken);
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { getDashboardSummary, estimateKeys } from "@/services/estimates.service";

/**
 * Fetch dashboard summary (total estimates, this month, avg confidence, total value).
 */
export function useDashboardSummary(token: string | undefined) {
  return useQuery({
    queryKey: estimateKeys.dashboard(),
    queryFn: ({ signal }) => getDashboardSummary(token!, signal),
    enabled: !!token,
  });
}
