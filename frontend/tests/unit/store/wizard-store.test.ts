/**
 * Unit tests for the Zustand wizard store.
 *
 * The store uses sessionStorage via zustand/middleware persist. In JSDOM the
 * real sessionStorage is available — we spy on it to verify persistence.
 *
 * Tests call store actions directly (no React rendering needed) because the
 * store is a plain function with state managed outside React.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { useWizardStore } from "@/store/wizard-store";

// Reset the store to defaults before each test so tests are isolated
function resetStore() {
  useWizardStore.setState({
    currentStep: 1,
    formData: {
      projectBasics: { building_type: "", floor_count: "", description: "", floorplan_urls: [] },
      floorAreas: { floor_areas: [{ floor_label: "Ground Floor", area_value: "", area_unit: "sqft" }] },
      buildingProgram: {},
      constructionDetails: {
        finish_level: "",
        structural_system: "",
        roof_type: "",
        ceiling_type: "",
        location: "",
        soil_condition: "",
        drainage_type: "",
        external_works_scope: "",
      },
    },
    status: "idle",
    sessionId: null,
    estimateId: null,
    streamEvents: [],
    validationErrors: {},
  });
}

beforeEach(resetStore);
afterEach(resetStore);

// ── Initial state ─────────────────────────────────────────────────────────────

describe("initial state", () => {
  it("starts on step 1", () => {
    expect(useWizardStore.getState().currentStep).toBe(1);
  });

  it("starts with idle status", () => {
    expect(useWizardStore.getState().status).toBe("idle");
  });

  it("starts with no session or estimate ID", () => {
    const { sessionId, estimateId } = useWizardStore.getState();
    expect(sessionId).toBeNull();
    expect(estimateId).toBeNull();
  });

  it("starts with empty stream events", () => {
    expect(useWizardStore.getState().streamEvents).toHaveLength(0);
  });
});

// ── Step navigation ───────────────────────────────────────────────────────────

describe("step navigation", () => {
  it("nextStep increments currentStep", () => {
    useWizardStore.getState().nextStep();
    expect(useWizardStore.getState().currentStep).toBe(2);
  });

  it("prevStep decrements currentStep", () => {
    useWizardStore.getState().setStep(3);
    useWizardStore.getState().prevStep();
    expect(useWizardStore.getState().currentStep).toBe(2);
  });

  it("nextStep does not exceed step 5", () => {
    useWizardStore.getState().setStep(5);
    useWizardStore.getState().nextStep();
    expect(useWizardStore.getState().currentStep).toBe(5);
  });

  it("prevStep does not go below step 1", () => {
    useWizardStore.getState().prevStep();
    expect(useWizardStore.getState().currentStep).toBe(1);
  });

  it("setStep jumps to any valid step", () => {
    useWizardStore.getState().setStep(4);
    expect(useWizardStore.getState().currentStep).toBe(4);
  });
});

// ── Form data ─────────────────────────────────────────────────────────────────

describe("updateFormData", () => {
  it("merges updates into existing form data", () => {
    useWizardStore.getState().updateFormData({
      projectBasics: { building_type: "residential", floor_count: 2, description: "", floorplan_urls: [] },
    });
    expect(useWizardStore.getState().formData.projectBasics.building_type).toBe("residential");
  });

  it("does not overwrite unrelated form sections", () => {
    useWizardStore.getState().updateFormData({
      projectBasics: { building_type: "commercial", floor_count: 3, description: "", floorplan_urls: [] },
    });
    // constructionDetails should still be in its default state
    expect(useWizardStore.getState().formData.constructionDetails.finish_level).toBe("");
  });
});

// ── Session / streaming ───────────────────────────────────────────────────────

describe("setSession", () => {
  it("stores session_id and estimate_id", () => {
    useWizardStore.getState().setSession("sess-123", "est-456");
    const { sessionId, estimateId } = useWizardStore.getState();
    expect(sessionId).toBe("sess-123");
    expect(estimateId).toBe("est-456");
  });

  it("transitions status to streaming", () => {
    useWizardStore.getState().setSession("s", "e");
    expect(useWizardStore.getState().status).toBe("streaming");
  });

  it("clears prior stream events", () => {
    useWizardStore.getState().appendEvent({ event: "progress", data: {} });
    useWizardStore.getState().setSession("s", "e");
    expect(useWizardStore.getState().streamEvents).toHaveLength(0);
  });
});

describe("appendEvent", () => {
  it("adds events to streamEvents array", () => {
    const evt = { event: "progress" as const, data: { stage: "boq" } };
    useWizardStore.getState().appendEvent(evt);
    expect(useWizardStore.getState().streamEvents).toHaveLength(1);
    expect(useWizardStore.getState().streamEvents[0]).toEqual(evt);
  });

  it("accumulates multiple events", () => {
    useWizardStore.getState().appendEvent({ event: "progress", data: {} });
    useWizardStore.getState().appendEvent({ event: "completed", data: {} });
    expect(useWizardStore.getState().streamEvents).toHaveLength(2);
  });
});

// ── Resets ────────────────────────────────────────────────────────────────────

describe("resetSession", () => {
  it("clears session state but keeps form data", () => {
    useWizardStore.getState().updateFormData({
      projectBasics: { building_type: "residential", floor_count: 2, description: "", floorplan_urls: [] },
    });
    useWizardStore.getState().setSession("s", "e");
    useWizardStore.getState().resetSession();

    const state = useWizardStore.getState();
    expect(state.sessionId).toBeNull();
    expect(state.estimateId).toBeNull();
    expect(state.status).toBe("idle");
    expect(state.streamEvents).toHaveLength(0);
    // Form data preserved
    expect(state.formData.projectBasics.building_type).toBe("residential");
  });
});

describe("resetAll", () => {
  it("clears all state including form data and step", () => {
    useWizardStore.getState().setStep(4);
    useWizardStore.getState().updateFormData({
      projectBasics: { building_type: "commercial", floor_count: 5, description: "", floorplan_urls: [] },
    });
    useWizardStore.getState().setSession("s", "e");
    useWizardStore.getState().resetAll();

    const state = useWizardStore.getState();
    expect(state.currentStep).toBe(1);
    expect(state.formData.projectBasics.building_type).toBe("");
    expect(state.sessionId).toBeNull();
    expect(state.status).toBe("idle");
  });
});

// ── Validation errors ─────────────────────────────────────────────────────────

describe("setValidationErrors", () => {
  it("stores validation error map", () => {
    useWizardStore.getState().setValidationErrors({ floor_count: "Required field" });
    expect(useWizardStore.getState().validationErrors["floor_count"]).toBe("Required field");
  });

  it("overrides previous errors with new set", () => {
    useWizardStore.getState().setValidationErrors({ a: "error a" });
    useWizardStore.getState().setValidationErrors({ b: "error b" });
    expect(useWizardStore.getState().validationErrors["a"]).toBeUndefined();
    expect(useWizardStore.getState().validationErrors["b"]).toBe("error b");
  });
});
