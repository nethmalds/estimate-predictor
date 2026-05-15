/**
 * Unit tests for useWizardSubmit hook.
 *
 * submitWizardForm and openFormEstimateStream are mocked so no real network
 * calls occur. A programmable fake EventSource lets tests dispatch progress,
 * completed, and error events synchronously.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWizardSubmit } from "@/hooks/use-wizard";
import { useWizardStore } from "@/store/wizard-store";

// ── Mock estimates service ────────────────────────────────────────────────────

vi.mock("@/services/estimates.service", () => ({
  submitWizardForm: vi.fn(),
  openFormEstimateStream: vi.fn(),
}));

import { submitWizardForm, openFormEstimateStream } from "@/services/estimates.service";

// ── Fake EventSource factory ──────────────────────────────────────────────────

class FakeEventSource {
  static CLOSED = 2;
  readyState = 1;
  onerror: ((e: Event) => void) | null = null;
  private listeners: Record<string, ((e: MessageEvent) => void)[]> = {};

  addEventListener(type: string, listener: (e: MessageEvent) => void) {
    this.listeners[type] = this.listeners[type] ?? [];
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: (e: MessageEvent) => void) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((l) => l !== listener);
  }

  dispatch(type: string, data: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent;
    (this.listeners[type] ?? []).forEach((l) => l(event));
  }

  close() {
    this.readyState = FakeEventSource.CLOSED;
  }
}

let fakeEs: FakeEventSource;

beforeEach(() => {
  fakeEs = new FakeEventSource();
  vi.mocked(openFormEstimateStream).mockReturnValue(fakeEs as unknown as EventSource);
  vi.mocked(submitWizardForm).mockResolvedValue({ session_id: "sess-1", status: "processing", estimate_id: "est-1" });

  // Reset wizard store
  useWizardStore.getState().resetAll();
});

afterEach(() => {
  vi.clearAllMocks();
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("useWizardSubmit", () => {
  it("starts with isSubmitting false", () => {
    const { result } = renderHook(() => useWizardSubmit({}));
    expect(result.current.isSubmitting).toBe(false);
  });

  it("calls submitWizardForm with the given payload", async () => {
    const { result } = renderHook(() => useWizardSubmit({ token: "tok-123" }));

    await act(async () => {
      await result.current.submit({ building_type: "residential" });
    });

    expect(submitWizardForm).toHaveBeenCalledWith({ building_type: "residential" }, "tok-123");
  });

  it("sets store session after successful submit", async () => {
    const { result } = renderHook(() => useWizardSubmit({ token: "tok" }));

    await act(async () => {
      await result.current.submit({});
    });

    const state = useWizardStore.getState();
    expect(state.sessionId).toBe("sess-1");
    expect(state.estimateId).toBe("est-1");
  });

  it("opens an SSE stream after submit", async () => {
    const { result } = renderHook(() => useWizardSubmit({}));

    await act(async () => {
      await result.current.submit({});
    });

    expect(openFormEstimateStream).toHaveBeenCalledWith("sess-1");
  });

  it("appends progress events to the store", async () => {
    const { result } = renderHook(() => useWizardSubmit({}));

    await act(async () => {
      await result.current.submit({});
      fakeEs.dispatch("progress", { stage: "boq_generation", pct: 30 });
    });

    const events = useWizardStore.getState().streamEvents;
    expect(events.some((e) => e.event === "progress")).toBe(true);
  });

  it("calls onComplete callback and sets status to completed on completed event", async () => {
    const onComplete = vi.fn();
    const { result } = renderHook(() => useWizardSubmit({ onComplete }));

    await act(async () => {
      await result.current.submit({});
      fakeEs.dispatch("completed", { boq_items: [], costs: {} });
    });

    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ boq_items: [], costs: {} }),
      "est-1"
    );
    expect(useWizardStore.getState().status).toBe("completed");
  });

  it("calls onError callback and sets status to error on error event", async () => {
    const onError = vi.fn();
    const { result } = renderHook(() => useWizardSubmit({ onError }));

    await act(async () => {
      await result.current.submit({});
      fakeEs.dispatch("error", { message: "Pipeline failed" });
    });

    expect(onError).toHaveBeenCalledWith("Pipeline failed");
    expect(useWizardStore.getState().status).toBe("error");
  });

  it("sets error status when submitWizardForm throws", async () => {
    vi.mocked(submitWizardForm).mockRejectedValue(new Error("Network error"));
    const onError = vi.fn();
    const { result } = renderHook(() => useWizardSubmit({ onError }));

    await act(async () => {
      await result.current.submit({});
    });

    expect(onError).toHaveBeenCalledWith("Network error");
    expect(useWizardStore.getState().status).toBe("error");
  });

  it("cancel closes the stream and resets session state", async () => {
    const { result } = renderHook(() => useWizardSubmit({}));

    await act(async () => {
      await result.current.submit({});
    });

    act(() => {
      result.current.cancel();
    });

    expect(fakeEs.readyState).toBe(FakeEventSource.CLOSED);
    expect(useWizardStore.getState().sessionId).toBeNull();
  });

  it("does not submit again if already submitting", async () => {
    // Make submit hang so isSubmitting stays true
    vi.mocked(submitWizardForm).mockImplementation(() => new Promise(() => {}));
    const { result } = renderHook(() => useWizardSubmit({}));

    act(() => {
      result.current.submit({});
    });

    await act(async () => {
      await result.current.submit({});
    });

    // Should have only been called once
    expect(submitWizardForm).toHaveBeenCalledTimes(1);
  });
});
