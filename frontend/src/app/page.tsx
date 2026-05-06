"use client";

import { useState, useRef, useEffect } from "react";
import * as XLSX from "xlsx";
import { uploadFiles } from "@/lib/uploadthing";
import { submitWizardForm, openFormEstimateStream } from "../services/estimation";
import {
  WizardFormData,
  WizardStepId,
  WIZARD_STEPS,
  ProjectBasics,
  FloorAreas,
  BuildingProgram,
  ConstructionDetails,
  ExcelPreviewRow,
} from "@/types/wizard";
import { WizardProgress } from "@/components/wizard/WizardProgress";
import { ProjectBasicsStep } from "@/components/wizard/steps/ProjectBasicsStep";
import { FloorAreasStep } from "@/components/wizard/steps/FloorAreasStep";
import { BuildingProgramStep } from "@/components/wizard/steps/BuildingProgramStep";
import { ConstructionDetailsStep } from "@/components/wizard/steps/ConstructionDetailsStep";
import { ReviewSubmitStep } from "@/components/wizard/steps/ReviewSubmitStep";
import { ChevronLeft, ChevronRight, Loader2, Download } from "lucide-react";

// --- Excel generator (client-side, SheetJS) ---

function generateExcelReport(data: Record<string, unknown>): ArrayBuffer {
  const wb = XLSX.utils.book_new();
  const projectInfo = (data.project_info as Record<string, unknown>) || {};
  const parameters  = (projectInfo.parameters as Record<string, unknown>) || {};
  const costs       = (data.costs as Record<string, unknown>) || {};
  const confidence  = (data.confidence as Record<string, unknown>) || {};
  const boqItems    = (data.boq_items as Record<string, unknown>[]) || [];

  const summaryRows: unknown[][] = [
    ["CONSTRUCTION COST ESTIMATION REPORT"],
    [],
    ["PROJECT DETAILS", ""],
    ["Building Type",    projectInfo.building_type  || "—"],
    ["Number of Floors", projectInfo.floors         || "—"],
    ["Built-up Area",    parameters.built_up_area   || "—"],
    ["Finish Level",     parameters.finish_level    || "—"],
    ["Roof Type",        parameters.roof_type       || "—"],
    ["Ceiling Type",     parameters.ceiling_type    || "—"],
    ["Location",         parameters.location        || "—"],
    [],
    ["COST SUMMARY", ""],
    ["Base Total (LKR)",   costs.base_total   ?? 0],
    ["Contingencies (5%)", costs.contingencies ?? 0],
    ["Grand Total (LKR)",  costs.total        ?? 0],
    [],
    ["ESTIMATE QUALITY", ""],
    ["Confidence Score", String(((confidence.score as number || 0) * 100).toFixed(1)) + "%"],
    ["Total BOQ Items",  boqItems.length],
  ];
  const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows);
  summarySheet["!cols"] = [{ wch: 30 }, { wch: 42 }];
  XLSX.utils.book_append_sheet(wb, summarySheet, "Summary");

  const boqHeaders = ["No.", "Description", "Category", "Unit", "Quantity", "Rate (LKR)", "Cost (LKR)", "BSR Code", "Match %"];
  const boqRows: unknown[][] = [boqHeaders];
  for (let i = 0; i < boqItems.length; i++) {
    const item = boqItems[i];
    const conf = item.match_confidence as number | undefined;
    boqRows.push([
      i + 1,
      item.description || item.bsr_description || "—",
      item.section || item.category || "Uncategorized",
      item.unit || "—",
      item.quantity ?? 0,
      item.rate ?? 0,
      item.cost ?? 0,
      item.bsr_item_no || "—",
      conf != null ? String((conf * 100).toFixed(0)) + "%" : "—",
    ]);
  }
  boqRows.push([]);
  boqRows.push(["", "", "", "", "", "GRAND TOTAL (incl. 5% Contingencies)", costs.total ?? 0, "", ""]);
  const boqSheet = XLSX.utils.aoa_to_sheet(boqRows);
  boqSheet["!cols"] = [{ wch: 6 }, { wch: 48 }, { wch: 26 }, { wch: 10 }, { wch: 12 }, { wch: 16 }, { wch: 16 }, { wch: 18 }, { wch: 10 }];
  XLSX.utils.book_append_sheet(wb, boqSheet, "Bill of Quantities");

  const subtotals = (costs.subtotals as Record<string, number>) || {};
  const baseTotal = (costs.base_total as number) || 1;
  const breakdownRows: unknown[][] = [["Category", "Subtotal (LKR)", "% of Base Total"]];
  Object.entries(subtotals).sort(([, a], [, b]) => b - a).forEach(([cat, amount]) => {
    breakdownRows.push([cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()), amount, String(((amount / baseTotal) * 100).toFixed(1)) + "%"]);
  });
  breakdownRows.push([]);
  breakdownRows.push(["Base Total", costs.base_total ?? 0, "100%"]);
  breakdownRows.push(["Contingencies (5%)", costs.contingencies ?? 0, ""]);
  breakdownRows.push(["Grand Total", costs.total ?? 0, ""]);
  const breakdownSheet = XLSX.utils.aoa_to_sheet(breakdownRows);
  breakdownSheet["!cols"] = [{ wch: 36 }, { wch: 20 }, { wch: 16 }];
  XLSX.utils.book_append_sheet(wb, breakdownSheet, "Cost Breakdown");

  return XLSX.write(wb, { bookType: "xlsx", type: "array" }) as ArrayBuffer;
}

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
    floorplan_image_url: projectBasics.floorplan_urls?.[0] || undefined,
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
  const [currentStep, setCurrentStep] = useState<WizardStepId>(1);
  const [formData, setFormData] = useState<WizardFormData>(INITIAL_FORM);
  const [stepErrors, setStepErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [pipelineStep, setPipelineStep] = useState<string | null>(null);
  const [isEstimating, setIsEstimating] = useState(false);

  const [estimateResult, setEstimateResult] = useState<Record<string, unknown> | null>(null);
  const [excelUrl, setExcelUrl] = useState<string | null>(null);
  const [excelPreview, setExcelPreview] = useState<ExcelPreviewRow[]>([]);
  const [excelTotal, setExcelTotal] = useState<number>(0);

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => () => { eventSourceRef.current?.close(); }, []);

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
      const { session_id } = await submitWizardForm(payload);

      setIsEstimating(true);
      setIsSubmitting(false);

      const source = openFormEstimateStream(session_id);
      eventSourceRef.current = source;

      source.addEventListener("progress", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as { step: string; status: string };
        setPipelineStep(data.step + " — " + data.status);
      });

      source.addEventListener("info", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as { message: string };
        setPipelineStep(data.message);
      });

      source.addEventListener("completed", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as Record<string, unknown>;
        source.close();
        setIsEstimating(false);
        setEstimateResult(data);

        const boqItems = (data.boq_items as Record<string, unknown>[]) || [];
        const preview: ExcelPreviewRow[] = boqItems.slice(0, 5).map((item) => ({
          description: String(item.description || item.bsr_description || "—"),
          unit:        String(item.unit || "—"),
          quantity:    Number(item.quantity ?? 0),
          rate:        Number(item.rate ?? 0),
          cost:        Number(item.cost ?? 0),
        }));
        const costs = (data.costs as Record<string, unknown>) || {};
        setExcelPreview(preview);
        setExcelTotal(Number(costs.total ?? 0));

        void (async () => {
          try {
            const excelBuffer = generateExcelReport(data);
            const blob = new Blob([excelBuffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
            const fileName = "estimate_" + new Date().toISOString().slice(0, 10) + ".xlsx";
            const file = new File([blob], fileName, { type: blob.type });
            const [uploaded] = await uploadFiles("excelUploader", { files: [file] });
            setExcelUrl(uploaded.ufsUrl);
          } catch (err) {
            console.error("Excel generation failed:", err);
          }
        })();
      });

      source.addEventListener("error", (event) => {
        const raw = (event as MessageEvent).data;
        const msg = raw ? (JSON.parse(raw) as { message?: string }).message ?? "Estimation failed." : "Estimation failed.";
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
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-bold mb-2">Estimate Complete</h1>
          <p className="text-zinc-400 mb-8">Your construction cost estimate has been generated.</p>

          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4">
              <p className="text-xs text-zinc-400 mb-1">Grand Total</p>
              <p className="text-xl font-bold text-zinc-100">LKR {Number(costs.total ?? 0).toLocaleString()}</p>
            </div>
            <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4">
              <p className="text-xs text-zinc-400 mb-1">Confidence Score</p>
              <p className="text-xl font-bold text-zinc-100">{((Number(confidence.score ?? 0)) * 100).toFixed(1)}%</p>
            </div>
            <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-4">
              <p className="text-xs text-zinc-400 mb-1">BOQ Items</p>
              <p className="text-xl font-bold text-zinc-100">{((estimateResult.boq_items as unknown[]) || []).length}</p>
            </div>
          </div>

          {excelPreview.length > 0 && (
            <div className="mb-6">
              <h2 className="text-sm font-semibold text-zinc-300 mb-3">Top BOQ Items (preview)</h2>
              <div className="overflow-x-auto rounded-lg border border-zinc-700">
                <table className="w-full text-xs">
                  <thead className="bg-zinc-800 text-zinc-400">
                    <tr>
                      <th className="px-3 py-2 text-left">Description</th>
                      <th className="px-3 py-2 text-right">Unit</th>
                      <th className="px-3 py-2 text-right">Qty</th>
                      <th className="px-3 py-2 text-right">Rate (LKR)</th>
                      <th className="px-3 py-2 text-right">Cost (LKR)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800">
                    {excelPreview.map((row, i) => (
                      <tr key={i} className="text-zinc-300">
                        <td className="px-3 py-2">{row.description}</td>
                        <td className="px-3 py-2 text-right">{row.unit}</td>
                        <td className="px-3 py-2 text-right">{row.quantity}</td>
                        <td className="px-3 py-2 text-right">{row.rate.toLocaleString()}</td>
                        <td className="px-3 py-2 text-right">{row.cost.toLocaleString()}</td>
                      </tr>
                    ))}
                    <tr className="bg-zinc-800 font-semibold text-zinc-200">
                      <td className="px-3 py-2" colSpan={4}>Grand Total (incl. 5% contingencies)</td>
                      <td className="px-3 py-2 text-right">LKR {excelTotal.toLocaleString()}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="flex gap-3">
            {excelUrl && (
              <a
                href={excelUrl}
                download
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <Download className="w-4 h-4" /> Download Excel Report
              </a>
            )}
            <button
              onClick={() => { setEstimateResult(null); setCurrentStep(1); setFormData(INITIAL_FORM); setExcelUrl(null); }}
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
