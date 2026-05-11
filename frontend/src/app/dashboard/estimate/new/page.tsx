"use client";

import { useState, useRef, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { uploadFiles } from "@/lib/uploadthing";
import { submitWizardForm, openFormEstimateStream } from "@/services/estimates.service";
import {
  WizardFormData,
  WizardStepId,
  WIZARD_STEPS,
  ProjectBasics,
  FloorAreas,
  BuildingProgram,
  ConstructionDetails,
} from "@/types/wizard";
import { WizardProgress } from "@/components/wizard/WizardProgress";
import { ProjectBasicsStep } from "@/components/wizard/steps/ProjectBasicsStep";
import { FloorAreasStep } from "@/components/wizard/steps/FloorAreasStep";
import { BuildingProgramStep } from "@/components/wizard/steps/BuildingProgramStep";
import { ConstructionDetailsStep } from "@/components/wizard/steps/ConstructionDetailsStep";
import { ReviewSubmitStep } from "@/components/wizard/steps/ReviewSubmitStep";
import {
  CostBreakdownChart,
  ConfidenceBreakdownCard,
  FullBoqTable,
  generateExcelReport,
  downloadExcelBlob,
  type BoqItem,
} from "@/components/results/ResultsComponents";
import { ChevronLeft, ChevronRight, Loader2, Download } from "lucide-react";

// --- Initial form state ---

const INITIAL_FORM: WizardFormData = {
  projectBasics: { building_type: "", floor_count: "", description: "", floorplan_urls: [] },
  floorAreas: { floor_areas: [] },
  buildingProgram: {},
  constructionDetails: {
    finish_level: "", structural_system: "", roof_type: "", ceiling_type: "",
    location: "", soil_condition: "", drainage_type: "", external_works_scope: "",
  },
};

// --- Flat payload builder for API ---

function buildApiPayload(form: WizardFormData): Record<string, unknown> {
  const { projectBasics, floorAreas, buildingProgram, constructionDetails } = form;
  return {
    building_type: projectBasics.building_type || undefined,
    floor_count: projectBasics.floor_count || undefined,
    description: projectBasics.description || undefined,
    floorplan_urls: projectBasics.floorplan_urls || [],
    floor_areas: floorAreas.floor_areas,
    ...buildingProgram,
    ...constructionDetails,
  };
}

// --- Step validation ---

function validateStep(step: WizardStepId, form: WizardFormData): Record<string, string> {
  const errors: Record<string, string> = {};
  if (step === 1) {
    if (!form.projectBasics.building_type) errors.building_type = "Please select a building type.";
    const fc = Number(form.projectBasics.floor_count);
    if (!fc || fc < 1 || fc > 100) errors.floor_count = "Floor count must be between 1 and 100.";
  }
  if (step === 2) {
    if (!form.floorAreas.floor_areas.length) {
      errors.floor_areas = "Please enter area for at least one floor.";
    } else {
      form.floorAreas.floor_areas.forEach((row, i) => {
        const v = typeof row.area_value === "number" ? row.area_value : parseFloat(String(row.area_value));
        if (!v || v <= 0) errors["floor_areas[" + i + "]"] = row.floor_label + " area must be greater than zero.";
      });
    }
  }
  if (step === 3 && form.projectBasics.building_type === "residential") {
    const b = Number(form.buildingProgram.bedrooms);
    if (!b || b < 1 || b > 50) errors.bedrooms = "Please enter a valid number of bedrooms (1-50).";
    const bt = Number(form.buildingProgram.bathrooms);
    if (!bt || bt < 1 || bt > 50) errors.bathrooms = "Please enter a valid number of bathrooms (1-50).";
  }
  if (step === 3 && form.projectBasics.building_type === "commercial") {
    const wc = Number(form.buildingProgram.washroom_count);
    if (!wc || wc < 1) errors.washroom_count = "Commercial buildings must have at least 1 washroom.";
  }
  if (step === 4) {
    if (!form.constructionDetails.finish_level) errors.finish_level = "Please select a finish level.";
    if (!form.constructionDetails.structural_system) errors.structural_system = "Please select a structural system.";
    if (!form.constructionDetails.roof_type) errors.roof_type = "Please select a roof type.";
    if (!form.constructionDetails.ceiling_type) errors.ceiling_type = "Please select a ceiling type.";
  }
  return errors;
}

// --- Main component ---

export default function Home() {
  const { data: session } = useSession();
  const router = useRouter();
  const accessToken = (session?.user as { accessToken?: string } | undefined)?.accessToken ?? "";

  const [currentStep, setCurrentStep] = useState<WizardStepId>(1);
  const [formData, setFormData] = useState<WizardFormData>(INITIAL_FORM);
  const [stepErrors, setStepErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [pipelineStep, setPipelineStep] = useState<string | null>(null);
  const [isEstimating, setIsEstimating] = useState(false);

  const [estimateResult, setEstimateResult] = useState<Record<string, unknown> | null>(null);
  const [excelUrl, setExcelUrl] = useState<string | null>(null);
  const [uploadFailed, setUploadFailed] = useState(false);
  const [stalledWarning, setStalledWarning] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);
  const stalledTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    eventSourceRef.current?.close();
    if (stalledTimerRef.current) clearTimeout(stalledTimerRef.current);
  }, []);

  const handleNext = () => {
    const errors = validateStep(currentStep, formData);
    if (Object.keys(errors).length > 0) {
      setStepErrors(errors);
      return;
    }
    setStepErrors({});
    setCurrentStep((s) => Math.min(s + 1, 5) as WizardStepId);
  };

  const handleBack = () => {
    setStepErrors({});
    setCurrentStep((s) => Math.max(s - 1, 1) as WizardStepId);
  };

  const handleEditStep = (step: WizardStepId) => {
    setStepErrors({});
    setCurrentStep(step);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const payload = buildApiPayload(formData);
      const { session_id, estimate_id } = await submitWizardForm(payload, accessToken || undefined);

      setIsEstimating(true);
      setIsSubmitting(false);

      const source = openFormEstimateStream(session_id);
      eventSourceRef.current = source;

      const resetStalledTimer = () => {
        setStalledWarning(false);
        if (stalledTimerRef.current) clearTimeout(stalledTimerRef.current);
        stalledTimerRef.current = setTimeout(() => setStalledWarning(true), 30_000);
      };
      resetStalledTimer();

      source.addEventListener("progress", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as { step: string; status: string };
        setPipelineStep(data.step + " — " + data.status);
        resetStalledTimer();
      });

      source.addEventListener("info", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as { message: string };
        setPipelineStep(data.message);
        resetStalledTimer();
      });

      source.addEventListener("completed", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as Record<string, unknown>;
        source.close();
        if (stalledTimerRef.current) clearTimeout(stalledTimerRef.current);
        setIsEstimating(false);
        setEstimateResult(data);

        // Navigate to the persisted estimate detail page if we have an ID
        const resolvedEstimateId = (data.estimate_id as string | undefined) ?? estimate_id;
        if (resolvedEstimateId) {
          router.push(`/dashboard/estimates/${resolvedEstimateId}`);
          return;
        }

        void (async () => {
          try {
            const excelBuffer = generateExcelReport(data);
            const blob = new Blob([excelBuffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
            const fileName = "estimate_" + new Date().toISOString().slice(0, 10) + ".xlsx";
            const file = new File([blob], fileName, { type: blob.type });
            const [uploaded] = await uploadFiles("excelUploader", { files: [file] });
            setExcelUrl(uploaded.ufsUrl);
          } catch (err) {
            console.error("Excel upload failed, using Blob URL fallback:", err);
            setUploadFailed(true);
          }
        })();
      });

      source.addEventListener("error", (event) => {
        const raw = (event as MessageEvent).data;
        // Only treat as fatal if the server sent a custom error event with a data payload.
        // Native EventSource reconnect/network errors have no data and should be ignored.
        if (!raw) return;
        if (stalledTimerRef.current) clearTimeout(stalledTimerRef.current);
        const msg = (JSON.parse(raw) as { message?: string }).message ?? "Estimation failed.";
        setIsEstimating(false);
        setSubmitError(msg);
        source.close();
      });

    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Submission failed.");
      setIsSubmitting(false);
    }
  };

  if (estimateResult && !isEstimating) {
    const costs = (estimateResult.costs as Record<string, unknown>) || {};
    const confidence = (estimateResult.confidence as Record<string, unknown>) || {};
    const boqItems = (estimateResult.boq_items as BoqItem[]) || [];
    const subtotals = (costs.subtotals as Record<string, number>) || {};
    const grandTotal = Number(costs.total ?? 0);
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-2xl font-bold mb-2">Estimate Complete</h1>
          <p className="text-zinc-400 mb-8">Your construction cost estimate has been generated.</p>

          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4">
              <p className="text-xs text-zinc-400 mb-1">Grand Total</p>
              <p className="text-xl font-bold text-zinc-100">LKR {grandTotal.toLocaleString()}</p>
            </div>
            <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4">
              <p className="text-xs text-zinc-400 mb-1">Confidence Score</p>
              <p className="text-xl font-bold text-zinc-100">{((Number(confidence.score ?? 0)) * 100).toFixed(1)}%</p>
            </div>
            <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4">
              <p className="text-xs text-zinc-400 mb-1">BOQ Items</p>
              <p className="text-xl font-bold text-zinc-100">{boqItems.length}</p>
            </div>
          </div>

          {/* Confidence breakdown (NEW-CONF-01) */}
          {Object.keys(confidence).length > 0 && (
            <ConfidenceBreakdownCard confidence={confidence} />
          )}

          {/* Per-category cost breakdown chart (IMP-FE-07) */}
          {Object.keys(subtotals).length > 0 && (
            <CostBreakdownChart subtotals={subtotals} />
          )}

          {/* Full BOQ table with no_match highlight (IMP-FE-01/02) */}
          {boqItems.length > 0 && (
            <FullBoqTable items={boqItems} grandTotal={grandTotal} />
          )}

          <div className="flex gap-3">
            {/* Download: UploadThing link if available, else direct Blob fallback (IMP-FE-05) */}
            {excelUrl ? (
              <a
                href={excelUrl}
                download
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <Download className="w-4 h-4" /> Download Excel Report
              </a>
            ) : (
              <button
                onClick={() => downloadExcelBlob(estimateResult)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <Download className="w-4 h-4" />
                {uploadFailed ? "Download Excel Report (local)" : "Download Excel Report"}
              </button>
            )}
            <button
              onClick={() => { setEstimateResult(null); setCurrentStep(1); setFormData(INITIAL_FORM); setExcelUrl(null); setUploadFailed(false); }}
              className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-zinc-200 rounded-lg text-sm font-medium transition-colors"
            >
              New Estimate
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (isEstimating) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center">
        <div className="text-center max-w-sm">
          <Loader2 className="w-10 h-10 text-blue-400 animate-spin mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">Generating Estimate</h2>
          <p className="text-zinc-400 text-sm mb-4">This usually takes 30-90 seconds.</p>
          {pipelineStep && (
            <p className="text-xs text-zinc-500 bg-zinc-800 rounded px-3 py-2">{pipelineStep}</p>
          )}
          {stalledWarning && (
            <p className="text-xs text-yellow-400 bg-yellow-950/30 border border-yellow-800 rounded px-3 py-2 mt-3">
              ⚠ Taking longer than expected — still processing, please wait...
            </p>
          )}
        </div>
      </div>
    );
  }

  const floorCount = Number(formData.projectBasics.floor_count) || 1;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold mb-1">Construction Cost Estimator</h1>
          <p className="text-zinc-400 text-sm">Complete the form to generate your Bill of Quantities estimate.</p>
        </div>

        <WizardProgress steps={WIZARD_STEPS} currentStep={currentStep} />

        <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 mb-6">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-zinc-100">
              {WIZARD_STEPS[currentStep - 1].title}
            </h2>
            <p className="text-sm text-zinc-400 mt-0.5">{WIZARD_STEPS[currentStep - 1].description}</p>
          </div>

          {currentStep === 1 && (
            <ProjectBasicsStep
              data={formData.projectBasics}
              onChange={(d: ProjectBasics) => setFormData((f) => ({ ...f, projectBasics: d }))}
              errors={stepErrors}
            />
          )}
          {currentStep === 2 && (
            <FloorAreasStep
              data={formData.floorAreas}
              floorCount={floorCount}
              onChange={(d: FloorAreas) => setFormData((f) => ({ ...f, floorAreas: d }))}
              errors={stepErrors}
            />
          )}
          {currentStep === 3 && (
            <BuildingProgramStep
              data={formData.buildingProgram}
              buildingType={formData.projectBasics.building_type}
              onChange={(d: BuildingProgram) => setFormData((f) => ({ ...f, buildingProgram: d }))}
              errors={stepErrors}
            />
          )}
          {currentStep === 4 && (
            <ConstructionDetailsStep
              data={formData.constructionDetails}
              onChange={(d: ConstructionDetails) => setFormData((f) => ({ ...f, constructionDetails: d }))}
              errors={stepErrors}
            />
          )}
          {currentStep === 5 && (
            <ReviewSubmitStep
              data={formData}
              onEditStep={handleEditStep}
              isSubmitting={isSubmitting}
              error={submitError}
            />
          )}
        </div>

        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={handleBack}
            disabled={currentStep === 1}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed text-zinc-200 rounded-lg text-sm font-medium transition-colors"
          >
            <ChevronLeft className="w-4 h-4" /> Back
          </button>

          {currentStep < 5 ? (
            <button
              type="button"
              onClick={handleNext}
              className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="flex items-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-lg text-sm font-medium transition-colors"
            >
              {isSubmitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting...</> : "Generate Estimate"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
