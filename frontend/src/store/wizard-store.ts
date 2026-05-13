/**
 * Zustand wizard store with sessionStorage persistence.
 *
 * Using sessionStorage (not localStorage) so project details are cleared when
 * the browser tab closes — reduces risk of sensitive data lingering on shared
 * machines (C6 from the hardening plan).
 *
 * Persisted state: currentStep, formData
 * Transient state (reset on mount): status, sessionId, estimateId, streamEvents
 *
 * This means if the user refreshes mid-wizard their form data is preserved
 * within the same tab session, but a completed/failed pipeline state is cleared
 * so they can re-submit.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { WizardFormData, WizardStepId } from "@/types/wizard";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type WizardStatus =
  | "idle"
  | "validating"
  | "submitting"
  | "streaming"
  | "completed"
  | "error";

export interface StreamEvent {
  event: "progress" | "completed" | "error" | "info";
  data: Record<string, unknown>;
}

interface WizardState {
  // ── Persisted ──────────────────────────────────────────────────────────────
  currentStep: WizardStepId;
  formData: WizardFormData;

  // ── Transient (not persisted) ──────────────────────────────────────────────
  status: WizardStatus;
  sessionId: string | null;
  estimateId: string | null;
  streamEvents: StreamEvent[];
  validationErrors: Record<string, string>;

  // ── Actions ────────────────────────────────────────────────────────────────
  setStep: (step: WizardStepId) => void;
  nextStep: () => void;
  prevStep: () => void;
  updateFormData: (updates: Partial<WizardFormData>) => void;
  setStatus: (status: WizardStatus) => void;
  setSession: (sessionId: string, estimateId: string) => void;
  appendEvent: (event: StreamEvent) => void;
  setValidationErrors: (errors: Record<string, string>) => void;
  /** Reset transient streaming state (keep form data). */
  resetSession: () => void;
  /** Full reset — clears persisted state too. */
  resetAll: () => void;
}

// ---------------------------------------------------------------------------
// Default form data
// ---------------------------------------------------------------------------

const DEFAULT_FORM_DATA: WizardFormData = {
  projectBasics: {
    building_type: "",
    floor_count: "",
    description: "",
    floorplan_urls: [],
  },
  floorAreas: {
    floor_areas: [{ floor_label: "Ground Floor", area_value: "", area_unit: "sqft" }],
  },
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
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useWizardStore = create<WizardState>()(
  persist(
    (set) => ({
      // Persisted defaults
      currentStep: 1,
      formData: DEFAULT_FORM_DATA,

      // Transient defaults
      status: "idle",
      sessionId: null,
      estimateId: null,
      streamEvents: [],
      validationErrors: {},

      // ── Step navigation ────────────────────────────────────────────────────
      setStep: (step) => set({ currentStep: step }),
      nextStep: () =>
        set((s) => ({
          currentStep: Math.min(s.currentStep + 1, 5) as WizardStepId,
        })),
      prevStep: () =>
        set((s) => ({
          currentStep: Math.max(s.currentStep - 1, 1) as WizardStepId,
        })),

      // ── Form data ──────────────────────────────────────────────────────────
      updateFormData: (updates) => set((s) => ({ formData: { ...s.formData, ...updates } })),

      // ── Status ─────────────────────────────────────────────────────────────
      setStatus: (status) => set({ status }),

      // ── Session / streaming ────────────────────────────────────────────────
      setSession: (sessionId, estimateId) =>
        set({ sessionId, estimateId, status: "streaming", streamEvents: [] }),

      appendEvent: (event) => set((s) => ({ streamEvents: [...s.streamEvents, event] })),

      setValidationErrors: (errors) => set({ validationErrors: errors }),

      // ── Resets ─────────────────────────────────────────────────────────────
      resetSession: () =>
        set({
          status: "idle",
          sessionId: null,
          estimateId: null,
          streamEvents: [],
          validationErrors: {},
        }),

      resetAll: () =>
        set({
          currentStep: 1,
          formData: DEFAULT_FORM_DATA,
          status: "idle",
          sessionId: null,
          estimateId: null,
          streamEvents: [],
          validationErrors: {},
        }),
    }),
    {
      name: "wizard-store",
      // sessionStorage clears on tab close — project details don't persist on shared machines
      storage: createJSONStorage(() => sessionStorage),
      // Only persist the form data and current step, not transient pipeline state
      partialize: (state) => ({
        currentStep: state.currentStep,
        formData: state.formData,
      }),
    }
  )
);
