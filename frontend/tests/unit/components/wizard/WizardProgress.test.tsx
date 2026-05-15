/**
 * Unit tests for WizardProgress component.
 *
 * Verifies ARIA semantics, step state classes, and progress indicator behaviour.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WizardProgress } from "@/components/wizard/WizardProgress";
import type { WizardStep } from "@/types/wizard";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const STEPS: WizardStep[] = [
  { id: 1, title: "Project Basics", description: "Building type and floor count" },
  { id: 2, title: "Floor Areas", description: "Area per floor" },
  { id: 3, title: "Building Program", description: "Rooms and spaces" },
  { id: 4, title: "Construction Details", description: "Materials and finishes" },
  { id: 5, title: "Review & Submit", description: "Confirm and estimate" },
];

function renderProgress(currentStep: number) {
  return render(
    <WizardProgress steps={STEPS} currentStep={currentStep as 1 | 2 | 3 | 4 | 5} />
  );
}

// ── ARIA ──────────────────────────────────────────────────────────────────────

describe("WizardProgress ARIA", () => {
  it("renders a progressbar role", () => {
    renderProgress(1);
    expect(screen.getByRole("progressbar")).toBeDefined();
  });

  it("sets aria-valuenow to the current step", () => {
    renderProgress(3);
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBe("3");
  });

  it("sets aria-valuemin to 1 and aria-valuemax to total steps", () => {
    renderProgress(2);
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuemin")).toBe("1");
    expect(bar.getAttribute("aria-valuemax")).toBe("5");
  });

  it("includes the current step title in aria-label", () => {
    renderProgress(2);
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-label")).toContain("Floor Areas");
  });

  it("marks the current step circle with aria-current=step", () => {
    renderProgress(3);
    const currentCircles = screen
      .getAllByRole("generic")
      .filter((el) => el.getAttribute("aria-current") === "step");
    expect(currentCircles).toHaveLength(1);
  });
});

// ── Step state rendering ──────────────────────────────────────────────────────

describe("WizardProgress step states", () => {
  it("renders all step titles", () => {
    renderProgress(1);
    STEPS.forEach((step) => {
      expect(screen.getByText(step.title)).toBeDefined();
    });
  });

  it("renders a screen-reader completed label for past steps", () => {
    renderProgress(3);
    // Steps 1 and 2 are completed; they should have sr-only text
    expect(screen.getByText("Project Basics — completed")).toBeDefined();
    expect(screen.getByText("Floor Areas — completed")).toBeDefined();
  });

  it("does not show completed label for the current step", () => {
    renderProgress(2);
    expect(screen.queryByText("Floor Areas — completed")).toBeNull();
  });

  it("shows step number in circle for pending steps", () => {
    renderProgress(1);
    // Steps 2-5 are pending: their circles show numbers
    // Step 1 is current (shows number too, since it's not completed)
    const numbers = screen.getAllByText(/^[2-5]$/);
    expect(numbers.length).toBeGreaterThanOrEqual(4);
  });
});

// ── Edge cases ────────────────────────────────────────────────────────────────

describe("WizardProgress edge cases", () => {
  it("renders correctly on the first step without crashing", () => {
    expect(() => renderProgress(1)).not.toThrow();
  });

  it("renders correctly on the last step without crashing", () => {
    expect(() => renderProgress(5)).not.toThrow();
  });

  it("marks all previous steps as completed on last step", () => {
    renderProgress(5);
    // Steps 1–4 should be completed
    const completedTexts = STEPS.slice(0, 4).map((s) => `${s.title} — completed`);
    completedTexts.forEach((text) => {
      expect(screen.getByText(text)).toBeDefined();
    });
  });
});
