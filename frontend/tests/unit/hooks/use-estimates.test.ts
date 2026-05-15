/**
 * Unit tests for React Query estimate hooks.
 *
 * All estimates.service calls are mocked. Hooks are rendered inside a
 * QueryClientProvider wrapper so React Query state is isolated per test.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  useEstimateList,
  useEstimateDetail,
  usePatchEstimate,
  useDeleteEstimate,
} from "@/hooks/use-estimates";

// ── Mock estimates service ────────────────────────────────────────────────────

vi.mock("@/services/estimates.service", () => ({
  listEstimates: vi.fn(),
  getEstimate: vi.fn(),
  patchEstimate: vi.fn(),
  deleteEstimate: vi.fn(),
  duplicateEstimate: vi.fn(),
  cancelEstimate: vi.fn(),
  regenerateEstimate: vi.fn(),
  estimateKeys: {
    all: ["estimates"],
    lists: () => ["estimates", "list"],
    list: (page: number, pageSize: number) => ["estimates", "list", { page, pageSize }],
    details: () => ["estimates", "detail"],
    detail: (id: string) => ["estimates", "detail", id],
    dashboard: () => ["dashboard", "summary"],
  },
}));

import { listEstimates, getEstimate, patchEstimate, deleteEstimate } from "@/services/estimates.service";

// ── Test wrapper ──────────────────────────────────────────────────────────────

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ── useEstimateList ───────────────────────────────────────────────────────────

describe("useEstimateList", () => {
  it("does not fetch when token is absent", () => {
    renderHook(() => useEstimateList(undefined), { wrapper: createWrapper() });
    expect(listEstimates).not.toHaveBeenCalled();
  });

  it("fetches the list when token is provided", async () => {
    const mockData = { estimates: [], total: 0, page: 1, page_size: 20 };
    vi.mocked(listEstimates).mockResolvedValue(mockData);

    const { result } = renderHook(() => useEstimateList("tok"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
    expect(listEstimates).toHaveBeenCalledWith("tok", 1, 20, expect.anything());
  });

  it("passes page and pageSize to service", async () => {
    vi.mocked(listEstimates).mockResolvedValue({ estimates: [], total: 0, page: 2, page_size: 10 });

    const { result } = renderHook(() => useEstimateList("tok", 2, 10), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(listEstimates).toHaveBeenCalledWith("tok", 2, 10, expect.anything());
  });

  it("surfaces error from service", async () => {
    vi.mocked(listEstimates).mockRejectedValue(new Error("Unauthorized"));

    const { result } = renderHook(() => useEstimateList("bad-tok"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect((result.current.error as Error).message).toBe("Unauthorized");
  });
});

// ── useEstimateDetail ─────────────────────────────────────────────────────────

describe("useEstimateDetail", () => {
  it("does not fetch when token or estimateId is absent", () => {
    renderHook(() => useEstimateDetail(undefined, "est-1"), { wrapper: createWrapper() });
    expect(getEstimate).not.toHaveBeenCalled();
  });

  it("fetches detail when both token and id are present", async () => {
    const mockDetail = { id: "est-1", status: "completed", project_name: "Test" };
    vi.mocked(getEstimate).mockResolvedValue(mockDetail as any);

    const { result } = renderHook(() => useEstimateDetail("tok", "est-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe("est-1");
  });
});

// ── usePatchEstimate ──────────────────────────────────────────────────────────

describe("usePatchEstimate", () => {
  it("calls patchEstimate service on mutate", async () => {
    vi.mocked(patchEstimate).mockResolvedValue({ id: "est-1", project_name: "Renamed", notes: null });

    const { result } = renderHook(() => usePatchEstimate("tok"), { wrapper: createWrapper() });

    await act(async () => {
      result.current.mutate({ id: "est-1", body: { project_name: "Renamed" } });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(patchEstimate).toHaveBeenCalledWith("est-1", { project_name: "Renamed" }, "tok");
  });

  it("surfaces mutation error", async () => {
    vi.mocked(patchEstimate).mockRejectedValue(new Error("Forbidden"));

    const { result } = renderHook(() => usePatchEstimate("tok"), { wrapper: createWrapper() });

    await act(async () => {
      result.current.mutate({ id: "est-1", body: { project_name: "X" } });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

// ── useDeleteEstimate ─────────────────────────────────────────────────────────

describe("useDeleteEstimate", () => {
  it("calls deleteEstimate service on mutate", async () => {
    vi.mocked(deleteEstimate).mockResolvedValue({ message: "Estimate deleted." });

    const { result } = renderHook(() => useDeleteEstimate("tok"), { wrapper: createWrapper() });

    await act(async () => {
      result.current.mutate("est-1");
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(deleteEstimate).toHaveBeenCalledWith("est-1", "tok");
  });
});
